"""Sparse UI selection preserves native IDs and Base-off OEM loading."""

import itertools
import os
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


class UIProfile(unittest.TestCase):
    def test_retained_plugin_list_resolves_every_authenticated_pin(self):
        rows = [
            row.split("\t")
            for row in (ASSETS / "ui-modules.tsv").read_text().splitlines()
            if row.startswith("vui\t") and row.split("\t")[2] != "base"
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            plugins = root / "plugins.list"
            plugins.write_text("".join(row[1] + "\n" for row in rows))
            busybox = os.environ.get("OC_TEST_BUSYBOX") or shutil.which("busybox")
            environments = [("host", os.environ.copy())]
            if busybox:
                tools = root / "tools"
                tools.mkdir()
                (tools / "awk").symlink_to(Path(busybox).resolve())
                environments.append(
                    (
                        "busybox",
                        {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
                    )
                )
            script = '. "$P/state.sh"; . "$P/firmware.sh"; vui_input_files "$1"'
            for name, environment in environments:
                with self.subTest(awk=name):
                    result = subprocess.run(
                        ["sh", "-c", script, "pins", plugins],
                        env={**environment, "P": str(ASSETS)},
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    actual = result.stdout.splitlines()[2:]
                    self.assertEqual(
                        actual,
                        [f"{row[3]} {row[1]} /jci/vui/plugins/{row[1]}" for row in rows],
                    )

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
