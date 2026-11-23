"""Durable record and immutable backup checks on real local files."""

import hashlib
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class InstallerState(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / "state"
        self.data.mkdir(mode=0o700)
        (self.data / "snapshots").mkdir(mode=0o700)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
        subprocess.run(
            [
                "clang",
                "-DOC_HOST",
                str(ROOT / "cmu/startup/flush.c"),
                "-o",
                str(self.tools / "flush"),
            ],
            check=True,
        )
        (self.root / "autostart").write_text("original startup\n")
        self.driver = self.root / "driver.sh"
        self.driver.write_text(
            "set -eu\numask 077\n"
            'D=$1; P=$2; . "$3"\n'
            "uuid() { openssl rand -hex 16; }\n"
            'case "$4" in\n'
            'create) base=$(snapshot_create "$5" - absent "755:$(id -u):$(id -g)" - - "")\n'
            'R_PHASE=removed; R_BACKEND=$(printf "%064d" 0); R_BASE=$base; R_CURRENT=$base\n'
            "R_BEFORE=-; R_AFTER=-; R_UNDO=-; R_BUDGET=0; R_OFF=-; R_BOOT=-; R_NOTICE=-\n"
            "record_write;;\n"
            'read) record_read && snapshot_read "$R_CURRENT";;\n'
            "change) record_read; R_BUDGET=3; record_write;;\n"
            'manifest) verify_manifest "$5";;\n'
            'create-dependencies) snapshot_create "$5" - absent "755:$(id -u):$(id -g)" "$6" - "";;\n'
            'read-prefs) snapshot_read "$5" && printf "%s|%s|%s\\n" "$S_PANDORA" "$S_BASE" "$S_WIRELESS";;\n'
            'read-pair) snapshot_read "$5" && snapshot_read "$6" && printf "%s|%s|%s\\n" "$S_PANDORA" "$S_BASE" "$S_WIRELESS";;\n'
            'dependencies) . "${3%/*}/firmware.sh"; . "${3%/*}/transaction.sh"; dependencies_match "$5";;\n'
            "esac\n"
        )
        self.assertEqual(self.run_command("create").returncode, 0)

    def run_command(self, action, path=None, *extra):
        return subprocess.run(
            [
                "sh",
                self.driver,
                self.data,
                self.tools,
                ROOT / "cmu/installer/state.sh",
                action,
                path or self.root / "autostart",
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=5,
            env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
        )

    def config_snapshot(self, config):
        original = next((self.data / "snapshots").iterdir())
        content = {
            name: original.joinpath(name).read_bytes()
            for name in ("autostart", "config", "dependencies")
        }
        content["config"] = config
        manifest = "".join(
            hashlib.sha256(data).hexdigest() + "  " + name + "\n" for name, data in content.items()
        ).encode()
        identity = hashlib.sha256(manifest).hexdigest()
        folder = self.data / "snapshots" / identity
        folder.mkdir(mode=0o700, exist_ok=True)
        for name, data in {**content, "files.sha256": manifest}.items():
            folder.joinpath(name).write_bytes(data)
        return identity

    def test_stock5_and_active_dev9_fields_remain_distinct(self):
        metadata = f"755:{os.getuid()}:{os.getgid()}"
        stock = f"-|0|0|absent|{metadata}\n".encode()
        active = f"{'a' * 64}|1|1|disable|{metadata}|0|1|1\n".encode()
        stock_id = self.config_snapshot(stock)
        active_id = self.config_snapshot(active)
        self.assertEqual(self.run_command("read-prefs", stock_id).stdout, "1|0|0\n")
        self.assertEqual(self.run_command("read-prefs", active_id).stdout, "0|1|1\n")
        # Stock must reset policy fields after decoding an active record.
        read = self.run_command("read-pair", active_id, stock_id)
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertEqual(read.stdout, "1|0|0\n")
        for config in (
            stock.replace(metadata.encode(), b"755:4294967296:0"),
            stock.replace(metadata.encode(), b"755:0:4294967296"),
            active.replace(metadata.encode(), b"755:4294967296:0"),
            active.replace(metadata.encode(), b"755:0:4294967296"),
            stock[:-1],
            stock[:-1] + b"\0\n",
            stock.replace(b"-|", b"a" * 64 + b"|", 1),
            active.replace(b"|0|1|1\n", b"\n"),
            active.replace(b"|0|1|1\n", b"|0\n"),
            active.replace(b"|0|1|1\n", b"|0|1\n"),
            active.replace(b"|0|1|1\n", b"|0|1|2\n"),
            active.replace(b"|0|1|1\n", b"|0|1|1|0\n"),
        ):
            with self.subTest(config=config):
                self.assertNotEqual(
                    self.run_command("read-prefs", self.config_snapshot(config)).returncode, 0
                )

    def test_canonical_config_uses_only_manifest_pinned_target_interpreter(self):
        packages = self.data / "packages"
        packages.mkdir(mode=0o700)
        folder = packages / "build"
        folder.mkdir(mode=0o700)
        for name in ("preferences.awk", "services.tsv"):
            shutil.copyfile(ROOT / "cmu/installer" / name, folder / name)
        manifest = "".join(
            hashlib.sha256((folder / name).read_bytes()).hexdigest() + "  " + name + "\n"
            for name in ("preferences.awk", "services.tsv")
        )
        (folder / "files.sha256").write_text(manifest)
        identity = hashlib.sha256(manifest.encode()).hexdigest()
        target = packages / identity
        folder.rename(target)
        config = subprocess.check_output(
            [
                "awk",
                "-v",
                "operation=write",
                "-v",
                f"catalog={target / 'services.tsv'}",
                "-v",
                f"catalog_bytes={(target / 'services.tsv').stat().st_size}",
                "-v",
                f"package_id={identity}",
                "-v",
                "nvram_value=disable",
                "-v",
                f"metadata_value=755:{os.getuid()}:{os.getgid()}",
                "-f",
                target / "preferences.awk",
            ]
        )
        current = self.config_snapshot(config)
        read = self.run_command("read-prefs", current)
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertEqual(read.stdout, "1|0|0\n")
        sentinel = self.root / "unverified-executed"
        interpreter = target / "preferences.awk"
        interpreter.write_text(
            'BEGIN {system("touch ' + str(sentinel) + '")}\n' + interpreter.read_text()
        )
        self.assertNotEqual(self.run_command("read-prefs", current).returncode, 0)
        self.assertFalse(sentinel.exists())

    def test_original_backup_changes_are_rejected(self):
        self.assertEqual(self.run_command("read").returncode, 0)
        snapshot = next((self.data / "snapshots").iterdir())
        (snapshot / "autostart").write_text("later change\n")
        self.assertNotEqual(self.run_command("read").returncode, 0)
        self.assertEqual((snapshot / "autostart").read_text(), "later change\n")

    def test_batched_manifest_rejects_changed_bytes_symlinks_and_traversal(self):
        folder = self.root / "manifest"
        folder.mkdir(mode=0o700)
        content = b"verified bytes\n"
        digest = hashlib.sha256(content).hexdigest()
        for name in ("one", "two"):
            (folder / name).write_bytes(content)
        manifest = folder / "files.sha256"
        manifest.write_text(f"{digest}  one\n{digest}  two\n")
        self.assertEqual(self.run_command("manifest", folder).returncode, 0)
        (folder / "two").write_bytes(b"changed\n")
        self.assertNotEqual(self.run_command("manifest", folder).returncode, 0)
        (folder / "two").unlink()
        (folder / "two").symlink_to(folder / "one")
        self.assertNotEqual(self.run_command("manifest", folder).returncode, 0)
        (self.root / "outside").write_bytes(content)
        manifest.write_text(f"{digest}  ../outside\n")
        self.assertNotEqual(self.run_command("manifest", folder).returncode, 0)

    def test_matching_hash_output_cannot_hide_failed_hash_process(self):
        openssl = shlex.quote(shutil.which("openssl"))
        (self.tools / "openssl").write_text(
            '#!/bin/sh\ncase " $* " in *" -r "*)\n'
            + openssl
            + ' "$@"\nexit 19;;\n*) exec '
            + openssl
            + ' "$@";; esac\n'
        )
        (self.tools / "openssl").chmod(0o700)
        self.assertNotEqual(self.run_command("read").returncode, 0)

    def test_dependency_groups_preserve_parent_and_individual_file_guards(self):
        package = "a" * 64
        content = b"synthetic dependency\n"
        digest = hashlib.sha256(content).hexdigest()
        folders = []
        entries = []
        for group in ("package", "composed"):
            folder = self.data / (group + "s" if group == "package" else group) / package
            folder.parent.mkdir(mode=0o700)
            folder.mkdir(mode=0o700)
            folders.append(folder)
            for name in ("one", "two"):
                (folder / name).write_bytes(content)
                entries.append(f"{digest}  {group}-{package}/{name}\n")
        dependencies = self.root / "dependencies"
        dependencies.write_text("".join(entries))
        result = self.run_command("create-dependencies", None, dependencies)
        self.assertEqual(result.returncode, 0, result.stderr)
        snapshot = result.stdout.strip()
        self.assertEqual(self.run_command("dependencies", snapshot).returncode, 0)

        # Later byte changes must be refused and preserved, including the second
        # member of a shared parent that has already been validated.
        second = folders[0] / "two"
        second.write_bytes(b"later third-party change\n")
        self.assertNotEqual(self.run_command("dependencies", snapshot).returncode, 0)
        self.assertEqual(second.read_bytes(), b"later third-party change\n")
        second.unlink()
        second.symlink_to(folders[0] / "one")
        self.assertNotEqual(self.run_command("dependencies", snapshot).returncode, 0)
        second.unlink()
        second.write_bytes(content)

        for folder in folders:
            with self.subTest(parent=folder.parent.name):
                folder.chmod(0o755)
                self.assertNotEqual(self.run_command("dependencies", snapshot).returncode, 0)
                folder.chmod(0o700)
                held = folder.with_name("held")
                folder.rename(held)
                folder.symlink_to(held, target_is_directory=True)
                self.assertNotEqual(self.run_command("dependencies", snapshot).returncode, 0)
                folder.unlink()
                held.rename(folder)
        self.assertEqual(self.run_command("dependencies", snapshot).returncode, 0)

        dependencies.write_text(f"{digest}  package-{package}/../one\n")
        result = self.run_command("create-dependencies", None, dependencies)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(self.run_command("dependencies", result.stdout.strip()).returncode, 0)

    def test_missing_or_invalid_record_never_selects_state(self):
        record = self.data / "record"
        original = record.read_bytes()
        for invalid in (
            b"",
            original[:-5],
            original + original,
            original.replace(b"|removed|", b"|unknown|"),
        ):
            record.write_bytes(invalid)
            self.assertNotEqual(self.run_command("read").returncode, 0)
            self.assertEqual(record.read_bytes(), invalid)

    def test_flush_failure_preserves_an_entire_old_or_new_record(self):
        record = self.data / "record"
        old = record.read_bytes()
        real_flush = self.tools / "real-flush"
        (self.tools / "flush").rename(real_flush)
        for failure, expected_budget in (("f", "0"), ("d", "3")):
            record.write_bytes(old)
            (self.tools / "flush").write_text(
                '#!/bin/sh\nif [ "$1" = '
                + failure
                + " ]; then exit 5; fi\n"
                + 'exec "'
                + str(real_flush)
                + '" "$@"\n'
            )
            (self.tools / "flush").chmod(0o700)
            result = self.run_command("change")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("flush_failed", result.stderr)
            self.assertEqual(self.run_command("read").returncode, 0)
            self.assertEqual(record.read_text().split("|")[9], expected_budget)

    def test_service_replacement_preserves_token_and_refuses_corruption(self):
        runtime = self.root / "runtime"
        source = self.root / "package"
        source.mkdir()
        state = (ROOT / "cmu/installer/state.sh").read_text()
        state = state.replace(
            "uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }",
            "uuid() { openssl rand -hex 16; }",
        )
        (source / "state.sh").write_text(state)
        for name in ("api", "flush"):
            (source / name).write_bytes(b"staging fixture\n")
        (source / "files.sha256").write_text(
            "".join(
                hashlib.sha256((source / name).read_bytes()).hexdigest() + "  " + name + "\n"
                for name in ("state.sh", "api", "flush")
            )
        )
        script = (ROOT / "cmu/installer/service.sh").read_text()
        script = script.replace("R=/tmp/open-connect", "R=" + str(runtime))
        # Exercise the real locked staging/token path, stopping before process
        # replacement (the CMU BusyBox listener is qualified on the bench).
        anchor = "service_listen() {\n"
        self.assertEqual(script.count(anchor), 1)
        script = script.replace(anchor, anchor + "return 0\n", 1)
        (source / "service.sh").write_text(script)
        if not shutil.which("flock"):
            (self.tools / "flock").write_text("#!/bin/sh\nexit 0\n")
            (self.tools / "flock").chmod(0o700)

        def run():
            return subprocess.run(
                ["sh", source / "service.sh"],
                capture_output=True,
                text=True,
                timeout=5,
                env={**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]},
            )

        first = run()
        self.assertEqual(first.returncode, 0, first.stderr)
        token = (runtime / "token").read_bytes()
        second = run()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((runtime / "token").read_bytes(), token)
        self.assertEqual(len(list((runtime / "sessions").iterdir())), 2)
        for session in (runtime / "sessions").iterdir():
            self.assertEqual((session / "token").read_bytes(), token)
        (runtime / "token").write_bytes(b"corrupt\n")
        failed = run()
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("token_failed", failed.stderr)
        self.assertEqual((runtime / "token").read_bytes(), b"corrupt\n")
