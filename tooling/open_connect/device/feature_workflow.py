"""One useful feature trial and baseline return, using the existing boot loop."""

import argparse
import json
import secrets
from pathlib import Path

from open_connect.paths import source_name

from . import boot as stock
from . import feature_state as d


def observe(args, wanted):
    commands = d.status_commands(check_artifacts=wanted == "selected")

    def check(rc, raw, before=None):
        value = d.parse_status(rc, raw)
        if before is None:
            if wanted == "selected" and (
                value["loaded"] != "baseline"
                or not value["installed_hook"]
                or value["SELECTOR"] != "armed"
            ):
                raise ValueError(
                    "trial request requires candidate hook and unused armed generation"
                )
            if wanted == "baseline" and value["installed_hook"]:
                raise ValueError("startup hook must be restored before baseline request")
            return value
        if value["BOOT"] == before["BOOT"] or float(value["UPTIME"].split()[0]) >= float(
            before["UPTIME"].split()[0]
        ):
            raise ValueError("fresh boot not established")
        if value["loaded"] != wanted:
            raise ValueError("expected " + wanted + " runtime; observed " + value["loaded"])
        if wanted == "selected" and value["SELECTOR"] != "spent":
            raise ValueError("selected startup did not consume its attempt")
        if wanted == "selected" and not value["home_acknowledged"]:
            raise ValueError("selected Home acknowledgement absent")
        return value

    profile = dict(
        source_pins={
            source_name(p): stock.sha(p)
            for p in (
                d.ROOT / "tooling/open_connect/device/boot.py",
                d.ROOT / "tooling/open_connect/session.py",
                Path(__file__),
                Path(d.__file__),
            )
        },
        normal_reboot_route_verified=True,
        reboot_hex=stock.REBOOT.hex(),
        scope="one " + wanted + " developer startup",
    )
    profile_path = d.R / (args.action + "-profile.json")
    d.save(profile_path.name, profile)
    outcome = "feature_" + wanted + "_startup_verified"
    return stock.main(
        [
            "--live",
            "--bundle",
            str(args.bundle),
            "--credentials",
            str(args.credentials),
            "--profile",
            str(profile_path),
            "--owner",
            args.owner,
            "--camera-index",
            str(args.camera_index),
            "--solicit-prompt",
        ],
        check_commands=commands,
        check_result=check,
        source_kind=wanted,
        success_outcome=outcome,
    )


def cancel_watcher():
    nonce = d.D.rsplit("-", 1)[1]
    # Independent cancellation: no candidate file is read or executed. This is
    # the same current-boot lock protocol as the tested supervisor.
    d.command(
        f"""
set -fu
w=/tmp/oc-health-{nonce}
if test -e "$w" || test -L "$w";then
 test -d "$w" && test ! -L "$w" && test "$(readlink -f "$w")" = "$w" || exit 70
 test "$(stat -c '%a:%u:%g' "$w")" = 700:0:0 || exit 71
 boot=$(cat /proc/sys/kernel/random/boot_id) || exit 72
 test "$(cat "$w/boot")" = "$boot" || exit 73
 mkdir -m 700 "$w/decision.lock" || exit 74
 trap 'rmdir "$w/decision.lock" 2>/dev/null' EXIT
 test ! -e "$w/reboot-requested" || exit 75
 test ! -L "$w/cancelled" || exit 76
 : > "$w/cancelled" || exit 77
fi
""",
        "cancel-" + secrets.token_hex(4),
    )


def record_observer_outcome(run, args, rc, success):
    # The observer's durable manifest distinguishes a known unsent request from
    # an uncertain one. Missing or malformed evidence stays uncertain.
    if rc == 0:
        run["phase"] = success
    else:
        try:
            manifest = json.loads((args.bundle / "manifest.json").read_text())
            unsent = manifest["outcome"] == "failed_before_request"
        except (OSError, ValueError, KeyError, TypeError):
            unsent = False
        if unsent:
            run["phase"] = (
                "restored_pending_baseline"
                if args.action == "disable"
                else "published_request_not_sent"
            )
    d.save("run.json", run)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("status", "trial", "disable"))
    p.add_argument("--state", required=True, type=Path)
    p.add_argument("--owner", required=True)
    p.add_argument("--bundle", required=True, type=Path)
    p.add_argument("--credentials", type=Path)
    p.add_argument("--camera-index", type=int)
    args = p.parse_args(argv)
    run = d.load_existing(args.state, args.owner)
    if args.bundle.exists():
        raise ValueError("fresh operation bundle required")
    if args.action == "status":
        raw = d.command(d.status_script(), str(args.bundle.resolve()))
        result = d.parse_status(0, raw)
        (args.bundle / "state.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(dict(outcome="state_observed", **result)))
        return 0
    # Validate camera/login arguments before any publication or restoration.
    if args.credentials is None or args.camera_index is None or args.camera_index < 0:
        p.error("trial/disable require private credentials and camera index")
    stock.private_credentials(args.credentials)
    if args.action == "trial":
        from open_connect.feature import compatible_sources, inspect_build

        inspect_build(Path(run["build"]))
        if not compatible_sources(d.ROOT, run["source_sha256"]) or run["phase"] not in (
            "prepared",
            "published_request_not_sent",
        ):
            raise ValueError("fresh prepared state from the current checked source is required")
        if run["phase"] == "prepared":
            before = d.parse_status(0, d.command(d.status_script(), "before-publication"))
            if (
                before["loaded"] != "baseline"
                or before["installed_hook"]
                or before["SELECTOR"] != "armed"
            ):
                raise ValueError("baseline required before publishing startup hook")
            d.resources("baseline-resources")
            # No resend after an incomplete start. The target also requires the exact
            # original and prepared control before publication.
            run["phase"] = "trial_started"
            d.save("run.json", run)
            d.action("APPLY", "apply")
            run["phase"] = "published"
            d.save("run.json", run)
        run["phase"] = "trial_requested"
        d.save("run.json", run)
        rc = observe(args, "selected")
        run["phase"] = "trial_unknown"
        record_observer_outcome(run, args, rc, "selected_verified")
        if rc == 0:
            d.resources("selected-resources")
        return rc
    if run["phase"] in (
        "baseline_requested",
        "baseline_verified_pending_cleanup",
        "disabled_baseline_verified",
    ):
        raw = d.command(d.status_script(check_artifacts=False), str(args.bundle.resolve()))
        current = d.parse_status(0, raw)
        if current["installed_hook"] or current["loaded"] != "baseline":
            raise ValueError("prior baseline request unresolved; preserve state, no reboot retry")
        d.action("CLEAN", "clean-" + secrets.token_hex(4))
        run["phase"] = "disabled_baseline_verified"
        d.save("run.json", run)
        print(json.dumps(dict(outcome="disabled_baseline_verified", reboot_requested=False)))
        return 0
    # Restoration is independent of a successful trial or current feature code.
    cancel_watcher()
    d.action("UNDO", "undo-" + secrets.token_hex(4))
    run["phase"] = "restored_pending_baseline"
    d.save("run.json", run)
    run["phase"] = "baseline_requested"
    d.save("run.json", run)
    rc = observe(args, "baseline")
    record_observer_outcome(run, args, rc, "baseline_verified_pending_cleanup")
    if rc == 0:
        d.resources("restored-resources")
        d.action("CLEAN", "clean-" + secrets.token_hex(4))
        d.action("VERIFY", "final-" + secrets.token_hex(4))
        run["phase"] = "disabled_baseline_verified"
        d.save("run.json", run)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
