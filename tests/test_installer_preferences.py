"""Canonical preferences and the shared catalog admit only bounded data."""

import copy
import itertools
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

BUSYBOX = os.environ.get("OC_TEST_BUSYBOX") or shutil.which("busybox")

ASSETS = Path(__file__).resolve().parents[1] / "cmu/installer"


@unittest.skipUnless(shutil.which("awk"), "POSIX awk required")
class InstallerPreferences(unittest.TestCase):
    awk = ("awk",)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = self.root / "services.tsv"
        self.catalog.write_bytes((ASSETS / "services.tsv").read_bytes())
        self.config = self.root / "config"

    def run_preferences(self, operation, data=None, **values):
        arguments = {
            "operation": operation,
            "catalog": str(self.catalog),
            "catalog_bytes": str(self.catalog.stat().st_size),
            **values,
        }
        if data is not None:
            data = data.encode() if isinstance(data, str) else data
            self.config.write_bytes(data)
            arguments.update(input=str(self.config), input_bytes=str(len(data)))
        command = list(self.awk)
        for key, value in arguments.items():
            command += ["-v", f"{key}={value}"]
        command += ["-f", str(ASSETS / "preferences.awk")]
        return subprocess.run(
            command, capture_output=True, env={**os.environ, "LC_ALL": "C"}, timeout=5
        )

    def fresh(self):
        result = self.run_preferences(
            "write", package_id="a" * 64, nvram_value="disable", metadata_value="775:1000:1000"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_round_trip_and_independent_service_selection(self):
        original = self.fresh()
        self.assertEqual(original.splitlines()[0], b"OC2")
        self.assertEqual(original.splitlines()[1:], sorted(original.splitlines()[1:]))
        decoded = self.run_preferences("decode", original)
        self.assertEqual(decoded.returncode, 0, decoded.stderr)
        self.assertTrue(decoded.stdout.endswith(b"|android-auto=1,pandora=1\n"))
        pandora_off = self.run_preferences("set", original, key="service.pandora", value="0")
        both_off = self.run_preferences(
            "set", pandora_off.stdout, key="service.android-auto", value="0"
        )
        android_restored = self.run_preferences(
            "set", both_off.stdout, key="service.android-auto", value="1"
        )
        self.assertEqual(android_restored.returncode, 0, android_restored.stderr)
        self.assertEqual(android_restored.stdout, pandora_off.stdout)
        self.assertEqual(self.config.read_bytes(), both_off.stdout)

    def test_missing_new_choice_defaults_only_during_upgrade_write(self):
        original = self.fresh()
        older = original.replace(b"service.android-auto=1\n", b"").replace(
            b"service-ids=android-auto,pandora", b"service-ids=pandora"
        )
        self.assertNotEqual(self.run_preferences("decode", older).returncode, 0)
        updated = self.run_preferences(
            "write", older, package_id="b" * 64, nvram_value="enable", metadata_value="775:0:0"
        )
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertIn(b"service.android-auto=1\n", updated.stdout)
        self.assertIn(b"package=" + b"b" * 64 + b"\n", updated.stdout)
        self.assertNotIn(b"package=" + b"a" * 64, updated.stdout)

    def test_malformed_noncanonical_and_oversized_records_refuse(self):
        original = self.fresh()
        malformed = (
            original[:-1],
            original + b"\n",
            original.replace(b"OC2\n", b"OC3\n"),
            original.replace(b"base=0\n", b"base=0\nbase=0\n"),
            original.replace(b"base=0\n", b"unknown=0\n"),
            original.replace(b"wireless=0", b"wireless=01"),
            original.replace(b"wireless=0", b"wireless=0\x00"),
            original.replace(b"metadata=775:1000:1000", b"metadata=775:4294967296:0"),
            original.replace(b"service.pandora=1", b"service.pandora=2"),
            original.replace(b"service.pandora=1", b"service.unknown=1"),
            original.replace(b"base=0\n", b"base=" + b"0" * 1024 + b"\n"),
        )
        for data in malformed:
            with self.subTest(data=data[:80]):
                result = self.run_preferences("decode", data)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(self.config.read_bytes(), data)

    def test_catalog_rejects_overlapping_resource_claims(self):
        original = self.fresh()
        catalog = self.catalog.read_text()
        malformed = (
            catalog.replace("blm_ira_pandora", "aap_service"),
            catalog.replace("pandora|Pandora", "android-auto|Pandora"),
            catalog.replace("|1|blm_ira_pandora", "|2|blm_ira_pandora"),
            catalog.replace("aap_service jciAAPA", "aap_service aap_service"),
            catalog.replace("android-auto|", "touch|"),
        )
        for data in malformed:
            with self.subTest(catalog=data):
                self.catalog.write_text(data)
                result = self.run_preferences("decode", original)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_catalog_requires_final_lf_and_config_binds_its_exact_key_set(self):
        config = self.fresh()
        for changed in (
            config.replace(b"service-ids=android-auto,pandora", b"service-ids=pandora"),
            config.replace(
                b"service-ids=android-auto,pandora",
                b"service-ids=android-auto,android-auto,pandora",
            ),
            config.replace(
                b"service-ids=android-auto,pandora", b"service-ids=pandora,android-auto"
            ),
            config.replace(b"service-ids=android-auto,pandora\n", b""),
        ):
            self.assertNotEqual(self.run_preferences("decode", changed).returncode, 0)
        self.catalog.write_bytes(self.catalog.read_bytes()[:-1])
        self.assertNotEqual(self.run_preferences("decode", config).returncode, 0)

    def test_attributes_are_named_once_and_tabbed_wcp_args_do_not_duplicate(self):
        config = self.fresh().replace(b"base=0", b"base=1").replace(b"wireless=0", b"wireless=1")
        for board in (False, True):
            source = self.profile(board)
            for name in ("jciAAPA", "jciDAB"):
                needle = 'name="' + name + '" autorun="yes"'
                for changed in (
                    source.replace(needle, 'name="' + name + '" autorun="no" autorun="yes"'),
                    source.replace(needle, 'name="' + name + '" old_autorun="yes"'),
                    source.replace(needle, 'name="' + name + '" autorun=\'no\' autorun="yes"'),
                ):
                    self.assertNotEqual(self.compose(changed, config).returncode, 0)
            tabbed = self.profile(True).replace(' args="wcp"', '\targs="wcp"')
            result = self.compose(tabbed, config)
            self.assertEqual(result.returncode, 0, result.stderr)
            ET.fromstring(result.stdout)
            self.assertEqual(result.stdout.count(b'\targs="wcp"'), tabbed.count('\targs="wcp"'))

    def test_rows_escape_catalog_text_and_keep_unknown_selection_explicit(self):
        config = self.fresh()
        self.catalog.write_text(
            self.catalog.read_text().replace("Pandora|", 'Pandora "test"\\label|')
        )
        result = self.run_preferences("rows", config, selected_services="android-auto=0")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)
        self.assertEqual(rows[0]["saved"], 1)
        self.assertEqual(rows[0]["current"], 0)
        self.assertIsNone(rows[1]["current"])
        self.assertEqual(rows[1]["label"], 'Pandora "test"\\label')
        for selected in ("android-auto=1,android-auto=0", "pandora=2", "=1"):
            self.assertNotEqual(
                self.run_preferences("rows", config, selected_services=selected).returncode, 0
            )

    def test_dev9_changes_retain_supported_policy_and_reject_new_service_writes(self):
        legacy = (
            self.fresh()
            .replace(b"service.android-auto=1\n", b"")
            .replace(b"service-ids=android-auto,pandora\n", b"")
        )
        changed = self.run_preferences("set", legacy, legacy="1", key="service.pandora", value="0")
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.assertEqual(self.run_preferences("legacy", changed.stdout).stdout, b"1|1|0|0|0\n")
        self.assertNotEqual(
            self.run_preferences(
                "set", legacy, legacy="1", key="service.android-auto", value="0"
            ).returncode,
            0,
        )

    def profile(self, wcp=False):
        root = ET.Element("services")
        names = (
            "stage_1",
            "stage_3",
            "stage_wifi",
            "jciVBS",
            "jciMMUI",
            "jciUSBMGR",
            "jciCARPLAY",
            "jciBCA",
            "blm_nms_svc",
            "bds",
            "start_network",
            "devicemanager",
            "aap_service",
            "jciAAPA",
            "blm_ira_pandora",
            "jciDAB",
            "jcitv",
            "blm_ira_stitcher",
            "irsstitcher_server",
            "stage_vr",
            "jciLDS",
            "peer",
        )
        for name in names:
            attributes = {"type": "process", "name": name, "autorun": "yes", "reset_board": "yes"}
            if name == "jciMMUI":
                attributes["path"] = "/tmp/open-connect/feature/mmui.so"
                attributes["args"] = "mouse=filtered-mouse0, display=filtered-touchscreen0" + (
                    ", wcp" if wcp else ""
                )
            elif name in ("jciUSBMGR", "jciCARPLAY", "jciBCA", "blm_nms_svc") and wcp:
                attributes["args"] = "wcp"
            elif name == "bds":
                attributes["args"] = "-interface dbus" + (" -wcp" if wcp else "")
            elif name == "start_network":
                attributes["path"] = "/jci/scripts/start_network.sh"
                attributes["args"] = "" if wcp else "UCP"
            elif name == "stage_vr":
                attributes["args"] = "5s"
            elif name == "jciLDS":
                attributes["args"] = "actual-gps-provider"
            node = ET.SubElement(root, "service", attributes)
            parents = {
                "bds": ("stage_3", "settings", "dmserver"),
                "stage_wifi": ("stage_3", "blm_ira_aha"),
                "peer": ("stage_3", "blm_ira_aha"),
            }.get(name, ("keep",))
            for parent in parents:
                ET.SubElement(node, "dependency", {"type": "service", "value": parent})
        ET.indent(root)
        return ET.tostring(root, encoding="unicode") + "\n"

    def compose(self, source, config):
        path = self.root / "profile.xml"
        path.write_text(source)
        self.config.write_bytes(config)
        return subprocess.run(
            [
                *self.awk,
                "-v",
                "operation=compose",
                "-v",
                f"catalog={self.catalog}",
                "-v",
                f"catalog_bytes={self.catalog.stat().st_size}",
                "-v",
                f"input={self.config}",
                "-v",
                f"input_bytes={len(config)}",
                "-f",
                str(ASSETS / "preferences.awk"),
                "-f",
                str(ASSETS / "sm-profile.awk"),
                str(path),
            ],
            capture_output=True,
            env={**os.environ, "LC_ALL": "C"},
            timeout=5,
        )

    def test_board_and_choice_matrix_changes_only_claimed_attributes(self):
        original = self.fresh()
        for wcp, wireless, base, android, pandora in itertools.product((0, 1), repeat=5):
            with self.subTest(
                wcp=wcp, wireless=wireless, base=base, android=android, pandora=pandora
            ):
                source = self.profile(bool(wcp))
                config = (
                    original.replace(b"base=0", f"base={base}".encode())
                    .replace(b"wireless=0", f"wireless={wireless}".encode())
                    .replace(b"service.android-auto=1", f"service.android-auto={android}".encode())
                    .replace(b"service.pandora=1", f"service.pandora={pandora}".encode())
                )
                result = self.compose(source, config)
                self.assertEqual(result.returncode, 0, result.stderr)
                before = ET.fromstring(source)
                after = ET.fromstring(result.stdout)
                jobs = {node.get("name"): node for node in after}
                self.assertEqual(len(after), len(before) + 1 + wireless)
                for node in before:
                    expected = copy.deepcopy(node)
                    name = expected.get("name")
                    if (name in ("aap_service", "jciAAPA") and not android) or (
                        name == "blm_ira_pandora" and not pandora
                    ):
                        expected.set("autorun", "no")
                    if base and name in (
                        "jciDAB",
                        "jcitv",
                        "blm_ira_stitcher",
                        "irsstitcher_server",
                    ):
                        expected.set("autorun", "no")
                    if wireless:
                        if name == "jciMMUI" and not wcp:
                            expected.set("args", expected.get("args") + ", wcp")
                        if name in ("jciUSBMGR", "jciCARPLAY", "jciBCA", "blm_nms_svc"):
                            expected.set("args", "wcp")
                        if name == "bds":
                            expected.set("args", "-interface dbus -wcp")
                        if name == "start_network":
                            expected.set("args", "")
                        if name == "devicemanager":
                            expected.insert(
                                0,
                                ET.Element(
                                    "dependency",
                                    {"type": "service", "value": "open_connect_wireless"},
                                ),
                            )
                    if wireless and base:
                        if name == "start_network":
                            expected.set("path", "/bin/sh")
                            expected.set("args", "/tmp/open-connect/feature/network.sh")
                        if name in ("jciCARPLAY", "jciMMUI"):
                            expected.set("affinity_mask", "0x03")
                        elif name == "bds":
                            next(
                                child for child in expected if child.get("value") == "stage_3"
                            ).set("value", "jciUSBMGR")
                        elif name == "stage_wifi":
                            expected.remove(
                                next(
                                    child
                                    for child in expected
                                    if child.get("value") == "blm_ira_aha"
                                )
                            )
                    self.assertEqual(jobs[name].attrib, expected.attrib)
                    self.assertEqual(
                        [child.attrib for child in jobs[name]], [child.attrib for child in expected]
                    )
                worker = jobs["open_connect_settings"]
                self.assertEqual(worker.get("reset_board"), "no")
                self.assertEqual(worker.get("affinity_mask"), "0x02")
                self.assertEqual(worker.find("dependency").get("value"), "stage_3")

    def test_settings_gate_requires_one_stage3_on_each_board(self):
        for wcp, duplicate in itertools.product((False, True), repeat=2):
            with self.subTest(wcp=wcp, duplicate=duplicate):
                root = ET.fromstring(self.profile(wcp))
                gate = next(node for node in root if node.get("name") == "stage_3")
                if duplicate:
                    root.append(copy.deepcopy(gate))
                else:
                    root.remove(gate)
                ET.indent(root)
                self.assertNotEqual(
                    self.compose(ET.tostring(root, encoding="unicode"), self.fresh()).returncode,
                    0,
                )

    def test_missing_duplicate_and_preexisting_claims_refuse(self):
        config = self.fresh().replace(b"base=0", b"base=1").replace(b"wireless=0", b"wireless=1")
        for name in (
            "stage_1",
            "stage_3",
            "stage_wifi",
            "jciVBS",
            "aap_service",
            "jciAAPA",
            "blm_ira_pandora",
            "jciDAB",
            "jcitv",
            "blm_ira_stitcher",
            "irsstitcher_server",
            "jciUSBMGR",
            "jciCARPLAY",
            "jciBCA",
            "blm_nms_svc",
            "jciMMUI",
            "bds",
            "start_network",
            "devicemanager",
        ):
            for duplicate in (False, True):
                with self.subTest(name=name, duplicate=duplicate):
                    root = ET.fromstring(self.profile())
                    node = next(node for node in root if node.get("name") == name)
                    if duplicate:
                        root.append(copy.deepcopy(node))
                    else:
                        root.remove(node)
                    ET.indent(root)
                    self.assertNotEqual(
                        self.compose(ET.tostring(root, encoding="unicode"), config).returncode, 0
                    )
        for worker in ("open_connect_settings", "open_connect_wireless"):
            source = self.profile().replace('name="peer"', f'name="{worker}"')
            self.assertNotEqual(self.compose(source, config).returncode, 0)
        # Four aggregate matches must not let duplicate BCA hide missing USBMGR.
        source = self.profile().replace('name="jciUSBMGR"', 'name="jciBCA"')
        self.assertNotEqual(self.compose(source, config).returncode, 0)
        source = self.profile().replace('name="jciUSBMGR"', 'name="jciUSBMGR" name="jciBCA"')
        self.assertNotEqual(self.compose(source, config).returncode, 0)

    def test_early_wireless_requires_each_original_dependency_once(self):
        config = self.fresh().replace(b"base=0", b"base=1").replace(b"wireless=0", b"wireless=1")
        for service, parent in (
            ("bds", "stage_3"),
            ("bds", "settings"),
            ("bds", "dmserver"),
            ("stage_wifi", "stage_3"),
            ("stage_wifi", "blm_ira_aha"),
        ):
            for duplicate in (False, True):
                with self.subTest(service=service, parent=parent, duplicate=duplicate):
                    root = ET.fromstring(self.profile())
                    node = next(node for node in root if node.get("name") == service)
                    dependency = next(child for child in node if child.get("value") == parent)
                    if duplicate:
                        node.append(copy.deepcopy(dependency))
                    else:
                        node.remove(dependency)
                    ET.indent(root)
                    self.assertNotEqual(
                        self.compose(ET.tostring(root, encoding="unicode"), config).returncode, 0
                    )
        source = self.profile().replace('value="dmserver"', 'value="jciUSBMGR"')
        self.assertNotEqual(self.compose(source, config).returncode, 0)

    def test_wireless_leaf_affinity_preserves_foreign_claim(self):
        config = self.fresh().replace(b"base=0", b"base=1").replace(b"wireless=0", b"wireless=1")
        for name in ("jciCARPLAY", "jciMMUI"):
            with self.subTest(name=name):
                source = self.profile().replace(
                    f'name="{name}"', f'name="{name}" affinity_mask="0x02"'
                )
                self.assertNotEqual(self.compose(source, config).returncode, 0)

    def test_restoring_android_auto_leaves_clean_pandora_only_profile(self):
        original = self.fresh().replace(b"base=0", b"base=1").replace(b"wireless=0", b"wireless=1")
        pandora_off = self.run_preferences("set", original, key="service.pandora", value="0")
        both_off = self.run_preferences(
            "set", pandora_off.stdout, key="service.android-auto", value="0"
        )
        restored = self.run_preferences(
            "set", both_off.stdout, key="service.android-auto", value="1"
        )
        for wcp in (False, True):
            expected = self.compose(self.profile(wcp), pandora_off.stdout)
            actual = self.compose(self.profile(wcp), restored.stdout)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(actual.returncode, 0, actual.stderr)
            self.assertEqual(actual.stdout, expected.stdout)

    def test_adding_a_service_requires_only_a_catalog_row(self):
        with self.catalog.open("a") as stream:
            stream.write("z-test|Test|1|optional_leaf|Load after restart.|Stop after restart.\n")
        config = self.fresh()
        disabled = self.run_preferences("set", config, key="service.z-test", value="0")
        self.assertEqual(disabled.returncode, 0, disabled.stderr)
        source = self.profile().replace('name="peer"', 'name="optional_leaf"')
        result = self.compose(source, disabled.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        jobs = {node.get("name"): node for node in ET.fromstring(result.stdout)}
        self.assertEqual(jobs["optional_leaf"].get("autorun"), "no")
        self.assertEqual(jobs["jciAAPA"].get("autorun"), "yes")


@unittest.skipUnless(BUSYBOX, "BusyBox awk required")
class InstallerBusyboxPreferences(InstallerPreferences):
    awk = (BUSYBOX, "awk")
