"""Build a bounded-attempt adaptation of an exact private composed generation.

This qualifies reservation/confirmation/administrative renewal, not automatic ACC
or production health policy. Output contains OEM files and must stay private.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

import prototype

HERE = Path(__file__).resolve().parent


def initial_record(generation):
    if not re.fullmatch(r"[0-9a-f]{32}", generation):
        raise ValueError("generation nonce")
    line = f"OC_ATTEMPT_1|{generation}|0|trial|0|none\n".encode()
    return line + b"MD5|" + hashlib.md5(line).hexdigest().encode() + b"\n"


def render(directory, artifacts, limit):
    if not re.fullmatch(r"/tmp/mnt/data_persist/oc-boot-[0-9a-f]{32}", directory):
        raise ValueError("generation directory")
    if type(limit) is not int or not 1 <= limit <= 9:
        raise ValueError("explicit bounded test limit, 1..9")
    values = dict(DIRECTORY=shlex.quote(directory), GENERATION=directory.rsplit("-", 1)[1],
                  LIMIT=str(limit), MOUNT_GUARD=prototype.MOUNT_GUARD,
                  FLUSH_SIZE=str(len(artifacts["flush"])),
                  FLUSH_MD5=hashlib.md5(artifacts["flush"]).hexdigest())
    guards = []
    for name in ("generation.conf", "mmui.so", "bootstrap.so", "index.html", "probe.js"):
        data = artifacts[name]
        guards += [f'file "$D/{name}" 600',
                   f'test "$(stat -c %s "$D/{name}")" = {len(data)} || refuse dependency_size',
                   f'test "$(md5sum < "$D/{name}")" = \'{hashlib.md5(data).hexdigest()}  -\' || refuse dependency_hash']
    values["DEPENDENCY_GUARDS"] = "\n ".join(guards)
    text = re.sub(r"@([A-Z0-9_]+)@", lambda m: values[m[1]], (HERE / "budget.sh.in").read_text())
    if re.search(r"@[A-Z0-9_]+@", text):
        raise ValueError("unrendered policy token")
    subprocess.run(["/bin/sh", "-n"], input=text.encode(), check=True)
    return text.encode()


def hook(directory, code, log_level):
    text = prototype.hook(directory, code, log_level)
    old = 'exec /bin/sh "$p"\n'
    if text.count(old) != 1:
        raise ValueError("explicit selection entry")
    return text.replace(old, 'exec /bin/sh "$p" SELECT\n').replace(
        "one-shot bench selection", "bounded-attempt bench selection")


def build(source, output, limit):
    source = source.resolve()
    plan = json.loads((source / "plan.json").read_text())
    names = {"generation.conf", "mmui.so", "bootstrap.so", "index.html", "probe.js",
             "flush", "autostart.original", "autostart.candidate", "select.sh", "armed"}
    if set(plan["artifacts"]) != names:
        raise ValueError("exact composed generation required")
    data = {}
    for name in names:
        content = (source / name).read_bytes()
        if prototype.fingerprint(content) != plan["artifacts"][name]:
            raise ValueError("changed input " + name)
        data[name] = content
    original = data["autostart.original"]
    if hashlib.sha256(original).hexdigest() != prototype.AUTOSTART_SHA:
        raise ValueError("unsupported autostart")
    directory = plan["directory"]
    code = render(directory, data, limit)
    insertion = hook(directory, code, plan["log_level"]).encode()
    anchor = b"        echo $MESSAGE_NORMALMODE\n"
    if original.count(anchor) != 1:
        raise ValueError("normal mode anchor")
    data["autostart.candidate"] = original.replace(anchor, anchor + insertion)
    subprocess.run(["/bin/sh", "-n"], input=data["autostart.candidate"], check=True)
    data["select.sh"] = code
    del data["armed"]
    data["policy"] = initial_record(directory.rsplit("-", 1)[1])
    # Reuse the existing private-output boundary; no public OEM output.
    from compose import loader
    output = loader.elf.private_output(output)
    output.mkdir(parents=True, exist_ok=False)
    for name, content in data.items():
        (output / name).write_bytes(content)
    plan.update(scope="finite attempt policy experiment; explicit renewal only",
                test_attempt_limit=limit,
                artifacts={k: prototype.fingerprint(v) for k, v in data.items()},
                policy=dict(initial_phase="trial", confirm_refunds_attempts=False,
                            automatic_renewal=False, acc_qualified=False,
                            boot_field="fences the latest reservation or renewal boot"))
    for p in (Path(__file__), HERE / "budget.sh.in", HERE / "prototype.py"):
        plan["source_pins"][str(p.relative_to(HERE.parents[1]))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="fresh composed payload directory")
    parser.add_argument("--output", type=Path, required=True, help="new private output directory")
    parser.add_argument("--attempts", type=int, required=True, help="experiment parameter, not a product default")
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.attempts)))
