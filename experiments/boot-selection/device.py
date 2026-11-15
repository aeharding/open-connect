"""Prepare one checked feature generation and independent undo. No reboot here."""

import argparse, json, sys, subprocess, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/mapped-publication"))
import linked, trial
from bench import rt

# Set only by the explicit CLI entry point; importing performs no operations.
R = F = P = D = OWNER = None
TARGET = "/usr/bin/autostart"


import runpy

delivery = runpy.run_path(str(ROOT / "experiments/staged-delivery/deliver.py"))


def guard(s, variable="q"):
    delivery["descriptor"](s)
    v = "$" + variable
    directory = s["path"].rsplit("/", 1)[0]
    return f'''{variable}={s["path"]}
test -d {directory} && test ! -L {directory} && test "$(readlink -f {directory})" = {directory} || exit 70
test "$(stat -c '%d:%i:%Y:%a:%u:%g:%h' {directory})" = '{s["dir_id"]}' || exit 71
test -f "{v}" && test ! -L "{v}" && test "$(readlink -f "{v}")" = "{v}" || exit 72
test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "{v}")" = '{s["file_id"]}' || exit 73
test "$(md5sum < "{v}")" = '{s["md5"]}  -' || exit 74
test "$(cksum < "{v}")" = '{s["cksum"]} {s["bytes"]}' || exit 75
'''


def save(name, value):
    (R / name).write_text(json.dumps(value, indent=2) + "\n")


def one(raw, prefix):
    rows = rt.typed_records(raw, prefix)
    if len(rows) != 1:
        raise ValueError("unique " + repr(prefix))
    return rows[0]


def command(script, name):
    b = R / name
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "open_connect",
            "uart",
            "--live",
            "--action",
            "command",
            "--command",
            script,
            "--owner",
            OWNER,
            "--solicit-prompt",
            "--deadline",
            "60",
            "--output-cap",
            "262144",
            "--bundle",
            str(b),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    (R / (name.replace("/", "-") + ".host.txt")).write_text(run.stdout + run.stderr)
    run.check_returncode()
    m = json.loads((b / "manifest.json").read_text())
    op = m["operations"][-1]
    assert op["exit_status"] == 0 and m["port_closed"]
    return (b / (op["nonce"] + ".output.bin")).read_bytes()


