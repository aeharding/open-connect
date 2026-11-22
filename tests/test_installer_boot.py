"""Run the actual selector with real records and simulated physical adapters."""

import hashlib
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class InstallerBoot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / "data"
        self.runtime = self.root / "runtime"
        self.tools = self.root / "tools"
        self.source = self.root / "source"
        for path in (self.data, self.runtime, self.tools, self.source):
            path.mkdir(mode=0o700)
        for name in ("packages", "composed", "snapshots"):
            (self.data / name).mkdir(mode=0o700)
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
        # Lock contention is covered separately; this fixture is one process.
        (self.tools / "flock").write_text("#!/bin/sh\nexit 0\n")
        (self.tools / "flock").chmod(0o700)
        subprocess.run(
            ["clang", "-DOC_HOST", ROOT / "cmu/startup/flush.c", "-o", self.source / "flush"],
            check=True,
        )
        shutil.copyfile(self.source / "flush", self.runtime / "flush")
        (self.runtime / "flush").chmod(0o700)
        (self.runtime / "lock").touch()
        (self.runtime / "token").write_text("a" * 32 + "\n")
        (self.runtime / "ignition.sh").write_text("exit 0\n")
        (self.root / "acc").write_text("1\n")
        state = (
            (ASSETS / "state.sh")
            .read_text()
            .replace(
                "uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }",
                "uuid() { openssl rand -hex 16; }",
            )
        )
        (self.source / "state.sh").write_text(state)
        shutil.copyfile(ASSETS / "transaction.sh", self.source / "transaction.sh")
        shutil.copyfile(ASSETS / "access.sh", self.source / "access.sh")
        for name in ("services-sm.awk", "wireless-device.awk", "wireless.sh"):
            shutil.copyfile(ASSETS / name, self.source / name)
        self.log_original = b"synthetic original logging settings\n"
        self.log_library = b"synthetic exact common library\n"
        (self.root / "physical-log-settings").write_bytes(self.log_original)
        (self.root / "common-library").write_bytes(self.log_library)
        firmware = (ASSETS / "firmware.sh").read_text()
        for old, new in {
            "/config/common/log/settings.txt": str(self.root / "physical-log-settings"),
            "/jci/lib/libjcicommon.so": str(self.root / "common-library"),
            "/tmp/common": str(self.root / "common"),
            "8c95ceaf213af1086e913fd78b69c9b00869c848375c3b40de3c36166d5d3ea0": hashlib.sha256(
                self.log_original
            ).hexdigest(),
            "637cc53cd0621ec7fed24be2519b3e208191dd22954d2442d70e854413874b0d": hashlib.sha256(
                self.log_library
            ).hexdigest(),
        }.items():
            firmware = firmware.replace(old, new)
        (self.source / "firmware.sh").write_text(
            firmware
            + r"""
firmware_guard() { :; }
native_guard() { :; }
root_mode() { printf 'ro,noatime\n'; }
cleanup_mount_guard() { :; }
startup_staging_guard() { :; }
nvram_read() { cat "$D-nvram"; }
nvram_change() {
    test "$(cat "$D-nvram")" = "$1" || return 1
    printf '%s\n' "$2" > "$D-nvram"
}
startup_publish() {
    test "$(sha "$AUTOSTART")" = "$3" || return 1
    cp "$1" "$AUTOSTART.next" && metadata "$2" &&
        chmod "$S_MODE" "$AUTOSTART.next" && mv "$AUTOSTART.next" "$AUTOSTART"
}
"""
        )
        (self.source / "service.sh").write_text(
            "printf '%s\\n' " + shlex.quote(str(self.runtime)) + "\n"
        )
        script = (ASSETS / "boot.sh").read_text()
        for old, new in {
            "/tmp/mnt/data_persist/open-connect": str(self.data),
            "/tmp/open-connect": str(self.runtime),
            "/usr/bin/autostart": str(self.root / "data-target"),
            "/proc/sys/kernel/random/boot_id": str(self.root / "boot-id"),
            "/sys/class/gpio/ACC_Sense/value": str(self.root / "acc"),
        }.items():
            script = script.replace(old, new)
        (self.source / "boot.sh").write_text(script)
        manifest = "".join(
            hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
            for p in sorted(self.source.iterdir())
        )
        (self.source / "files.sha256").write_text(manifest)
        self.package_id = hashlib.sha256(manifest.encode()).hexdigest()
        self.package = self.data / "packages" / self.package_id
        shutil.copytree(self.source, self.package)
        composed = self.data / "composed" / self.package_id
        composed.mkdir(mode=0o700)
        for name in (
            "uia.so",
            "mmui.so",
            "mmui.xml",
            "system-app.js",
            "sm-normal-on.conf",
            "sm-wcp-on.conf",
            "index-on.html",
            "index-off.html",
        ):
            (composed / name).write_text("synthetic feature @TOKEN@\n")
        for profile in ("normal", "wcp"):
            for setting in ("on", "off"):
                (composed / f"sm-{profile}-{setting}.conf").write_text(f"{profile} {setting}\n")
        self.env = {**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]}
        self.shell(r"""
printf 'stock\n' > "$D/stock"; chmod 755 "$D/stock"
R_BASE=$(snapshot_create "$D/stock" - 0 0 absent "755:$(id -u):$(id -g)")
printf 'installed\n' > "$D-target"; chmod 755 "$D-target"
cp "$D-target" "$D/composed/$R_BACKEND/autostart"
printf 'disable\n' > "$D-nvram"
R_CURRENT=$(snapshot_create "$D-target" "$R_BACKEND" 1 1 disable "755:$(id -u):$(id -g)")
R_PHASE=active; R_BEFORE=-; R_AFTER=-; R_UNDO=-; R_BUDGET=3; R_OFF=-; R_BOOT=-; R_NOTICE=installed
record_write
""")

    def shell(self, script):
        return subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; umask 077; D=$1; P=$2; R_BACKEND=$3; . "$P/state.sh"\n' + script,
                "test",
                self.data,
                self.package,
                self.package_id,
            ],
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

    def boot(self, number, *, preserve_log=False):
        boot_id = "00000000-0000-0000-0000-" + f"{number:012x}"
        (self.root / "boot-id").write_text(boot_id + "\n")
        shutil.rmtree(self.runtime / "feature", ignore_errors=True)
        (self.runtime / "selected").unlink(missing_ok=True)
        if not preserve_log:
            shutil.rmtree(self.root / "common", ignore_errors=True)
        return subprocess.run(
            ["sh", self.package / "boot.sh"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def record(self):
        return (self.data / "record").read_text().strip().split("|")

    def test_both_board_configurations_follow_selected_warning_preference(self):
        for warning, number in ((1, 1), (0, 2)):
            with self.subTest(warning=warning):
                self.shell(
                    'record_read; snapshot_read "$R_CURRENT"; '
                    'R_CURRENT=$(snapshot_create "$D-target" "$R_BACKEND" 1 '
                    + str(warning)
                    + ' disable "$S_META"); record_write'
                )
                result = self.boot(number)
                self.assertEqual(result.returncode, 0, result.stderr)
                setting = "on" if warning else "off"
                for profile, name in (("normal", "sm.conf"), ("wcp", "sm_WCP.conf")):
                    self.assertEqual(
                        (self.runtime / "feature" / name).read_text(), f"{profile} {setting}\n"
                    )

    def select_wireless(self, value, *, base=0):
        for profile in ("normal", "wcp"):
            args = {
                "jciMMUI": "mouse=filtered-mouse0, keyboard=filtered-keyboard0, display=filtered-touchscreen0",
                "start_network": "UCP",
                "bds": "-interface dbus",
            }
            if profile == "wcp":
                args["jciMMUI"] += ", wcp"
                args["start_network"] = ""
                args["bds"] += " -wcp"
            lines = ["<services>"]
            for name in (
                "jciMMUI",
                "start_network",
                "bds",
                "jciUSBMGR",
                "jciCARPLAY",
                "jciBCA",
                "blm_nms_svc",
                "devicemanager",
                "blm_ira_pandora",
                "jciLDS",
                "aap_service",
                "jciAAPA",
                "stage_wifi",
                "blm_ira_aha",
            ):
                attr = f'name="{name}" autorun="yes" reset_board="yes" retry_count="0"'
                if name in args:
                    attr += f' args="{args[name]}"'
                elif (
                    name in ("jciUSBMGR", "jciCARPLAY", "jciBCA", "blm_nms_svc")
                    and profile == "wcp"
                ):
                    attr += ' args="wcp"'
                elif name == "jciLDS":
                    attr += ' args="actual-gps-provider"'
                lines += ["<service " + attr + ">"]
                if name == "stage_wifi":
                    lines += [
                        '<dependency type="service" value="stage_3"/>',
                        '<dependency type="service" value="blm_ira_aha"/>',
                    ]
                else:
                    lines += ['<dependency type="service" value="existing"/>']
                lines += ["</service>"]
            lines += ["</services>"]
            for setting in ("on", "off"):
                path = self.data / "composed" / self.package_id / f"sm-{profile}-{setting}.conf"
                path.write_text("\n".join(lines) + "\n")
        self.shell(
            'record_read; snapshot_read "$R_CURRENT"; '
            'R_CURRENT=$(snapshot_create "$D-target" "$R_BACKEND" 1 1 disable "$S_META" /dev/null - 1 '
            + str(base)
            + " "
            + str(value)
            + "); record_write"
        )

    def test_wireless_boot_composes_both_profiles_and_preserves_native_services(self):
        self.select_wireless(1)
        result = self.boot(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        feature = self.runtime / "feature"
        for name in ("wireless.sh", "wireless-device.awk"):
            self.assertEqual((feature / name).read_bytes(), (ASSETS / name).read_bytes())
        self.assertEqual((feature / "boot-id").read_bytes(), (self.root / "boot-id").read_bytes())
        self.assertEqual((feature / "wireless-applied").read_text(), "0\n")
        for name in ("sm.conf", "sm_WCP.conf"):
            services = {s.attrib["name"]: s for s in ET.parse(feature / name).iter("service")}
            self.assertEqual(services["jciLDS"].attrib["args"], "actual-gps-provider")
            self.assertEqual(services["jciCARPLAY"].attrib["args"], "wcp")
            self.assertEqual(services["jciCARPLAY"].attrib["reset_board"], "yes")
            self.assertEqual(services["jciCARPLAY"].attrib["retry_count"], "0")
            helper = services["open_connect_wireless"]
            self.assertEqual(
                helper.attrib["args"], "timeout -t 15 sh /tmp/open-connect/feature/wireless.sh"
            )
            self.assertEqual(helper.attrib["reset_board"], "no")
            dependencies = [d.attrib["value"] for d in services["devicemanager"]]
            self.assertEqual(dependencies, ["open_connect_wireless", "existing"])

    def test_wireless_remains_absent_when_disabled_or_startup_budget_is_exhausted(self):
        self.select_wireless(0)
        result = self.boot(1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.runtime / "feature/wireless.sh").exists())
        self.assertNotIn("open_connect_wireless", (self.runtime / "feature/sm.conf").read_text())
        self.select_wireless(1)
        self.shell("record_read; R_BUDGET=0; record_write")
        result = self.boot(2)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "feature").exists())
        self.assertFalse((self.runtime / "selected").exists())

    def test_foreign_wireless_service_argument_refuses_before_other_ram_effects(self):
        self.select_wireless(1, base=1)
        path = self.data / "composed" / self.package_id / "sm-normal-on.conf"
        path.write_text(
            path.read_text().replace('name="jciUSBMGR"', 'name="jciUSBMGR" args="foreign"')
        )
        result = self.boot(1)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "selected").exists())
        self.assertFalse((self.runtime / "feature").exists())
        self.assertFalse((self.root / "common/log/settings.txt").exists())

    def select_base(self, value):
        self.select_wireless(0, base=value)

    def test_base_disables_only_android_auto_leaves_and_restores_them(self):
        for wireless, number in ((0, 1), (1, 2)):
            self.select_wireless(wireless, base=1)
            result = self.boot(number)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ("sm.conf", "sm_WCP.conf"):
                services = {
                    s.get("name"): s
                    for s in ET.parse(self.runtime / "feature" / name).iter("service")
                }
                for leaf in ("aap_service", "jciAAPA"):
                    self.assertEqual(services[leaf].get("autorun"), "no")
                    self.assertEqual(services[leaf].get("reset_board"), "yes")
                self.assertEqual(
                    [d.get("value") for d in services["stage_wifi"]],
                    ["stage_3", "blm_ira_aha"],
                )
                self.assertEqual(services["blm_ira_aha"].get("autorun"), "yes")
                self.assertNotIn("configFilePath", services["bds"].get("args"))
                self.assertEqual("open_connect_wireless" in services, bool(wireless))
        self.select_base(0)
        self.assertEqual(self.boot(3).returncode, 0)
        for name in ("sm.conf", "sm_WCP.conf"):
            services = {
                s.get("name"): s for s in ET.parse(self.runtime / "feature" / name).iter("service")
            }
            self.assertEqual(services["aap_service"].get("autorun"), "yes")
            self.assertEqual(services["jciAAPA"].get("autorun"), "yes")

    def test_base_android_auto_refuses_missing_or_duplicate_leaf(self):
        number = 0
        for leaf in ("aap_service", "jciAAPA"):
            for duplicate in (False, True):
                number += 1
                self.select_base(1)
                path = self.data / "composed" / self.package_id / "sm-normal-on.conf"
                data = path.read_text()
                start = data.index('<service name="' + leaf + '"')
                end = data.index("</service>\n", start) + len("</service>\n")
                stanza = data[start:end]
                path.write_text(data[:start] + (stanza * 2 if duplicate else "") + data[end:])
                self.shell("record_read; R_BUDGET=3; record_write")
                result = self.boot(number)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("service_config_failed", result.stderr)
                self.assertFalse((self.runtime / "feature").exists())
                self.assertFalse((self.runtime / "selected").exists())
                self.assertFalse((self.root / "common").exists())

    def test_logging_is_boot_only_and_disabled_again_on_fallback(self):
        target = self.root / "common/log/settings.txt"
        for enabled, number in ((1, 1), (0, 2), (1, 3)):
            self.select_base(enabled)
            result = self.boot(number)
            self.assertEqual(result.returncode, 0, result.stderr)
            if enabled:
                self.assertEqual(target.read_bytes(), b"COMMON_LOG_LEVEL=Warn\n")
                self.assertEqual(target.stat().st_nlink, 1)
                self.assertEqual(list(target.parent.glob(".open-connect-*")), [])
            else:
                self.assertFalse((self.root / "common").exists())
            self.assertEqual((self.root / "physical-log-settings").read_bytes(), self.log_original)
        result = self.boot(4)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual((self.root / "physical-log-settings").read_bytes(), self.log_original)

    def test_logging_conflict_preserves_other_provider_and_refuses_selected_marker(self):
        self.select_base(1)
        target = self.root / "common/log/settings.txt"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"another provider\n")
        result = self.boot(1, preserve_log=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_bytes(), b"another provider\n")
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual((self.root / "physical-log-settings").read_bytes(), self.log_original)

    def test_service_policy_selects_both_ram_profiles_and_survives_fallback(self):
        composed = self.data / "composed" / self.package_id
        original = '<service name="peer" autorun="yes" />\n<service name="blm_ira_pandora" autorun="yes" />\n'
        for profile in ("normal", "wcp"):
            (composed / f"sm-{profile}-on.conf").write_text(original)
        for enabled, number in ((0, 1), (1, 2), (0, 3)):
            self.shell(
                'record_read; snapshot_read "$R_CURRENT"; '
                'R_CURRENT=$(snapshot_create "$D-target" "$R_BACKEND" 1 1 disable "$S_META" /dev/null - '
                + str(enabled)
                + "); record_write"
            )
            result = self.boot(number)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ("sm.conf", "sm_WCP.conf"):
                expected = (
                    original
                    if enabled
                    else original.replace(
                        'name="blm_ira_pandora" autorun="yes"',
                        'name="blm_ira_pandora" autorun="no"',
                    )
                )
                self.assertEqual((self.runtime / "feature" / name).read_text(), expected)
            self.assertEqual((composed / "sm-normal-on.conf").read_text(), original)
            self.assertEqual((composed / "sm-wcp-on.conf").read_text(), original)
        self.assertNotEqual(self.boot(4).returncode, 0)
        self.assertFalse((self.runtime / "feature").exists())
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual((self.root / "data-nvram").read_text(), "absent\n")
        config = (
            (self.data / "snapshots" / self.record()[5] / "config").read_text().strip().split("|")
        )
        self.assertEqual(config[5], "0")

    def test_reset_budget_is_finite_and_fallback_restores_nvram_without_losing_preferences(self):
        for number in range(1, 4):
            result = self.boot(number)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.record()[9], str(3 - number))
            self.assertTrue((self.runtime / "selected").exists())
        result = self.boot(4)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "selected").exists())
        self.assertEqual((self.root / "data-nvram").read_text(), "absent\n")
        self.assertEqual(self.record()[9], "0")
        config = (self.data / "snapshots" / self.record()[5] / "config").read_text().split("|")
        self.assertEqual(config[1:4], ["1", "1", "absent"])
        self.assertNotEqual(self.boot(5).returncode, 0)
        self.assertEqual((self.root / "data-nvram").read_text(), "absent\n")

    def test_only_off_then_new_kernel_and_on_renews_attempts(self):
        self.assertEqual(self.boot(1).returncode, 0)
        self.shell("record_read; R_OFF=$R_BOOT; record_write")
        # The same kernel cannot consume or renew another attempt.
        self.assertNotEqual(self.boot(1).returncode, 0)
        self.assertEqual(self.record()[9], "2")
        (self.root / "acc").write_text("0\n")
        self.assertEqual(self.boot(2).returncode, 0)
        self.assertEqual(self.record()[9], "1")
        self.shell("record_read; R_OFF=$R_BOOT; record_write")
        (self.root / "acc").write_text("1\n")
        self.assertEqual(self.boot(3).returncode, 0)
        self.assertEqual(self.record()[9], "2")

    def test_ignition_requires_sustained_off_and_clears_quick_resume_evidence(self):
        self.assertEqual(self.boot(1).returncode, 0)
        boot = self.record()[11]
        script = (ASSETS / "ignition.sh").read_text()
        for old, new in {
            "/tmp/mnt/data_persist/open-connect": str(self.data),
            "/tmp/open-connect": str(self.runtime),
            "/proc/sys/kernel/random/boot_id": str(self.root / "boot-id"),
            "/sys/class/gpio/ACC_Sense/value": str(self.root / "acc"),
        }.items():
            script = script.replace(old, new)
        (self.package / "ignition.sh").write_text(script)
        (self.root / "sequence").write_text("0\n1\n0\n0\n0\n1\nend\n")
        (self.root / "step").write_text("0\n")
        # Advance physical samples instead of waiting; capture the real record
        # after each observation, including a short OFF and same-kernel resume.
        (self.tools / "sleep").write_text(
            "#!/bin/sh\nset -eu\nR=" + shlex.quote(str(self.root)) + "\n"
            'cut -d "|" -f 11 "$R/data/record" >> "$R/observed"\n'
            'n=$(cat "$R/step"); n=$((n+1)); echo "$n" > "$R/step"\n'
            'next=$(sed -n "${n}p" "$R/sequence")\n'
            'if test "$next" = end; then echo changed > "$R/boot-id"; '
            'else printf "%s\\n" "$next" > "$R/acc"; fi\n'
        )
        (self.tools / "sleep").chmod(0o700)
        subprocess.run(
            ["sh", self.package / "ignition.sh", boot],
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        self.assertEqual(
            (self.root / "observed").read_text().splitlines(), ["-", "-", "-", "-", "-", boot, "-"]
        )
        self.assertEqual(self.record()[9:11], ["2", "-"])

    def test_boot_finishes_interrupted_uninstall_from_ram_and_starts_stock(self):
        self.shell(r"""
. "$P/firmware.sh"
. "$P/transaction.sh"
AUTOSTART=$D-target
record_read
transaction_prepare uninstall "$R_CURRENT" "$R_BASE"
""")
        result = self.boot(1)
        # The hook uses Mazda's original configuration on a nonzero exit.
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.data.exists())
        self.assertEqual((self.root / "data-target").read_text(), "stock\n")
        self.assertEqual((self.root / "data-nvram").read_text(), "absent\n")
        self.assertFalse((self.runtime / "selected").exists())
