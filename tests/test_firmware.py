"""Private exact-original checks of the maintained USB composition, never a CMU."""

import json
import os
import re
import struct
import subprocess
import unittest
from pathlib import Path

from open_connect.elf import ELF

ROOT = Path(__file__).resolve().parents[1]
STUB, END, ALIGN = 0x6F79C, 0x70000, 0x8000


def branch_target(word, place):
    value = word & 0xFFFFFF
    if value & 0x800000:
        value -= 1 << 24
    return place + 8 + (value << 2)


class PrivateFirmware(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("OC_FIRMWARE_CHECK_DIR"):
            raise unittest.SkipTest("private originals required; run tests/check_firmware.py")
        cls.output = Path(os.environ["OC_FIRMWARE_CHECK_DIR"])
        cls.build = cls.output / "build"
        cls.composed = Path((cls.output / "composed-path").read_text().strip())
        cls.originals = cls.output / "compose/originals"
        cls.original = (cls.originals / "uia.so").read_bytes()
        cls.candidate = (cls.composed / "uia.so").read_bytes()
        cls.old, cls.new = ELF(cls.original), ELF(cls.candidate)
        cls.linked = ELF((cls.build / "patch.elf").read_bytes())
        cls.payload = (cls.build / "native.bin").read_bytes()

    def test_all_original_sections_symbols_addresses_and_segment_alignment(self):
        self.assertEqual(len(self.candidate), len(self.original) + ALIGN)
        header = list(self.old.h)
        header[6] += ALIGN
        self.assertEqual(tuple(header), self.new.h)
        self.assertEqual(self.old.names, self.new.names)
        self.assertEqual(self.old.symbols, self.new.symbols)
        site = self.linked.section(".branch")[1][3]
        branch = (self.build / "branch.bin").read_bytes()
        for name, old, new in zip(self.old.names, self.old.sections, self.new.sections):
            with self.subTest(section=name):
                expected = list(old)
                if old[4] >= STUB:
                    expected[4] += ALIGN
                if name == ".rodata":
                    expected[5] += len(self.payload)
                self.assertEqual(tuple(expected), new)
                if not name or old[1] == 8:
                    continue
                before = bytearray(self.original[old[4] : old[4] + old[5]])
                after = self.candidate[new[4] : new[4] + old[5]]
                if name == ".text":
                    at = site - old[3]
                    before[at : at + 4] = branch
                self.assertEqual(before, after)
        for index, (old, new) in enumerate(zip(self.old.programs, self.new.programs)):
            expected = list(old)
            if index == 0:
                self.assertEqual(old, (1, 0, 0, 0, STUB, STUB, 5, ALIGN))
                expected[4] = expected[5] = STUB + len(self.payload)
            elif old[1] >= STUB:
                expected[1] += ALIGN
            self.assertEqual(tuple(expected), new)
            if new[0] == 1:
                self.assertEqual(new[1] % new[7], new[2] % new[7])
        self.assertLessEqual(STUB + len(self.payload), END)
        self.assertEqual(self.new.virtual_data(STUB, len(self.payload)), self.payload)

    def test_intercept_is_in_ordinary_event_callback_and_pic_relocations(self):
        original = self.originals / "uia.so"
        text = subprocess.check_output(
            [os.environ["OC_OBJDUMP"], "-d", "-j", ".plt", original], text=True
        )
        labels = {
            match[2]: int(match[1], 16)
            for match in re.finditer(r"^([0-9a-f]+) <([^>]+)>:", text, re.M)
        }
        external = {
            "cmu_stock_process": labels["UIAHLP_ProcessContextEvent@plt"],
            "cmu_copy": labels["memcpy@plt"],
            "cmu_log_allowed": labels["COMMON_Log_Acceptable@plt"],
            "cmu_log_write": labels["COMMON_Log_Write@plt"],
            "cmu_focused_app": labels["UIAM_GetFocusedApp@plt"],
            "cmu_uia_handle": self.old.symbols["uiaSystemGetUiaMgrHandle"]["value"],
            "cmu_stop_service": self.old.symbols["MMUI_SM_CLIENT_StopService"]["value"],
            "cmu_image_base": 0,
        }
        blob, symbols, relocations = inspect_link(
            (self.build / "native.o").read_bytes(),
            (self.build / "patch.elf").read_bytes(),
            external,
        )
        self.assertEqual(blob, self.payload)
        site = self.linked.section(".branch")[1][3]
        callback = self.old.symbols["UIA_SYSTEM_EventCallback"]
        self.assertTrue(callback["value"] <= site < callback["value"] + callback["size"])
        old = struct.unpack("<I", self.old.virtual_data(site, 4))[0]
        new = struct.unpack("<I", self.new.virtual_data(site, 4))[0]
        self.assertEqual(branch_target(old, site), external["cmu_stock_process"])
        self.assertEqual(branch_target(new, site), symbols["cmu_native_process"])
        self.assertEqual(new >> 24, 0xEB)
        for relocation in relocations:
            place, target = relocation["place"], relocation["target"]
            old, new = relocation["old"], relocation["new"]
            self.assertEqual(struct.unpack("<I", self.new.virtual_data(place, 4))[0], new)
            for base in (0, 0x2B710000, 0x60000000):
                if relocation["kind"] in (28, 29):
                    self.assertEqual(branch_target(new, base + place), base + target)
                else:
                    self.assertEqual(
                        (new + base + place) & 0xFFFFFFFF, (target + base + old) & 0xFFFFFFFF
                    )
        (self.output / "relocations.json").write_text(json.dumps(relocations, indent=2) + "\n")

    def test_mmui_both_xml_consumers_and_only_planned_changes(self):
        old = (self.originals / "mmui.so").read_bytes()
        new = (self.composed / "mmui.so").read_bytes()
        path = b"/tmp/open-connect/feature/mmui.xml\0"
        allowed = set(range(0x3DC4, 0x3DC4 + len(path))) | set(range(68, 76))
        self.assertEqual(len(old), len(new))
        self.assertEqual(new[0x3DC4 : 0x3DC4 + len(path)], path)
        for length_at, pointer_at, pc in (
            (0x1BC8, 0x1CC8, 0x1BCC),
            (0x29C0, 0x30FC, 0x29C4),
        ):
            self.assertEqual(struct.unpack_from("<I", new, length_at)[0], 0xE3A02000 + len(path))
            pointer = struct.unpack_from("<I", new, pointer_at)[0]
            for base in (0, 0x2B710000, 0x60000000):
                self.assertEqual(base + pc + pointer, base + 0x3DC4)
            allowed.update(range(length_at, length_at + 4))
            allowed.update(range(pointer_at, pointer_at + 4))
        for index, (before, after) in enumerate(zip(old, new)):
            if before != after:
                self.assertIn(index, allowed)
        self.assertEqual(struct.unpack_from("<2I", new, 68), (0x3DC4 + len(path),) * 2)

    def test_both_board_profiles_and_original_startup_branch_are_preserved(self):
        for profile, name in (("normal", "sm.conf"), ("wcp", "sm_WCP.conf")):
            original = (self.originals / name).read_bytes()
            for setting in ("on", "off"):
                expected = original.replace(
                    b'args="-u /jci/gui/index.html"',
                    b'args="-u /tmp/open-connect/feature/index.html"',
                )
                if setting == "on":
                    expected = expected.replace(
                        b'name="jciMMUI" path="/jci/mmui/svcjcimmui.so"',
                        b'name="jciMMUI" path="/tmp/open-connect/feature/mmui.so"',
                    )
                self.assertEqual(
                    (self.composed / f"sm-{profile}-{setting}.conf").read_bytes(), expected
                )
        original = (self.originals / "autostart").read_bytes()
        hook = (ROOT / "cmu/installer/startup-hook.sh").read_bytes()
        join = (ROOT / "cmu/installer/startup-join.sh").read_bytes()
        anchor = b"        echo $MESSAGE_NORMALMODE\n"
        join_anchor = (
            b"                sleep 1\n                $(/jci/scripts/get_board_type.sh)\n"
        )
        self.assertEqual(original.count(anchor), 1)
        self.assertEqual(original.count(join_anchor), 1)
        self.assertEqual(
            (self.composed / "autostart").read_bytes(),
            original.replace(anchor, anchor + hook).replace(
                join_anchor,
                b"                sleep 1\n"
                + join
                + b"                $(/jci/scripts/get_board_type.sh)\n",
            ),
        )

    def test_renderer_insertion_is_the_only_edit_and_host_contract_passed(self):
        original = (self.originals / "system-app.js").read_bytes()
        candidate = (self.composed / "system-app.js").read_bytes()
        anchor = b'        "IntroAnimation" : {'
        at = original.index(anchor) + len(anchor)
        fragment = (ROOT / "cmu/installer/intro.js").read_bytes().replace(b"\n", b"\r\n")[:-2]
        self.assertEqual(candidate, original[:at] + fragment + original[at:])
        contract = (self.output / "host-contract.stdout").read_text()
        self.assertEqual(contract.count("PASS "), 4)
        self.assertIn("HOST MODEL ONLY", contract)


def inspect_link(obj, linked_image, external):
    """Check LLD's output against the object relocations; never link or emit code."""
    elf = ELF(obj)
    linked = ELF(linked_image)
    text_i, text = elf.section(".text")
    textdata = elf.section_data(".text")
    ro_i, ro = elf.section(".rodata.str1.1")
    roaddr = STUB + ((len(textdata) + 3) & ~3)
    locations = {text_i: STUB, ro_i: roaddr}
    unlinked = textdata + bytes(roaddr - STUB - len(textdata)) + elf.section_data(".rodata.str1.1")
    payload_i, payload = linked.section(".payload")
    blob = linked.section_data(".payload")
    if payload[3] != STUB or len(blob) != len(unlinked):
        raise ValueError("unexpected linked payload layout")
    if len(blob) > END - STUB:
        raise ValueError(f"compiled PIC stub {len(blob)} exceeds the verified RX address gap")
    for name, address in external.items():
        if linked.symbols.get(name, {}).get("value") != address:
            raise ValueError("linker map does not match verified OEM symbol " + name)
    symbols = {
        name: sym["value"] for name, sym in linked.symbols.items() if sym["section"] == payload_i
    }
    relocations = []
    for i, s in enumerate(elf.sections):
        if s[1] != 9:
            continue
        # .ARM.exidx is compiler cantunwind metadata, not injected executable/data.
        if s[7] not in locations:
            continue
        for at in range(s[4], s[4] + s[5], s[9]):
            offset, info = struct.unpack_from("<II", obj, at)
            kind = info & 255
            sym = elf.by_table[s[6]][info >> 8]
            if sym["section"] in locations:
                target = locations[sym["section"]] + sym["value"]
            elif sym["section"] == 0 and sym["name"] in external:
                target = external[sym["name"]]
            else:
                raise ValueError("unsupported/undefined symbol " + sym["name"])
            place = locations[s[7]] + offset
            index = place - STUB
            old = struct.unpack_from("<I", unlinked, index)[0]
            new = struct.unpack_from("<I", blob, index)[0]
            if kind in (28, 29):
                if (kind == 28 and old >> 24 != 0xEB) or (kind == 29 and old >> 24 != 0xEA):
                    raise ValueError("unexpected compiler ARM branch relocation form")
                # REL addend is encoded in instruction; compiler's unresolved branch is -8.
                addend = branch_target(old, 0) - 8
                delta = target + addend - place
                if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
                    raise ValueError("relocation branch range")
                if new >> 24 != old >> 24 or branch_target(new, place) != target + addend + 8:
                    raise ValueError("LLD ARM branch does not resolve to the expected symbol")
            elif (
                kind == 3
            ):  # R_ARM_REL32 S+A-P; runtime load base cancels for PC-relative references.
                if (new + place) & 0xFFFFFFFF != (target + old) & 0xFFFFFFFF:
                    raise ValueError("LLD REL32 does not resolve to the expected symbol")
            else:
                raise ValueError("unsupported relocation " + str(kind))
            relocations.append(
                dict(place=place, kind=kind, symbol=sym["name"], target=target, old=old, new=new)
            )
    return blob, symbols, relocations
