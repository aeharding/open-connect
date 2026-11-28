"""Sparse UI selection preserves native IDs and Base-off OEM loading."""

import itertools
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


class UIProfile(unittest.TestCase):
    def test_choice_matrix_preserves_ids_and_retained_xml(self):
        original = (ROOT / "tests/fixtures/ui-profile.xml").read_bytes()
        stock = {n.get("name"): n.attrib for n in ET.fromstring(original)}
        groups = {}
        plugins = []
        for row in (ASSETS / "ui-modules.tsv").read_text().splitlines():
            if row.startswith("#"):
                continue
            kind, name, group, _ = row.split("\t")
            if kind == "uia":
                groups[name] = group
            else:
                plugins.append((name, group))
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config"
            for base, warning, aa, pandora, sxm in itertools.product((0, 1), repeat=5):
                with self.subTest(base=base, warning=warning, aa=aa, pandora=pandora, sxm=sxm):
                    choices = {
                        "base": base,
                        "warning": warning,
                        "service.android-auto": aa,
                        "service.pandora": pandora,
                        "service.siriusxm": sxm,
                    }
                    values = dict(
                        choices,
                        metadata="755:0:0",
                        nvram="disable",
                        package="a" * 64,
                        touch=1,
                        wireless=1,
                        **{"service-ids": "android-auto,pandora,siriusxm"},
                    )
                    config.write_text(
                        "OC2\n" + "".join(f"{k}={v}\n" for k, v in sorted(values.items()))
                    )

                    def render(mode):
                        return subprocess.check_output(
                            [
                                "awk",
                                "-v",
                                "operation=compose",
                                "-v",
                                "ui_mode=" + mode,
                                "-v",
                                "modules=" + str(ASSETS / "ui-modules.tsv"),
                                "-v",
                                "catalog=" + str(ASSETS / "services.tsv"),
                                "-v",
                                "catalog_bytes=" + str((ASSETS / "services.tsv").stat().st_size),
                                "-v",
                                "input=" + str(config),
                                "-v",
                                "input_bytes=" + str(config.stat().st_size),
                                "-f",
                                ASSETS / "preferences.awk",
                                "-f",
                                ASSETS / "ui-profile.awk",
                                ROOT / "tests/fixtures/ui-profile.xml",
                            ],
                            timeout=5,
                        )

                    def enabled(group):
                        return (
                            not base
                            or group == "keep"
                            or (group != "base" and choices["service." + group])
                        )

                    xml = render("mmui")
                    nodes = {n.get("name"): n.attrib for n in ET.fromstring(xml)}
                    self.assertEqual(set(nodes), {name for name in stock if enabled(groups[name])})
                    for name, attributes in nodes.items():
                        expected = dict(stock[name])
                        if name == "system" and warning:
                            expected.update(libpath="/tmp/open-connect/feature/", lib="uia.so")
                        self.assertEqual(attributes, expected)
                    names = render("plugins").decode().splitlines()
                    self.assertEqual(names, [n for n, g in plugins if base and enabled(g)])
                    if not base and not warning:
                        self.assertEqual(xml, original)  # Includes Base=0/AA=0.
                    if base:
                        self.assertGreaterEqual(len(nodes), 33)
                        self.assertLessEqual(len(nodes), 38)
                        self.assertGreaterEqual(len(names), 36)
                        self.assertLessEqual(len(names), 46)

    def test_fail_closed_rejections(self):
        original_xml = (ROOT / "tests/fixtures/ui-profile.xml").read_text()
        original_tsv = (ASSETS / "ui-modules.tsv").read_text()
        with tempfile.TemporaryDirectory() as temp:
            tdir = Path(temp)
            config = tdir / "config"
            values = {
                "base": 1,
                "metadata": "755:0:0",
                "nvram": "disable",
                "package": "a" * 64,
                "service-ids": "android-auto,pandora,siriusxm",
                "service.android-auto": 1,
                "service.pandora": 1,
                "service.siriusxm": 1,
                "touch": 1,
                "warning": 1,
                "wireless": 1,
            }
            config.write_text("OC2\n" + "".join(f"{k}={v}\n" for k, v in sorted(values.items())))

            def run_awk(*, mode="mmui", tsv_path=ASSETS / "ui-modules.tsv", xml_path=None):
                target_xml = xml_path or (ROOT / "tests/fixtures/ui-profile.xml")
                return subprocess.run(
                    [
                        "awk",
                        "-v",
                        "operation=compose",
                        "-v",
                        "ui_mode=" + mode,
                        "-v",
                        "modules=" + str(tsv_path),
                        "-v",
                        "catalog=" + str(ASSETS / "services.tsv"),
                        "-v",
                        "catalog_bytes=" + str((ASSETS / "services.tsv").stat().st_size),
                        "-v",
                        "input=" + str(config),
                        "-v",
                        "input_bytes=" + str(config.stat().st_size),
                        "-f",
                        ASSETS / "preferences.awk",
                        "-f",
                        ASSETS / "ui-profile.awk",
                        str(target_xml),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

            # 1) Invalid ui_mode
            self.assertNotEqual(run_awk(mode="invalid").returncode, 0)

            # 2) Missing ui-modules.tsv
            self.assertNotEqual(run_awk(tsv_path=tdir / "missing.tsv").returncode, 0)

            # 3) Duplicate numeric uiaid across distinct UIA rows
            lines = original_tsv.splitlines()
            dup_id_tsv = tdir / "dup-id.tsv"
            replaced = False
            out_lines = []
            for ln in lines:
                if not replaced and ln.startswith("uia\t") and not ln.startswith("uia\tsystem\t"):
                    parts = ln.split("\t")
                    parts[3] = "1"
                    out_lines.append("\t".join(parts))
                    replaced = True
                else:
                    out_lines.append(ln)
            dup_id_tsv.write_text("\n".join(out_lines) + "\n")
            self.assertNotEqual(run_awk(tsv_path=dup_id_tsv).returncode, 0)

            # 4) Wrong UIA count (dropped one uia row)
            short_tsv = tdir / "short.tsv"
            dropped = False
            short_lines = []
            for ln in lines:
                if not dropped and ln.startswith("uia\t") and not ln.startswith("uia\tsystem\t"):
                    dropped = True
                    continue
                short_lines.append(ln)
            short_tsv.write_text("\n".join(short_lines) + "\n")
            self.assertNotEqual(run_awk(tsv_path=short_tsv).returncode, 0)

            # 5) Duplicate attribute on a <Config> element
            dup_attr_xml = tdir / "dup-attr.xml"
            dup_text = original_xml.replace('name="system"', 'name="system" name="system"', 1)
            self.assertNotEqual(dup_text, original_xml)
            dup_attr_xml.write_text(dup_text)
            self.assertNotEqual(run_awk(xml_path=dup_attr_xml).returncode, 0)

            # 6) Mismatched uiaid on <Config>
            bad_id_xml = tdir / "bad-id.xml"
            bad_id_text = original_xml.replace(
                'uiaid="1" name="system"', 'uiaid="999" name="system"', 1
            )
            self.assertNotEqual(bad_id_text, original_xml)
            bad_id_xml.write_text(bad_id_text)
            self.assertNotEqual(run_awk(xml_path=bad_id_xml).returncode, 0)

            # 7) Missing libjciuiasystem.so anchor when warning=1
            bad_anchor_xml = tdir / "bad-anchor.xml"
            bad_anchor_text = original_xml.replace("libjciuiasystem.so", "libother.so", 1)
            self.assertNotEqual(bad_anchor_text, original_xml)
            bad_anchor_xml.write_text(bad_anchor_text)
            self.assertNotEqual(run_awk(xml_path=bad_anchor_xml).returncode, 0)

            # 8) Single-line non-self-closing omitted <Config ...>...</Config> cleanly accepted,
            #    while an unclosed omitted <Config ...> is rejected.
            omitted_name = next(
                ln.split("\t")[1]
                for ln in lines
                if ln.startswith("uia\t") and ln.split("\t")[2] == "base"
            )
            xml_lines = original_xml.splitlines()
            target_idx = next(i for i, ln in enumerate(xml_lines) if f'name="{omitted_name}"' in ln)
            raw_line = xml_lines[target_idx]
            self.assertTrue(raw_line.rstrip().endswith("/>"), raw_line)
            one_line_xml = tdir / "one-line.xml"
            one_lines = list(xml_lines)
            one_lines[target_idx] = raw_line.rstrip()[:-2] + "></Config>"
            one_line_xml.write_text("\n".join(one_lines) + "\n")
            self.assertEqual(run_awk(xml_path=one_line_xml).returncode, 0)
            unclosed_xml = tdir / "unclosed.xml"
            unclosed_lines = list(xml_lines)
            unclosed_lines[target_idx] = raw_line.rstrip()[:-2] + ">"
            unclosed_xml.write_text("\n".join(unclosed_lines) + "\n")
            self.assertNotEqual(run_awk(xml_path=unclosed_xml).returncode, 0)
