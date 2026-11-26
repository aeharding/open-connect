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


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class InstallerComposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.tools = Path(cls.temp.name).resolve()
        subprocess.run(
            ["clang", "-DOC_HOST", ROOT / "cmu/startup/flush.c", "-o", cls.tools / "flush"],
            check=True,
            capture_output=True,
            timeout=20,
        )

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
                            'P=$3; . "$1/state.sh"; . "$2"; factory_wireless',
                            "test",
                            ASSETS,
                            firmware,
                            self.tools,
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

    def test_wcp_dependency_resolves_without_accepting_unknown_paths(self):
        driver = (
            'set -eu; P=$2; . "$1/state.sh"; . "$1/firmware.sh"\n'
            "dependency_path root/sm_WCP.conf\n"
            "for name in root/not_known.conf root/../sm_WCP.conf root//sm_WCP.conf; do\n"
            '    if dependency_path "$name"; then exit 1; fi\n'
            "done\n"
        )
        result = subprocess.run(
            ["sh", "-c", driver, "test", ASSETS, self.tools],
            capture_output=True,
            text=True,
            check=True,
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
            backend_source = (ASSETS / "backend.sh").read_text()
            backend = backend_source.splitlines()
            # Keep the actual complete handler, including multiline definitions.
            start = backend_source.index("fail() {")
            end = backend_source.index("\n}\n", start) + len("\n}\n")
            error_handler = backend_source[start:end]
            invocation = next(
                line for line in backend if line.lstrip().startswith('compose "$package"')
            )
            driver = (
                'set -eu\numask 077\nD=$1; P=$4; . "$2/state.sh"; . "$2/firmware.sh"\n'
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
                        ["sh", "-c", driver, "test", root, ASSETS, package, self.tools],
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
                    self.assertTrue(result.stdout, result.stderr)
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
                'set -eu\nP=$3; . "$1/state.sh"; . "$2"\n'
                "original_files() { :; }\ndependencies_capture -\ndependency_path root/manager.so\n"
            )
            result = subprocess.run(
                ["sh", "-c", driver, "test", ASSETS, firmware, self.tools],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(result.stdout.splitlines(), expected + [str(root / "manager.so")])