def stage(file, name):
    b = R / name
    run = subprocess.run(
        [
            sys.executable,
            "experiments/staged-delivery/deliver.py",
            "stage",
            "--source",
            str(file),
            "--live",
            "--owner",
            OWNER,
            "--solicit-prompt",
            "--bundle",
            str(b),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    (R / (name + ".host.txt")).write_text(run.stdout + run.stderr)
    run.check_returncode()
    return json.loads((b / "stage.json").read_text())


def entry(mode):
    return trial.bound_entry(
        json.loads((R / "publication.json").read_text()),
        json.loads((R / "code.json").read_text()),
        mode,
    )


SOURCE_PINS = {}


def source_commands():
    commands = []
    for path, digest in SOURCE_PINS.items():
        commands.append(f"""test -f {path} && test ! -L {path} && test "$(readlink -f {path})" = {path} || exit 85
test "$(md5sum < {path})" = '{digest}  -' || exit 86
v=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' {path}) || exit 87
printf 'OCGEN_SOURCE|%s|%s\\n' {path} "$v"
""")
    return commands


def source_checks():
    return "".join(source_commands())


def prepare():
    o = P["artifacts"]["autostart.original"]
    c = P["artifacts"]["autostart.candidate"]
    raw = command(
        source_checks()
        + f"""p={TARGET}
 for d in /usr /usr/bin;do
  test -d "$d" && test ! -L "$d" && test "$(readlink -f "$d")" = "$d" || exit 70
  v=$(stat -c '%d:%i:%a:%u:%g' "$d") || exit 71
  printf 'OCSEL_PARENT|%s|%s\\n' "$d" "$v"
 done
 test -f "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 72
 test "$(stat -c '%Y:%s:%a:%u:%g:%h' "$p")" = 1380015098:3039:775:1018:3015:1 || exit 73
 test "$(md5sum < "$p")" = '{o["md5"]}  -' || exit 74
 test "$(cksum < "$p")" = '{o["crc"]} {o["bytes"]}' || exit 75
 v=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p") || exit 76
 printf 'OCSEL_ID|%s\\n' "$v"
 test "$(md5sum < /jci/sm/sm.conf)" = '{P["original_config"]["md5"]}  -' || exit 77
 awk '$1=="/dev/ffx01p1"&&$2=="/"&&$3=="relfs"{{n++;m=$4}}END{{exit !(n==1&&m=="ro,noatime")}}' /proc/mounts || exit 78
 """,
        "baseline",
    )
    oid = one(raw, b"OCSEL_ID|")
    save(
        "source-identities.json",
        dict(v.split("|", 1) for v in rt.typed_records(raw, b"OCGEN_SOURCE|")),
    )
    parents = dict(v.split("|") for v in rt.typed_records(raw, b"OCSEL_PARENT|"))
    assert len(parents) == 2
    prefix = "/usr/bin/.autostart.oc-" + D.rsplit("-", 1)[1]
    pub = dict(
        target=TARGET,
        directory=D,
        oid=oid.rsplit(":", 1)[0],
        parents=parents,
        hold_o=prefix + "-O",
        hold_c=prefix + "-C",
        stage=prefix + "-stage",
        original=o,
        candidate=c,
    )
    body = linked.render(
        TARGET, D, pub["hold_o"], pub["hold_c"], pub["stage"], pub["oid"], parents, o, c
    )
    # Reuse the tested transaction; autostart uses OEM mode775 and is a shell script.
    assert body.count("$n:755:1018:3015") == 1
    body = body.replace("$n:755:1018:3015", "$n:775:1018:3015")
    start = body.index("  pid=$(pgrep")
    end = body.index("  begin_write", start)
    body = body[:start] + body[end:]  # no native-MMUI positive original mapping assertion
    subprocess.run(["/bin/sh", "-n"], input=body.encode(), check=True)
    pub["body"] = rt.fp(body.encode())
    save("publication.json", pub)
    (R / "recovery.sh").write_text(body)
    stages = {}
    for key, file in [
        ("selector", F / "select.sh"),
        ("flush", F / "flush"),
        ("candidate", F / "autostart.candidate"),
        ("recovery", R / "recovery.sh"),
    ]:
        stages[key] = stage(file, key + "-stage")
    chunks = {}
    for name in (
        "generation.conf",
        "mmui.so",
        "mmui.xml",
        "index.html",
        "system-app.js",
        "ready-receiver",
        "ready-watch.sh",
    ):
        data = (F / name).read_bytes()
        keys = []
        for offset in range(0, len(data), 16384):
            key = name.replace(".", "_").replace("-", "_") + "_" + str(offset // 16384)
            part = R / (key + ".part")
            part.write_bytes(data[offset : offset + 16384])
            stages[key] = stage(part, key + "-stage")
            keys.append(key)
        chunks[name] = keys
    stages["native_delta"] = stage(
        Path(P["feature_pair"]) / "native/candidate/delta-blocks.bin", "native-delta-stage"
    )
    save("chunks.json", chunks)

    save("deliveries.json", stages)
    prep = "set -fu\numask 077\n"
    prep += """delivery_guard() {
 gx=$1;gd=${gx%/*}
 test -d "$gd" && test ! -L "$gd" && test "$(readlink -f "$gd")" = "$gd" || exit 70
 test "$(stat -c '%d:%i:%Y:%a:%u:%g:%h' "$gd")" = "$2" || exit 71
 test -f "$gx" && test ! -L "$gx" && test "$(readlink -f "$gx")" = "$gx" || exit 72
 test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$gx")" = "$3" || exit 73
 test "$(md5sum < "$gx")" = "$4  -" || exit 74
 test "$(cksum < "$gx")" = "$5 $6" || exit 75
}
"""
    for key, desc in stages.items():
        delivery["descriptor"](desc)
        prep += f"delivery_guard {desc['path']} {desc['dir_id']} {desc['file_id']} {desc['md5']} {desc['cksum']} {desc['bytes']}\n"
        prep += key + "=" + desc["path"] + "\n"
    prep += "source_guard() {\n" + source_checks() + "}\nsource_guard\n"

    prep += f"""d={D};p={TARGET}
for q in /tmp /tmp/mnt /tmp/mnt/data_persist;do
 test -d "$q" && test ! -L "$q" && test "$(readlink -f "$q")" = "$q" || exit 80
done
test "$(stat -c '%a:%u:%g:%d' /tmp/mnt/data_persist)" = 755:0:0:45826 || exit 81
awk '$1=="/dev/mmcblk0p2"&&$2=="/tmp/mnt/data_persist"&&$3=="relfs"{{n++;split($4,a,",");for(i in a)if(a[i]=="rw")rw++}}END{{exit !(n==1&&rw==1)}}' /proc/mounts || exit 82
test ! -e "$d" && test ! -L "$d" || exit 83
test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p")" = '{oid}' || exit 84
test "$(md5sum < "$p")" = '{o["md5"]}  -' || exit 85
test "$(md5sum < /jci/sm/sm.conf)" = '{P["original_config"]["md5"]}  -' || exit 86
mkdir -m 700 "$d" || exit 87
cp -p "$p" "$d/original" || exit 88
cp "$candidate" "$d/candidate" && chmod 775 "$d/candidate" && chown 1018:3015 "$d/candidate" || exit 89
cp "$selector" "$d/select.sh" && chmod 600 "$d/select.sh" || exit 90
cp "$flush" "$d/flush" && chmod 700 "$d/flush" || exit 91
cp "$recovery" "$d/recovery.sh" && chmod 600 "$d/recovery.sh" || exit 92
printf 'OC_TRIAL_1|{D.rsplit("-", 1)[1]}\\n' > "$d/armed" || exit 94
printf 'prepared|none\\n' > "$d/state" || exit 95
"""
    for name, keys in json.loads((R / "chunks.json").read_text()).items():
        args = " ".join('"$' + key + '"' for key in keys)
        prep += f'cat {args} > "$d/{name}" && chmod 600 "$d/{name}" || exit 93\n'
    profile = json.loads((Path(P["feature_pair"]) / "native/candidate/profile.json").read_text())
    prep += "(\n"
    for part in profile["reconstruction"]:
        if part["kind"] == "delta_block":
            prep += f'dd if="$native_delta" bs=4096 skip={part["index"]} count=1 || exit 93\n'
        else:
            prep += f"dd if=/jci/mmui/uia/libjciuiasystem.so bs=4096 skip={part['skip']} count={part['count']} || exit 93\n"
    prep += ') > "$d/uia.so" || exit 93\nchmod 600 "$d/uia.so" || exit 93\n'
    for name, key in [
        ("original", "autostart.original"),
        ("candidate", "autostart.candidate"),
        ("select.sh", "select.sh"),
        ("flush", "flush"),
        ("armed", "armed"),
    ] + [(n, n) for n in ("generation.conf", *P["dependencies"])]:
        f = P["artifacts"][key]
        prep += f"""test "$(md5sum < "$d/{name}")" = '{f["md5"]}  -' || exit 96
test "$(cksum < "$d/{name}")" = '{f["crc"]} {f["bytes"]}' || exit 97
timeout -t 8 "$d/flush" f "$d/{name}" || exit 98
"""
    prep += f"""test "$(md5sum < "$d/recovery.sh")" = '{pub["body"]["md5"]}  -' || exit 99
test "$(cksum < "$d/recovery.sh")" = '{pub["body"]["crc"]} {pub["body"]["bytes"]}' || exit 100
timeout -t 8 "$d/flush" f "$d/recovery.sh" || exit 101
timeout -t 8 "$d/flush" f "$d/state" || exit 102
timeout -t 8 "$d/flush" d "$d" || exit 103
v=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$d/recovery.sh") || exit 104
printf 'OCSEL_CODE|%s\\n' "$v"
v=$(stat -c '%d:%i:%a:%u:%g' "$d") || exit 105
printf 'OCSEL_DIR|%s\\n' "$v"
"""
    prep += "source_guard\n"
    (R / "prepare.sh").write_text(prep)
    assert len(prep.encode()) <= 16384, len(prep.encode())
    desc = stage(R / "prepare.sh", "prepare-stage")
    out = command(guard(desc) + '\n/bin/sh "$q" </dev/null', "prepare")
    ident = one(out, b"OCSEL_CODE|")
    rt.code_identity(ident, body.encode())
    save("code.json", dict(identity=ident, directory=one(out, b"OCSEL_DIR|")))
    command(entry("VERIFY"), "ready-verify")
    for key, s in dict(stages, prepare=desc).items():
        command(delivery["cleanup_command"](s), key + "-delivery-clean")
    artifact_ids = command(
        f"""d={D}
for n in generation.conf mmui.so mmui.xml index.html system-app.js uia.so ready-receiver ready-watch.sh;do
 v=$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$d/$n") || exit 90
 printf 'OCGEN_FILE|%s|%s\\n' "$n" "$v"
done
""",
        "artifact-identities",
    )
    save(
        "artifact-identities.json",
        dict(v.split("|", 1) for v in rt.typed_records(artifact_ids, b"OCGEN_FILE|")),
    )
    print("Ready: complete generation and independent undo; no root publication.")


def action(mode, name):
    out = command(entry(mode), name)
    rows = rt.typed_records(out, b"OCLINK|")
    save(name + ".json", dict(mode=mode, rows=rows))
    print("\n".join(rows))


def configure(args):
    global R, F, P, D, OWNER, SOURCE_PINS
    from open_connect.feature import inspect_build, compatible_sources, private_output

    build = args.build.resolve()
    inspect_build(build)
    record = json.loads((build / "build.json").read_text())
    if record["workspace"] != str(ROOT) or not compatible_sources(ROOT, record["source_sha256"]):
        raise ValueError("payload producer changed; rebuild before device preparation")
    F = build / "payload"
    P = json.loads((F / "plan.json").read_text())
    D = P["directory"]
    from feature import directory_guard

    directory_guard(D)
    OWNER = args.owner
    R = private_output(ROOT, args.state)
    inputs = record["inputs"]
    for item in inputs.values():
        if hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("original build input changed")
    SOURCE_PINS = {
        "/jci/sm/sm.conf": P["original_config"]["md5"],
        "/jci/mmui/svcjcimmui.so": hashlib.md5(
            Path(inputs["plugin"]["path"]).read_bytes()
        ).hexdigest(),
        "/jci/mmui/mmui_config.xml": hashlib.md5(
            Path(inputs["mmui_xml"]["path"]).read_bytes()
        ).hexdigest(),
        "/jci/mmui/uia/libjciuiasystem.so": "b9ff5edc632163f88cda04686c118591",
        "/jci/lib/libjciuiamgr.so": "8ce49f8bc9833c48a3a89e5c4c683ddc",
        "/jci/gui/framework/js/GuiFramework.js": "e90530cdb9b05922bdcaade8757ea1f9",
        "/jci/gui/index.html": hashlib.md5(Path(inputs["index"]["path"]).read_bytes()).hexdigest(),
    }
    # Existing baseline JS is never overwritten. An explicit private file can bind
    # an already-modified bench; absent that, require the original supplied to build.
    baseline = args.baseline_system_app or Path(inputs["system_app"]["path"])
    SOURCE_PINS["/jci/gui/apps/system/js/systemApp.js"] = hashlib.md5(
        baseline.read_bytes()
    ).hexdigest()
    return record


def unique_pairs(raw, prefix):
    rows = rt.typed_records(raw, prefix)
    pairs = [x.split("|", 1) for x in rows]
    if any(len(x) != 2 for x in pairs) or len({x[0] for x in pairs}) != len(pairs):
        raise ValueError("duplicate or malformed records")
    return dict(pairs)


def load_existing(state, owner):
    global R, D, OWNER, SOURCE_PINS, F, P
    import re
    from feature import directory_guard

    R = state.resolve()
    OWNER = owner
    if not R.is_relative_to(ROOT / "runs") or R == ROOT / "runs":
        raise ValueError("private trial state required")
    run = json.loads((R / "run.json").read_text())
    D = run["directory"]
    directory_guard(D)
    SOURCE_PINS = run["source_pins"]
    expected = {
        "/jci/sm/sm.conf",
        "/jci/mmui/svcjcimmui.so",
        "/jci/mmui/mmui_config.xml",
        "/jci/mmui/uia/libjciuiasystem.so",
        "/jci/lib/libjciuiamgr.so",
        "/jci/gui/framework/js/GuiFramework.js",
        "/jci/gui/index.html",
        "/jci/gui/apps/system/js/systemApp.js",
    }
    if set(SOURCE_PINS) != expected or any(
        not re.fullmatch("[0-9a-f]{32}", v) for v in SOURCE_PINS.values()
    ):
        raise ValueError("invalid source binding")
    pub = json.loads((R / "publication.json").read_text())
    code = json.loads((R / "code.json").read_text())
    prefix = "/usr/bin/.autostart.oc-" + D.rsplit("-", 1)[1]
    if (
        pub["target"] != TARGET
        or pub["directory"] != D
        or any(
            pub[k] != prefix + s
            for k, s in (("hold_o", "-O"), ("hold_c", "-C"), ("stage", "-stage"))
        )
    ):
        raise ValueError("publication path binding")
    if not re.fullmatch(r"[0-9]+(?::[0-9]+){7}", code["identity"]) or not re.fullmatch(
        r"[0-9]+(?::[0-9]+){4}", code["directory"]
    ):
        raise ValueError("persistent code binding")
    body = (R / "recovery.sh").read_bytes()
    if rt.fp(body) != pub["body"]:
        raise ValueError("local recovery body changed")
    rt.code_identity(code["identity"], body)
    F = Path(run["payload"])
    P = None
    return run


def status_commands(check_artifacts=True):
    run = json.loads((R / "run.json").read_text())
    files = json.loads((R / "artifact-identities.json").read_text())
    guards = []
    import re

    required = {
        "generation.conf",
        "mmui.so",
        "mmui.xml",
        "index.html",
        "system-app.js",
        "uia.so",
        "ready-receiver",
        "ready-watch.sh",
    }
    if set(files) != required:
        raise ValueError("prepared file identities")
    for name in sorted(files) if check_artifacts else ():
        identity = files[name]
        fp = run["artifacts"][name]
        if not re.fullmatch(r"[0-9]+(?::[0-9]+){7}", identity) or not re.fullmatch(
            "[0-9a-f]{32}", fp["md5"]
        ):
            raise ValueError("artifact binding")
        if any(type(fp[k]) is not int or fp[k] < 0 for k in ("crc", "bytes")):
            raise ValueError("artifact size/checksum")
        guards.append(f"""p={D}/{name}
test -f "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 85
test "$(stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p")" = '{identity}' || exit 86
test "$(md5sum < "$p")" = '{fp["md5"]}  -' || exit 87
test "$(cksum < "$p")" = '{fp["crc"]} {fp["bytes"]}' || exit 88
""")
    armed = run["artifacts"]["armed"]
    if not re.fullmatch("[0-9a-f]{32}", armed["md5"]) or any(
        type(armed[k]) is not int or armed[k] < 0 for k in ("crc", "bytes")
    ):
        raise ValueError("armed fingerprint")
    runtime = f'''
emit() {{ printf 'OCSTATE|%s|%s\\n' "$1" "$2"; }}
emit BOOT "$(cat /proc/sys/kernel/random/boot_id)"
emit UPTIME "$(cat /proc/uptime)"
v=invalid
if test ! -e {D}/select.lock && test ! -L {D}/select.lock;then
 for kind in armed spent;do
  other=spent;test "$kind" = spent && other=armed
  p={D}/$kind
  if test -f "$p" && test ! -L "$p" &&
     test ! -e {D}/$other && test ! -L {D}/$other &&
     test "$(stat -c '%a:%u:%g:%h' "$p")" = 600:0:0:1 &&
     test "$(md5sum < "$p")" = '{armed["md5"]}  -' &&
     test "$(cksum < "$p")" = '{armed["crc"]} {armed["bytes"]}';then
   v=$kind
  fi
 done
fi
emit SELECTOR "$v"
for label in SM MMUI OPERA;do
 case "$label" in
 SM) pattern='^/jci/sm/sm -f ';;
 MMUI) pattern='[/]jci/sm/sm_svclauncher -l jciMMUI ';;
 OPERA) pattern='^/jci/opera/opera -u ';;
 esac
 p=$(pgrep -f "$pattern") || p=
 case "$p" in ''|*[!0-9]*) v=unavailable;;
 *) v=$(tr '\\000' '|' < /proc/$p/cmdline) || exit 80;;
 esac
 emit "$label" "$v"
 if test "$label" = MMUI;then
  case "$p" in ''|*[!0-9]*) v=unavailable;;
  *) v=$(awk '$6=="/jci/mmui/uia/libjciuiasystem.so"||$6=="{D}/uia.so"{{if(NF!=6)bad++;if(n&&($5!=i||$6!=p))bad++;n++;i=$5;p=$6;if($2~/x/)x++}}END{{if(!n||bad)printf "unavailable";else printf "%d:%s:%s:%d",n,i,p,x}}' /proc/$p/maps) || exit 81;;
  esac
  emit NATIVE_MAP "$v"
 fi
done
w=/tmp/oc-health-{D.rsplit("-", 1)[1]}
v=absent
if test -f "$w/result" && test ! -L "$w/result";then v=$(cat "$w/result");fi
emit HEALTH "$v"
v=absent
if test -f "$w/boot" && test ! -L "$w/boot";then v=$(cat "$w/boot");fi
emit HEALTH_BOOT "$v"
'''
    return [entry("VERIFY"), *source_commands(), *guards, runtime]


def status_script(check_artifacts=True):
    return "\n".join(status_commands(check_artifacts))


def parse_status(status, raw):
    import re

    if status:
        raise ValueError("fresh verification failed")
    values = unique_pairs(raw, b"OCSTATE|")
    if set(values) != {
        "BOOT",
        "UPTIME",
        "SM",
        "MMUI",
        "OPERA",
        "NATIVE_MAP",
        "HEALTH",
        "HEALTH_BOOT",
        "SELECTOR",
    }:
        raise ValueError("missing runtime state")
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", values["BOOT"]):
        raise ValueError("boot identity")
    if not re.fullmatch(r"[0-9]+\.[0-9]+ [0-9]+\.[0-9]+", values["UPTIME"]):
        raise ValueError("uptime")
    observed = unique_pairs(raw, b"OCGEN_SOURCE|")
    expected = json.loads((R / "source-identities.json").read_text())
    if observed != expected:
        raise ValueError("installed source identity changed")
    rows = rt.typed_records(raw, b"OCLINK|")
    if len(rows) != 1:
        raise ValueError("one independent VERIFY result required")
    fields = rows[0].split("|")
    if (
        len(fields) != 6
        or fields[0] != "VERIFY"
        or fields[1] not in ("O", "C")
        or fields[-2:] != ["ro,noatime", "writes=0"]
    ):
        raise ValueError("independent VERIFY result")
    values.update(
        installed_hook=fields[1] == "C",
        hook_identity=fields[3],
        publication_phase=fields[2],
        loaded="unknown",
        root="ro,noatime",
    )
    baseline = json.loads((R / "runtime-baseline.json").read_text())
    files = json.loads((R / "artifact-identities.json").read_text())
    for selected in (False, True):
        config = D + "/generation.conf" if selected else "/jci/sm/sm.conf"
        plugin = D + "/mmui.so" if selected else "/jci/mmui/svcjcimmui.so"
        index = D + "/index.html" if selected else "/jci/gui/index.html"
        native = D + "/uia.so" if selected else "/jci/mmui/uia/libjciuiasystem.so"
        identity = files["uia.so"] if selected else expected[native]
        maps = values["NATIVE_MAP"].split(":")
        mapped = (
            len(maps) == 4
            and maps[0].isdigit()
            and int(maps[0]) > 0
            and maps[1] == identity.split(":")[1]
            and maps[2] == native
            and maps[3] == "1"
        )
        if (
            values["SM"] == "/jci/sm/sm|-f|" + config + "|-e|/tmp/smevents.txt|"
            and values["MMUI"] == baseline["MMUI"].replace("/jci/mmui/svcjcimmui.so", plugin)
            and values["OPERA"] == baseline["OPERA"].replace("/jci/gui/index.html", index)
            and mapped
        ):
            values["loaded"] = "selected" if selected else "baseline"
    values["home_acknowledged"] = (
        values["loaded"] == "selected"
        and values["HEALTH"] == "ready|0"
        and values["HEALTH_BOOT"] == values["BOOT"]
    )
    return values


def runtime_baseline():
    raw = command(
        """set -fu
mm=$(pgrep -f '[/]jci/sm/sm_svclauncher -l jciMMUI ') || exit 90
op=$(pgrep -f '^/jci/opera/opera -u ') || exit 91
case "$mm:$op" in *[!0-9:]*|:*)exit 92;;esac
test "$(readlink -f /proc/$mm/exe)" = /jci/sm/sm_svclauncher || exit 93
test "$(readlink -f /proc/$op/exe)" = /jci/opera/opera || exit 94
printf 'OCRUNTIME|MMUI|%s\\n' "$(tr '\\000' '|' < /proc/$mm/cmdline)"
printf 'OCRUNTIME|OPERA|%s\\n' "$(tr '\\000' '|' < /proc/$op/cmdline)"
""",
        "runtime-baseline",
    )
    values = unique_pairs(raw, b"OCRUNTIME|")
    if (
        set(values) != {"MMUI", "OPERA"}
        or values["OPERA"] != "/jci/opera/opera|-u|/jci/gui/index.html|"
        or "/jci/mmui/svcjcimmui.so|" not in values["MMUI"]
    ):
        raise ValueError("baseline launch paths required")
    save("runtime-baseline.json", values)


def resources(name):
    # Raw paired points are retained with uptime. They are not a speedup claim.
    return command(
        """set -fu
for sample in 1 2;do
 echo "OCRESOURCE|SAMPLE|$sample"
 cat /proc/uptime /proc/sys/kernel/random/boot_id
 cat /proc/meminfo
 head -n 1 /proc/stat
 for pattern in '^/jci/opera/opera -u ' '[/]jci/sm/sm_svclauncher -l jciMMUI ';do
  p=$(pgrep -f "$pattern") || exit 90
  case "$p" in ''|*[!0-9]*)exit 91;;esac
  echo "OCRESOURCE|PID|$p"
  cat /proc/$p/stat
  awk '/^(Name|VmSize|VmRSS|Threads):/{print}' /proc/$p/status
  if test -r /proc/$p/io;then cat /proc/$p/io;fi
 done
 if test "$sample" = 1;then sleep 1;fi
done
""",
        name,
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", required=True, type=Path)
    p.add_argument("--state", required=True, type=Path)
    p.add_argument("--owner", required=True)
    p.add_argument("--baseline-system-app", type=Path)
    a = p.parse_args(argv)
    record = configure(a)
    R.mkdir(mode=0o700, parents=True, exist_ok=False)
    save(
        "run.json",
        dict(
            workspace=str(ROOT),
            build=str(a.build.resolve()),
            payload=str(F),
            directory=D,
            source_pins=SOURCE_PINS,
            source_sha256=record["source_sha256"],
            phase="preparing",
            owner=OWNER,
            watch=P["artifacts"]["ready-watch.sh"],
            artifacts=P["artifacts"],
            baseline="as-found; existing JS explicitly bound",
        ),
    )
    try:
        prepare()
        runtime_baseline()
        run = json.loads((R / "run.json").read_text())
        run["phase"] = "prepared"
        save("run.json", run)
    except BaseException as exc:
        run = json.loads((R / "run.json").read_text())
        run.update(phase="preparation_incomplete", error=type(exc).__name__ + ": " + str(exc))
        save("run.json", run)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
