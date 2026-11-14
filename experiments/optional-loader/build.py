"""Build an uninstalled FW55 MMUI loader probe from an explicit private original."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location(
    "_oc_native_elf", HERE.parent / "disclaimer-native/build.py"
)
elf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(elf)
BASE_SHA = "2c2c0494817b13a38c36a8276a39899b4096efc217e82568fe3842f8b34bb025"
SITE, START, LIMIT = 0x31AC, 0x3F38, 0x4000
EXTERNAL = {"oc_dlopen": 0x10FC, "oc_dlsym": 0xF94}
SOURCE = ROOT / "cmu/adapters/fw55/mmui-loader.S"


def link(obj):
    parsed = elf.ELF(obj)
    text_i, _ = parsed.section(".text")
    blob = bytearray(parsed.section_data(".text"))
    if not blob or len(blob) > LIMIT - START:
        raise ValueError("stub exceeds the verified RX gap")
    entry = parsed.symbols["oc_mmui_load"]
    if entry["section"] != text_i or entry["value"] != 0:
        raise ValueError("unexpected entry layout")
    relocs = []
    for section in parsed.sections:
        if section[1] != 9:
            continue
        if section[7] != text_i:
            raise ValueError("unexpected relocation section")
        for pos in range(section[4], section[4] + section[5], section[9]):
            offset, info = struct.unpack_from("<II", obj, pos)
            symbol = parsed.by_table[section[6]][info >> 8]
            if info & 255 != 28 or symbol["section"] != 0 or symbol["name"] not in EXTERNAL:
                raise ValueError("unexpected relocation")
            old = struct.unpack_from("<I", blob, offset)[0]
            if old != 0xEBFFFFFE:
                raise ValueError("unexpected ARM call addend")
            place, target = START + offset, EXTERNAL[symbol["name"]]
            word = elf.branch_word(old, place, target)
            struct.pack_into("<I", blob, offset, word)
            relocs.append(dict(place=place, target=target, symbol=symbol["name"]))
    if sorted(r["symbol"] for r in relocs) != sorted(EXTERNAL):
        raise ValueError("expected exactly two loader calls")
    return bytes(blob), relocs


def patch(original, obj):
    if len(original) != 22952 or hashlib.sha256(original).hexdigest() != BASE_SHA:
        raise ValueError("unsupported exact svcjcimmui.so; no fuzzy patch")
    parsed = elf.ELF(original)
    ph = struct.unpack_from("<8I", original, parsed.h[5])
    if ph != (1, 0, 0, 0, START, START, 5, 0x8000):
        raise ValueError("unexpected RX segment")
    if original[START:LIMIT] != bytes(LIMIT - START):
        raise ValueError("nonempty segment gap")
    if original[SITE:SITE+4] != struct.pack("<I", 0xE3A00000):
        raise ValueError("unexpected original return instruction")
    blob, relocs = link(obj)
    candidate = bytearray(original)
    candidate[START:START+len(blob)] = blob
    struct.pack_into("<I", candidate, SITE, elf.branch_word(0xEB000000, SITE, START))
    for offset in (16, 20):
        struct.pack_into("<I", candidate, parsed.h[5] + offset, START + len(blob))
    allowed = set(range(START, START+len(blob))) | set(range(SITE, SITE+4))
    for offset in (16, 20):
        allowed.update(range(parsed.h[5]+offset, parsed.h[5]+offset+4))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(original, candidate))):
        raise ValueError("unexpected change outside hook and RX length fields")
    return bytes(candidate), relocs


def compile_stub(clang, output, library_path=None):
    options = []
    if library_path is not None:
        if not library_path.startswith("/") or any(c in library_path for c in "\n\r\0"):
            raise ValueError("absolute library path required")
        options = ["-DOC_BOOTSTRAP_PATH=" + json.dumps(library_path)]
    subprocess.run([
        clang, "--target=armv7-none-eabi", "-march=armv7-a", "-marm",
        "-mfloat-abi=hard", "-mfpu=vfpv3", *options, "-c", str(SOURCE), "-o", str(output),
    ], check=True, capture_output=True)
    return output.read_bytes()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--clang")
    args = p.parse_args()
    out = elf.private_output(args.output)
    original = args.original.read_bytes()
    if hashlib.sha256(original).hexdigest() != BASE_SHA:
        p.error("unsupported original")
    clang = elf.tool("clang", args.clang)
    out.mkdir(parents=True, mode=0o700)
    obj = compile_stub(clang, out / "loader.o")
    candidate, relocs = patch(original, obj)
    (out / "candidate.bin").write_bytes(candidate)
    (out / "loader.S").write_bytes(SOURCE.read_bytes())
    result = dict(
        status="HOST_ONLY_UNINSTALLED", live_authority=False,
        target="/jci/mmui/svcjcimmui.so", firmware="55.00.750B/cmu150_NA",
        original_sha256=BASE_SHA, candidate_sha256=hashlib.sha256(candidate).hexdigest(),
        bytes=len(candidate), stub_bytes=len(link(obj)[0]), call_site=SITE,
        relocations=relocs, source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (SOURCE, Path(__file__), HERE/"noop.c", HERE/"test_loader.py")},
        compiler=dict(path=clang,version=subprocess.check_output([clang,"--version"],text=True)) ,
        limits=["no ARM execution or device proof", "no optional-feature control yet",
                "bootstrap failure is not caught; original restoration still required"],
    )
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
