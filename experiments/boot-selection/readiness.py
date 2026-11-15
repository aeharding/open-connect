"""Add an independent startup receiver to a fresh private feature generation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

import feature
import prototype

HERE = Path(__file__).resolve().parent
RECEIVER = HERE.parents[1] / "cmu/startup/ready-receiver.c"


def watch(directory, binary, *, port=48637, deadline=90, recover=False):
    feature.directory_guard(directory)
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("loopback port")
    if type(deadline) is not int or not 5 <= deadline <= 180:
        raise ValueError("bounded startup deadline, 5..180 seconds")
    values = dict(DIRECTORY=shlex.quote(directory), GENERATION=directory.rsplit("-", 1)[1],
                  PORT=str(port), DEADLINE=str(deadline), RECOVERY="yes" if recover else "no",
                  RECEIVER_SIZE=str(len(binary)), RECEIVER_MD5=hashlib.md5(binary).hexdigest())
    text = re.sub(r"@([A-Z0-9_]+)@", lambda m: values[m[1]],
                  (HERE / "ready-watch.sh.in").read_text())
    subprocess.run(["/bin/sh", "-n"], input=text.encode(), check=True)
    return text.encode()


def commit(directory):
    # Runs inline in the startup parent. No timed child can publish a late grant.
    generation = directory.rsplit("-", 1)[1]
    return """
