"""Render a firmware-55 one-shot service-configuration selection experiment.

Original firmware inputs and generated OEM-containing outputs stay private.
This is a bench experiment, not an installer or a persistent feature policy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

HERE = Path(__file__).resolve().parent
AUTOSTART_SHA = "b91b2c5a5b7d036860321da730ad571dbae9164d2632946f6566238c3cd42e31"
CONFIG_SHA = "52dac9b051ab02a07afdc7bdfac56402420f8230901b5a55a76a7e9c44fb2e08"
MOUNT_GUARD = """awk '$1=="/dev/mmcblk0p2"&&$2=="/tmp/mnt/data_persist"&&$3=="relfs"{n++;split($4,a,",");for(i in a)if(a[i]=="rw")rw++}END{exit !(n==1&&rw==1)}' /proc/mounts || exit 69"""


def fingerprint(data):
    crc = subprocess.check_output(["cksum"], input=data).decode().split()
    return dict(bytes=len(data), md5=hashlib.md5(data).hexdigest(),
                crc=int(crc[0]), sha256=hashlib.sha256(data).hexdigest())


def selector(directory, config, flush, record):
    values = dict(DIRECTORY=directory, MOUNT_GUARD=MOUNT_GUARD)
    for name, data in (("CONFIG", config), ("FLUSH", flush), ("RECORD", record)):
        f = fingerprint(data)
        values[name + "_SIZE"] = str(f["bytes"])
        values[name + "_MD5"] = f["md5"]
    text = re.sub(r"@([A-Z0-9_]+)@", lambda m: values[m[1]] if m[1] == "MOUNT_GUARD"
                  else shlex.quote(values[m[1]]), (HERE / "selector.sh.in").read_text())
    if re.search(r"@[A-Z0-9_]+@", text):
        raise ValueError("unrendered selector token")
    subprocess.run(["/bin/sh", "-n"], input=text.encode(), check=True)
    return text


def hook(directory, selector_bytes):
    # All dependency reads and execution are inside the parent's bounded child.
    guard = f"""d={shlex.quote(directory)}
test -d "$d" && test ! -L "$d" && test "$(/bin/busybox readlink -f "$d")" = "$d" || exit 70
test "$(/bin/busybox stat -c '%a:%u:%g' "$d")" = 700:0:0 || exit 71
p="$d/select.sh"
test -f "$p" && test ! -L "$p" && test "$(/bin/busybox readlink -f "$p")" = "$p" || exit 72
test "$(/bin/busybox stat -c '%a:%u:%g:%h:%s' "$p")" = '600:0:0:1:{len(selector_bytes)}' || exit 73
test "$(/bin/busybox md5sum < "$p")" = '{hashlib.md5(selector_bytes).hexdigest()}  -' || exit 74
exec /bin/sh "$p"
"""
    return f"""
# Open Connect one-shot bench selection; no stdout pipe can hold startup open.
if /bin/busybox timeout -t 5 /bin/sh -c {shlex.quote(guard)} >/dev/null 2>&1; then
    SMCFG_NORMALMODE={shlex.quote(directory + "/generation.conf")}
    echo 'OCBOOT|trial|consumed-before-services'
else
    echo "OCBOOT|baseline|selector_rc=$?"
fi
"""



def build(original, config, flush, directory, output):
    if hashlib.sha256(original).hexdigest() != AUTOSTART_SHA:
        raise ValueError("unsupported autostart original")
    if hashlib.sha256(config).hexdigest() != CONFIG_SHA:
        raise ValueError("unsupported service configuration")
    if not re.fullmatch(r"/tmp/mnt/data_persist/oc-boot-[0-9a-f]{32}", directory):
        raise ValueError("fresh owned experiment directory required")
    if flush[:7] != b"\x7fELF\x01\x01\x01" or int.from_bytes(flush[18:20], "little") != 40:
        raise ValueError("ARM ELF flush helper required")
    record = ("OC_TRIAL_1|" + directory.rsplit("-", 1)[1] + "\n").encode()
    text = selector(directory, config, flush, record)
    insertion = hook(directory, text.encode()).encode()
    anchor = b"        echo $MESSAGE_NORMALMODE\n"
    if original.count(anchor) != 1:
        raise ValueError("normal-mode insertion anchor")
    candidate = original.replace(anchor, anchor + insertion)
    subprocess.run(["/bin/sh", "-n"], input=candidate, check=True)
    output.mkdir(parents=True, exist_ok=False)
    artifacts = {"select.sh": text.encode(), "flush": flush, "armed": record,
                 "generation.conf": config, "autostart.original": original,
                 "autostart.candidate": candidate}
    for name, data in artifacts.items():
        (output / name).write_bytes(data)
    plan = dict(directory=directory, artifacts={k: fingerprint(v) for k, v in artifacts.items()},
                source_pins={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (Path(__file__), HERE / "selector.sh.in", HERE / "flush.c")},
                scope="one no-change configuration trial; no automatic rearming")
    (output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("original", "config", "flush", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--directory", required=True)
    a = p.parse_args()
    print(json.dumps(build(a.original.read_bytes(), a.config.read_bytes(),
                           a.flush.read_bytes(), a.directory, a.output), indent=2))
