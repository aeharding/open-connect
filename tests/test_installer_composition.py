"""Composition must stop at a failed native write, even in an OR-list caller."""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


class InstallerComposition(unittest.TestCase):
    def test_vr_pilot_changes_only_the_gate_and_requires_one_stock_delay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, selected = root / "source", root / "selected"
            gate = '<service name="stage_vr" args="5s" autorun="yes" />\n'
            peer = '<service name="natp" sched_priority="0" autorun="yes" />\n'
            original = '<services>\n<service name="stage_1" />\n' + gate + peer + "</services>\n"
            driver = 'set -eu; . "$1/firmware.sh"; S_BASE=$4; boot_sm_profile "$2" "$3"'

            def render(text, base):
                source.write_text(text)
                return subprocess.run(
                    ["sh", "-c", driver, "test", ASSETS, source, selected, str(base)],
                    capture_output=True,
                    timeout=5,
                )

            for base in (0, 1):
                self.assertEqual(render(original, base).returncode, 0)
                expected_gate = gate.replace('args="5s"', 'args="35s"') if base else gate
                self.assertIn(expected_gate, selected.read_text())
                self.assertIn(peer, selected.read_text())
                self.assertEqual(selected.read_text().count('name="open_connect_settings"'), 1)
            for changed in (
                original.replace(gate, ""),
                original.replace(gate, gate + gate),
                original.replace('args="5s"', 'args="6s"'),
            ):
                self.assertNotEqual(render(changed, 1).returncode, 0)

    def test_boot_mounts_allow_rootfs_but_refuse_protected_overlays(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            mounts = root / "mounts"
            firmware = root / "firmware.sh"
            firmware.write_text(
                (ASSETS / "firmware.sh").read_text().replace("/proc/self/mounts", str(mounts))
            )
            physical = "/dev/ffx01p1 / relfs ro,noatime 0 0\n"
            persistence = "/dev/mmcblk0p2 /tmp/mnt/data_persist relfs rw,noatime 0 0\n"
            for extra, valid in (("", True), ("rootfs / rootfs rw 0 0\n", True)):
                mounts.write_text(extra + physical + persistence)
                result = subprocess.run(["sh", "-c", '. "$1"; boot_mount_guard', "test", firmware])
                self.assertEqual(result.returncode == 0, valid)
            for overlay in (
                "/tmp/open-connect",
                "/tmp/open-connect/feature",
                "/tmp/mnt/data_persist/open-connect",
            ):
                mounts.write_text(physical + persistence + f"tmpfs {overlay} tmpfs rw 0 0\n")
                result = subprocess.run(["sh", "-c", '. "$1"; boot_mount_guard', "test", firmware])
                self.assertNotEqual(result.returncode, 0)
            mounts.write_text(physical.replace("ro,noatime", "rw,noatime") + persistence)
            strict = subprocess.run(["sh", "-c", '. "$1"; boot_mount_guard', "test", firmware])
            maintenance = subprocess.run(
                ["sh", "-c", '. "$1"; boot_mount_guard maintenance', "test", firmware]
            )
            self.assertNotEqual(strict.returncode, 0)
            self.assertEqual(maintenance.returncode, 0)

    def test_factory_wireless_uses_only_the_verified_oem_board_branch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            result = root / "board-result"
            board = root / "board.sh"
            board.write_text('exit "$(cat ' + shlex.quote(str(result)) + ')"\n')
            firmware = root / "firmware.sh"
            firmware.write_text(
                (ASSETS / "firmware.sh")
                .read_text()
                .replace("/jci/scripts/get_board_type.sh", str(board))
                .replace(
                    "2c66145fe9c76cbbed471b6e190c57837c72ae5a3cf8f750c6c87a689ded20da",
                    hashlib.sha256(board.read_bytes()).hexdigest(),
                )
            )

            def detected():
                return (
                    subprocess.run(
                        [
                            "sh",
                            "-c",
                            '. "$1/state.sh"; . "$2"; factory_wireless',
                            "test",
                            ASSETS,
                            firmware,
                        ],
                        capture_output=True,
                        timeout=5,
                    ).returncode
                    == 0
                )

            for code, factory in ((1, False), (2, True), (0, False), (3, False)):
                result.write_text(str(code) + "\n")
                self.assertEqual(detected(), factory)
            marker = root / "untrusted-executed"
            board.write_text("touch " + shlex.quote(str(marker)) + "\nexit 2\n")
            self.assertFalse(detected())
            self.assertFalse(marker.exists())

    def test_service_selection_preserves_peers_and_refuses_unknown_structure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, selected = root / "original", root / "selected"
            pandora = '<service type="jci_service" name="blm_ira_pandora" autorun="yes" retry_count="6" />\n'
            original = (
                '<services>\n<service name="peer" autorun="yes" />\n' + pandora + "</services>\n"
            )
            driver = 'set -eu; . "$1/state.sh"; . "$1/firmware.sh"; service_config "$2" "$3" "$4"'

            def run(value):
                return subprocess.run(
                    ["sh", "-c", driver, "test", ASSETS, source, selected, value],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

            source.write_text(original)
            self.assertEqual(run("1").returncode, 0)
            self.assertEqual(selected.read_text(), original)
            self.assertEqual(run("0").returncode, 0)
            self.assertEqual(
                selected.read_text(),
                original.replace(pandora, pandora.replace('autorun="yes"', 'autorun="no"')),
            )
            self.assertEqual(source.read_text(), original)
            for unknown in (
                original.replace(pandora, ""),
                original.replace(pandora, pandora * 2),
                original.replace(
                    'name="blm_ira_pandora" autorun="yes"', 'name="blm_ira_pandora" autorun="no"'
                ),
            ):
                source.write_text(unknown)
                self.assertNotEqual(run("0").returncode, 0)
                self.assertEqual(source.read_text(), unknown)
            for invalid in ("", "2", "false"):
                self.assertNotEqual(run(invalid).returncode, 0)

    def test_wcp_dependency_resolves_without_accepting_unknown_paths(self):
        driver = (
            'set -eu; . "$1/state.sh"; . "$1/firmware.sh"\n'
            "dependency_path root/sm_WCP.conf\n"
            "for name in root/not_known.conf root/../sm_WCP.conf root//sm_WCP.conf; do\n"
            '    if dependency_path "$name"; then exit 1; fi\n'
            "done\n"
        )
        result = subprocess.run(
            ["sh", "-c", driver, "test", ASSETS], capture_output=True, text=True, check=True
        )
        self.assertEqual(result.stdout, "/jci/sm/sm_WCP.conf\n")

    def test_each_failed_patch_write_refuses_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for name in ("originals", "packages", "composed", "tools"):
                (root / name).mkdir(mode=0o700)
            for name in ("uia.so", "mmui.so"):
                (root / "originals" / name).write_bytes(b"synthetic original\n")
            package = "a" * 64
            (root / "packages" / package).mkdir()
            for name in (
                "native",
                "branch",
                "sizes",
                "layout",
                "mmui-path",
                "mmui-sizes",
                "mmui-length",
                "mmui-pointer",
                "mmui-count-pointer",
            ):
                (root / "packages" / package / (name + ".bin")).write_bytes(b"patch")
            shutil.copyfile(
                ROOT / "cmu/features/disclaimer/layout.txt",
                root / "packages" / package / "layout.txt",
            )
            for command in ("dd", "head", "tail"):
                wrapper = root / "tools" / command
                wrapper.write_text(
                    "#!/bin/sh\nset -eu\n"
                    'n=$(cat "$COUNT"); n=$((n+1)); echo "$n" > "$COUNT"\n'
                    'if test "$n" = "$FAIL_AT"; then exit 42; fi\n'
                    + "exec "
                    + shlex.quote(shutil.which(command))
                    + ' "$@"\n'
                )
                wrapper.chmod(0o700)
            backend = (ASSETS / "backend.sh").read_text().splitlines()
            error_handler = next(line for line in backend if line.startswith("fail()"))
            invocation = next(
                line for line in backend if line.lstrip().startswith('compose "$package"')
            )
            driver = (
                'set -eu\numask 077\nD=$1; . "$2/state.sh"; . "$2/firmware.sh"\n'
                # Synthetic fixtures enter immediately after input verification;
                # every composition write and its real caller context are intact.
                "verify_manifest() { :; }; originals_verify() { :; }\n"
                + error_handler
                + "\npackage=$3\n"
                + invocation
                + "\n"
            )
            # Prefix/gap/tail, payload/branch/sizes, every ELF layout word,
            # and all six MMUI writes must fail closed in the backend caller.
            for fail_at in range(1, 30):
                with self.subTest(write=fail_at):
                    (root / "count").write_text("0\n")
                    result = subprocess.run(
                        ["sh", "-c", driver, "test", root, ASSETS, package],
                        env={
                            **os.environ,
                            "PATH": str(root / "tools") + os.pathsep + os.environ["PATH"],
                            "COUNT": str(root / "count"),
                            "FAIL_AT": str(fail_at),
                        },
                        text=True,
                        capture_output=True,
                        timeout=10,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(
                        json.loads(result.stdout), {"ok": False, "error": "composition_failed"}
                    )
                    self.assertEqual((root / "count").read_text().strip(), str(fail_at))
                    self.assertFalse((root / "composed" / package).exists())

    def test_manager_and_access_tools_are_captured_and_resolved_as_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            contents = (ASSETS / "firmware.sh").read_text()
            expected = []
            for name, target in (
                ("manager.so", "/jci/lib/libjciuiamgr.so"),
                ("device-master.xml", "/etc/devmgr_config_master.xml"),
                ("eem.so", "/jci/vbs/modules/libjcimod_eem.so"),
                ("device-manager.so", "/jci/devicemanager/libdevicemanager.so"),
                ("rungetty", "/usr/bin/rungetty"),
                ("sshd", "/usr/sbin/sshd"),
                ("ssh-keygen", "/usr/bin/ssh-keygen"),
                ("framework.js", "/jci/gui/framework/js/GuiFramework.js"),
                ("lvds-service", "/jci/lvds/lvds_service"),
            ):
                fixture = root / name
                fixture.write_bytes(b"synthetic dependency\n")
                contents = contents.replace(target, str(fixture))
                expected.append(hashlib.sha256(fixture.read_bytes()).hexdigest() + "  root/" + name)
            firmware = root / "firmware.sh"
            firmware.write_text(contents)
            driver = (
                'set -eu\n. "$1/state.sh"; . "$2"\n'
                "original_files() { :; }\ndependencies_capture -\ndependency_path root/manager.so\n"
            )
            result = subprocess.run(
                ["sh", "-c", driver, "test", ASSETS, firmware],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(result.stdout.splitlines(), expected + [str(root / "manager.so")])
