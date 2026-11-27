"""Root selector creation/removal uses the maintained interrupted publisher."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class SelectorPublication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.tools = self.root / "tools"
        self.folder = self.root / "bin"
        self.tools.mkdir()
        self.folder.mkdir()
        self.target = self.folder / "open-connect-boot-select"
        self.source = self.root / "planned"
        self.source.write_bytes(b"new verified selector\nsecond complete line\n")
        self.mount = self.root / "mount"
        self.mount.write_text("ro,noatime\n")
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
        from tests.host_bins import copy_host_flush

        copy_host_flush(self.tools / "flush")
        self.firmware = self.root / "firmware.sh"
        self.firmware.write_text(
            (ASSETS / "firmware.sh").read_text().replace("/usr/bin", str(self.folder))
        )
        self.driver = self.root / "driver.sh"
        self.driver.write_text(r"""
set -eu
umask 077
P=$1; FIRMWARE=$2; SOURCE=$3; TARGET=$4; MOUNT=$5; EXPECTED=$6; ACTION=$7; CUT=$8; STATE=$9
. "$STATE"
. "$FIRMWARE"
R_REV=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
AUTOSTART=${TARGET%/*}/autostart
root_mode() { cat "$MOUNT"; }
remount() { printf '%s,noatime\n' "$1" > "$MOUNT"; }
mv() {
    command mv "$@" || return
    for destination; do :; done
    if test "$CUT:$destination" = "renamed:$TARGET"; then sh -c 'kill -KILL "$PPID"'; fi
}
rm() {
    command rm "$@" || return
    if test "$CUT:$1" = "unlinked:$TARGET"; then sh -c 'kill -KILL "$PPID"'; fi
}
if test "$EXPECTED" = -; then expected_mode=-
else expected_mode=700:$(id -u):$(id -g); fi
if test "$ACTION" = remove; then SOURCE=-; mode=-
else mode=700:$(id -u):$(id -g); fi
root_publish "$TARGET" "$SOURCE" "$mode" "$EXPECTED" "$expected_mode"
""")

    def invoke(self, expected="-", *, remove=False, cut="none", target=None):
        return subprocess.run(
            [
                "sh",
                self.driver,
                self.tools,
                self.firmware,
                self.source,
                target or self.target,
                self.mount,
                expected,
                "remove" if remove else "publish",
                cut,
                ASSETS / "state.sh",
            ],
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
            capture_output=True,
            timeout=10,
        )

    def digest(self, path=None):
        return hashlib.sha256((path or self.target).read_bytes()).hexdigest()

    def test_absent_install_update_and_removal_restore_absence(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
        before = self.digest()
        self.source.write_bytes(b"updated verified selector\n")
        result = self.invoke(before)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
        result = self.invoke(self.digest(), remove=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.mount.read_text(), "ro,noatime\n")
        self.assertEqual(list(self.folder.glob(".open-connect-*")), [])

    def test_foreign_file_directory_and_dangling_link_are_preserved(self):
        self.target.write_bytes(b"foreign helper\n")
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(self.target.read_bytes(), b"foreign helper\n")
        self.target.unlink()
        self.target.mkdir()
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(list(self.target.iterdir()), [])
        self.target.rmdir()
        self.target.symlink_to("missing")
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(os.readlink(self.target), "missing")

    def test_cut_after_rename_finishes_flush_and_read_only_on_reconcile(self):
        result = self.invoke(cut="renamed")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
        self.assertEqual(self.mount.read_text(), "rw,noatime\n")
        result = self.invoke(self.digest())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.mount.read_text(), "ro,noatime\n")
        self.assertEqual(list(self.folder.glob(".open-connect-*")), [])

    def test_cut_after_unlink_recognizes_after_state_and_finishes_removal(self):
        self.target.write_bytes(b"owned selector\n")
        self.target.chmod(0o700)
        result = self.invoke(self.digest(), remove=True, cut="unlinked")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.mount.read_text(), "rw,noatime\n")
        result = self.invoke(remove=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.mount.read_text(), "ro,noatime\n")

    def test_removal_does_not_accept_unknown_bytes_or_other_targets(self):
        self.target.write_bytes(b"foreign replacement\n")
        self.target.chmod(0o700)
        result = self.invoke("a" * 64, remove=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_bytes(), b"foreign replacement\n")
        other = self.folder / "autostart"
        other.write_bytes(b"stock startup\n")
        other.chmod(0o700)
        result = self.invoke(self.digest(other), remove=True, target=other)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(other.read_bytes(), b"stock startup\n")


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class SelectorTransaction(unittest.TestCase):
    """The real journal orders helper publication around hook activation."""

    def setUp(self):
        SelectorPublication.setUp(self)
        from tests.test_installer_transaction import DRIVER, fixture_package

        self.data = self.root / "state"
        self.data.mkdir(mode=0o700)
        (self.data / "snapshots").mkdir(mode=0o700)
        fixture_package(self.data, self.tools, b"verified selector\n")
        firmware = self.firmware.read_text().replace("selector_apply()", "actual_selector_apply()")
        self.firmware.write_text(firmware)
        driver = (
            DRIVER.replace(
                '. "$SOURCE/transaction.sh"',
                '. "$SOURCE/transaction.sh"\n. "$D-firmware"\n'
                'boot_snapshot_seal() { printf "%s\\n" "$1"; }\n'
                "selector_apply() {\n"
                ' actual_selector_apply "$@" || return\n'
                ' printf "helper:%s\\n" "$(test -e "'
                + str(self.target)
                + '" && echo present || echo absent)" >> "$D-order"\n'
                ' test "$CUT" != selector || kill -KILL $$\n'
                "}\n",
            )
            .replace(
                "startup_publish() {",
                "startup_publish() {\n"
                ' test -f "' + str(self.target) + '" || return 1\n'
                ' printf "hook:%s\\n" "$(cat "$1")" >> "$D-order"\n',
            )
            .replace(
                'R_BASE=$(state_capture - - "")',
                'mkdir "$D/resources"\n'
                'selector_capture "$D/resources" || exit 1\n'
                'R_BASE=$(state_capture - "$D/resources" "")',
            )
            .replace(
                "service_choice=1; base_choice=0; wireless_choice=0",
                'digest=$(sha "$D/packages/$package/boot-select")\n'
                "# The fixture supplies its known package, independent of selector_compose.\n"
                'printf "%s|700:%s:%s|%s\\n" "$digest" "$(id -u)" "$(id -g)" "$package" > "$D/resources/selector"\n'
                "service_choice=1; base_choice=0; wireless_choice=0",
            )
            .replace(
                'dependencies" - "$service_choice"',
                'dependencies" "$D/resources" "$service_choice"',
            )
            .replace(
                "root_mode() { printf 'ro,noatime\\n'; }",
                'root_mode() { cat "' + str(self.mount) + '"; }\n'
                'remount() { printf "%s,noatime\\n" "$1" > "' + str(self.mount) + '"; }',
            )
        )
        driver = driver.replace(
            "record_read\nif ! settled;",
            'if test "$ACTION" = read-snapshot; then snapshot_read "$CUT"; exit; fi\n'
            "record_read\nif ! settled;",
        )
        # Host fixture state_capture uses its fake target; firmware root writes
        # remain restricted to this test's temporary bin directory.
        (self.root / "state-firmware").write_text(self.firmware.read_text())
        self.driver.write_text(driver)
        result = self.transaction("init")
        self.assertEqual(result.returncode, 0, result.stderr)

    def transaction(self, action, cut="none"):
        return subprocess.run(
            ["sh", self.driver, self.data, self.tools, ASSETS, action, cut],
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_journal_installs_before_hook_and_removes_after_stock_hook(self):
        result = self.transaction("install")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.transaction("uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.target.exists())
        self.assertEqual(
            (self.root / "state-order").read_text().splitlines(),
            ["helper:present", "hook:installed", "hook:stock", "helper:absent"],
        )

    def test_interrupted_helper_activation_recovers_from_prepared_record(self):
        result = self.transaction("install", "selector")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.target.is_file())
        self.assertEqual((self.data / "record").read_text().split("|")[1], "install")
        self.assertEqual((self.root / "state-target").read_text(), "stock\n")
        result = self.transaction("install")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "state-target").read_text(), "installed\n")
        self.assertEqual((self.data / "record").read_text().split("|")[1], "active")

    def test_selector_descriptor_is_hashed_typed_and_bound_to_its_package(self):
        self.assertEqual(self.transaction("install").returncode, 0)
        identity = (self.data / "record").read_text().split("|")[5]
        original = self.data / "snapshots" / identity
        descriptor = (original / "selector").read_text()
        for name, changed in (
            ("package", descriptor[:-65] + "f" * 64 + "\n"),
            ("mode", descriptor.replace("|700:", "|755:")),
            ("extra", descriptor.rstrip("\n") + "|unexpected\n"),
            ("unlisted", descriptor),
        ):
            with self.subTest(name=name):
                work = self.data / "snapshots" / (".test-" + name)
                shutil.copytree(original, work)
                (work / "selector").write_text(changed)
                manifest = "".join(
                    hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n"
                    for path in sorted(work.iterdir())
                    if path.name != "files.sha256"
                    and not (name == "unlisted" and path.name == "selector")
                )
                (work / "files.sha256").write_text(manifest)
                new_id = hashlib.sha256(manifest.encode()).hexdigest()
                work.rename(work.with_name(new_id))
                result = self.transaction("read-snapshot", new_id)
                self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(), "verified selector\n")