oc_commit_selection() {
 oc_w=/tmp/oc-health-@GEN@
 oc_boot=$(cat /proc/sys/kernel/random/boot_id) || return 1
 case "$oc_boot" in ????????-????-????-????-????????????) :;; *)return 1;;esac
 case "$oc_boot" in *[!0-9a-f-]*)return 1;;esac
 oc_tries=0
 until mkdir -m 700 "$oc_w/decision.lock" 2>/dev/null;do
  oc_tries=$((oc_tries+1));test "$oc_tries" -lt 3 || return 1
  sleep 1
 done
 oc_ok=no
 if test "$(cat "$oc_w/boot")" = "$oc_boot" &&
    test ! -e "$oc_w/cancelled" && test ! -e "$oc_w/result" &&
    test ! -e "$oc_w/selected" && test ! -L "$oc_w/selected";then
  oc_worker=$(cat "$oc_w/worker")
  case "$oc_worker" in ''|*[!0-9]*) :;;
   *)
    if kill -0 "$oc_worker" 2>/dev/null &&
       printf '%s\n' "@GEN@.$oc_boot" > "$oc_w/selected.next";then
     SMCFG_NORMALMODE=@CONFIG@
     if mv "$oc_w/selected.next" "$oc_w/selected";then
      oc_ok=yes
     else
      SMCFG_NORMALMODE=/jci/sm/sm.conf
     fi
    fi
    ;;
  esac
 fi
 rmdir "$oc_w/decision.lock" 2>/dev/null || :
 if test "$oc_ok" = yes;then
  echo "OCHEALTH|authorized|@GEN@|$oc_boot" || :
  return 0
 fi
 return 1
}
""".replace("@GEN@", generation).replace("@CONFIG@", shlex.quote(directory+"/generation.conf"))


def hook(directory, selector):
    text = prototype.hook(directory, selector)
    prepare = ("/bin/busybox timeout -t 5 /bin/sh " +
               shlex.quote(directory + "/ready-watch.sh") + " prepare")
    old = " >/dev/null 2>&1; then"
    if text.count(old) != 1:
        raise ValueError("selection hook shape")
    text = text.replace(old, " >/dev/null 2>&1 && " + prepare + "; then")
    old = ("    SMCFG_NORMALMODE=" + shlex.quote(directory+"/generation.conf") +
           "\n    echo 'OCBOOT|trial|consumed-before-services'")
    if text.count(old) != 1:
        raise ValueError("selection commitment shape")
    text = text.replace(old, """    if oc_commit_selection; then
        echo 'OCBOOT|trial|consumed-before-services' || :
    else
        echo 'OCBOOT|baseline|health-commit-failed' || :
    fi""")
    return commit(directory) + text


def build(source, receiver, output, *, recover=False, deadline=90):
    plan = json.loads((source / "plan.json").read_text())
    directory = plan["directory"]
    feature.directory_guard(directory)
    if plan.get("log_level") is not None or not plan.get("home_ready_probe"):
        raise ValueError("Home-probed paired feature generation required")
    if plan["source_pins"].get("cmu/adapters/fw55/home-ready.js") != hashlib.sha256(feature.HOME_READY.read_bytes()).hexdigest():
        raise ValueError("current acknowledgement adapter required")
    data = {}
    for name, expected in plan["artifacts"].items():
        if not re.fullmatch(r"[a-z][a-z0-9.-]*", name):
            raise ValueError("artifact name")
        content = (source / name).read_bytes()
        if prototype.fingerprint(content) != expected:
            raise ValueError("changed generation artifact: " + name)
        data[name] = content
    if hashlib.sha256(data["autostart.original"]).hexdigest() != prototype.AUTOSTART_SHA:
        raise ValueError("original autostart")
    binary = receiver.read_bytes()
    record = json.loads(receiver.with_name("build.json").read_text())
    if record["sha256"] != hashlib.sha256(binary).hexdigest() or record["source_sha256"] != hashlib.sha256(RECEIVER.read_bytes()).hexdigest():
        raise ValueError("receiver build provenance")
    if binary[:7] != b"\x7fELF\x01\x01\x01" or int.from_bytes(binary[18:20], "little") != 40:
        raise ValueError("ARM receiver required")
    nonce = directory.rsplit("-", 1)[1]
    script = ('<script src="file:///tmp/oc-health-' + nonce + '/session.js"></script>\n').encode()
    data["index.html"] = feature.replace_once(data["index.html"], b"<head>", b"<head>\n" + script)
    data["ready-receiver"] = binary
    data["ready-watch.sh"] = watch(directory, binary, recover=recover, deadline=deadline)
    deps = {n: data[n] for n in (*plan["dependencies"], "ready-receiver", "ready-watch.sh")}
    data["select.sh"] = prototype.selector(directory, data["generation.conf"], data["flush"],
                                           data["armed"], deps).encode()
    data["autostart.candidate"] = feature.replace_once(data["autostart.original"],
        b"        echo $MESSAGE_NORMALMODE\n",
        b"        echo $MESSAGE_NORMALMODE\n" + hook(directory, data["select.sh"]).encode())
    subprocess.run(["/bin/sh", "-n"], input=data["autostart.candidate"], check=True)
    output = feature.loader.elf.private_output(output)
    output.mkdir(parents=True, exist_ok=False)
    for name, content in data.items():
        (output / name).write_bytes(content)
    plan.update(artifacts={n: prototype.fingerprint(b) for n, b in data.items()},
                dependencies=sorted(deps),
                health=dict(port=48637, deadline_seconds=deadline, recover_on_timeout=recover,
                            current_boot_token=True, replenishes_attempts=False,
                            work_directory="/tmp/oc-health-" + nonce))
    for p in (Path(__file__), HERE/"ready-watch.sh.in", RECEIVER, feature.HOME_READY):
        plan["source_pins"][str(p.relative_to(HERE.parents[1]))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (output/"plan.json").write_text(json.dumps(plan, indent=2)+"\n")
    return plan


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "receiver", "output"):
        p.add_argument("--"+name, required=True, type=Path)
    p.add_argument("--recover-on-timeout", action="store_true",
                   help="permit one normal reboot after selected startup fails; defaults to observation only")
    p.add_argument("--deadline", type=int, default=90)
    a = p.parse_args()
    print(json.dumps(build(a.source, a.receiver, a.output, recover=a.recover_on_timeout, deadline=a.deadline)))
