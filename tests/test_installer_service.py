"""Real Linux flock, BusyBox listener ownership and first-client readiness."""

import fcntl
import hashlib
import http.client
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"

# These staging fixtures deliberately use inert bytes for the helper whose
# inode/mode they inspect. Hash on the host without executing that fake payload.
STAGING_SHA = '\nsha() { local value; value=$(openssl dgst -sha256 < "$1") || return; printf "%s\\n" "${value##* }"; }\n'

BUSYBOX = os.environ.get("OC_TEST_BUSYBOX") or shutil.which("busybox")
HAS_TCPSVD = bool(
    sys.platform == "linux"
    and BUSYBOX
    and shutil.which("flock")
    and "tcpsvd" in subprocess.check_output([BUSYBOX, "--list"], text=True, timeout=3).splitlines()
)


class InstallerUSBStaging(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "oc-usb-ABC123"
        self.source.mkdir(mode=0o700)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir(mode=0o700)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        if shutil.which("gstat"):
            (self.tools / "stat").symlink_to(shutil.which("gstat"))
        self.env = {**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"]}
        service = (ASSETS / "service.sh").read_text()
        service = service.replace("usb:/tmp:oc-usb-", f"usb:{self.root}:oc-usb-") + STAGING_SHA
        (self.source / "service.sh").write_text(service)
        for name in ("api", "flush", "install", "runtime.js"):
            (self.source / name).write_text("verified " + name + "\n")
        self.manifest(self.source)

    def manifest(self, source):
        (source / "files.sha256").unlink(missing_ok=True)
        (source / "files.sha256").write_text(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(source.iterdir())
            )
        )
        for path in source.iterdir():
            path.chmod(0o700 if path.name in ("api", "flush", "install") else 0o600)

    def stage(self, source=None, kind="usb"):
        source = source or self.source
        identity = hashlib.sha256((source / "files.sha256").read_bytes()).hexdigest()
        return subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; umask 077; P=$1; R=$2; . "$P/service.sh"; '
                "uuid() { openssl rand -hex 16; }; "
                'service_files "$3" "$4"; printf "%s\\n" "$runtime"',
                "staging",
                source,
                self.runtime,
                identity,
                kind,
            ],
            capture_output=True,
            text=True,
            timeout=5,
            env=self.env,
        )

    def witness(self, source):
        return {
            p.name: (p.stat().st_ino, p.stat().st_nlink, p.stat().st_mode, p.stat().st_ctime_ns)
            for p in source.iterdir()
        }

    def test_private_packet_survives_scanner_cleanup_with_independent_replacement(self):
        first = self.stage()
        self.assertEqual(first.returncode, 0, first.stderr)
        old = Path(first.stdout.strip())
        originals = {p.name: p.read_bytes() for p in self.source.iterdir()}
        for name in originals:
            self.assertEqual((old / name).stat().st_ino, (self.source / name).stat().st_ino)
        other = self.root / "oc-usb-DEF456"
        shutil.copytree(self.source, other)
        (other / "install").write_text("different verified payload\n")
        self.manifest(other)
        second = self.stage(other)
        self.assertEqual(second.returncode, 0, second.stderr)
        new = Path(second.stdout.strip())
        self.assertNotEqual((old / "token").read_bytes(), (new / "token").read_bytes())
        self.assertEqual((new / "install").read_text(), "different verified payload\n")
        for name in originals:
            self.assertNotEqual((old / name).stat().st_ino, (new / name).stat().st_ino)
        shutil.rmtree(self.source)
        for name, data in originals.items():
            self.assertEqual((old / name).read_bytes(), data)

    def test_sealed_usb_and_held_sources_keep_inodes_modes_and_ctime(self):
        for relative in (
            "data/packages/" + "a" * 64,
            "data/snapshots/" + "b" * 64,
            "mnt/sda1/open-connect",
            "runtime/sessions/session-held",
        ):
            for damaged in (False, True):
                with self.subTest(source=relative, damaged=damaged):
                    source = self.root / relative
                    self.addCleanup(shutil.rmtree, source, ignore_errors=True)
                    shutil.rmtree(source, ignore_errors=True)
                    shutil.copytree(self.source, source)
                    if damaged:
                        (source / "api").write_text("corrupt payload\n")
                    before = self.witness(source)
                    result = self.stage(source)
                    self.assertEqual(self.witness(source), before)
                    if damaged:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("damaged_runtime", result.stderr)
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        staged = Path(result.stdout.strip())
                        for name in before:
                            self.assertNotEqual(
                                (staged / name).stat().st_ino, (source / name).stat().st_ino
                            )
                            self.assertEqual(
                                (staged / name).read_bytes(), (source / name).read_bytes()
                            )
                        shutil.rmtree(staged)
                    shutil.rmtree(source)

    def test_packet_with_a_held_member_gets_fresh_copies_without_touching_donor(self):
        sealed = self.root / "sealed"
        sealed.mkdir(mode=0o700)
        os.link(self.source / "api", sealed / "api")
        before = self.witness(self.source)
        result = self.stage()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.witness(self.source), before)
        staged = Path(result.stdout.strip())
        self.assertNotEqual((staged / "api").stat().st_ino, (sealed / "api").stat().st_ino)
        self.assertEqual((sealed / "api").read_bytes(), (staged / "api").read_bytes())

    def test_nonprivate_packet_does_not_donate_inodes(self):
        self.source.chmod(0o755)
        before = self.witness(self.source)
        result = self.stage()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.witness(self.source), before)
        for name in before:
            self.assertNotEqual(
                (Path(result.stdout.strip()) / name).stat().st_ino,
                (self.source / name).stat().st_ino,
            )

    def test_full_staging_copies_even_a_private_usb_packet(self):
        before = self.witness(self.source)
        result = self.stage(kind="full")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.witness(self.source), before)
        for name in before:
            self.assertNotEqual(
                (Path(result.stdout.strip()) / name).stat().st_ino,
                (self.source / name).stat().st_ino,
            )

    def test_corrupt_packet_removes_only_unpublished_links(self):
        published = self.runtime / "sessions/session-published"
        published.mkdir(parents=True, mode=0o700)
        published.parent.chmod(0o700)
        (published / "reader").write_text("reader still owns this\n")
        (self.runtime / "runtime").symlink_to(published)
        (self.source / "api").write_text("corrupt payload\n")
        result = self.stage()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("damaged_runtime", result.stderr)
        self.assertEqual(list(published.parent.iterdir()), [published])
        self.assertEqual((published / "reader").read_text(), "reader still owns this\n")
        self.assertEqual((self.runtime / "runtime").resolve(), published)
        self.assertTrue(all(p.stat().st_nlink == 1 for p in self.source.iterdir()))

    def test_interrupted_linking_removes_partial_unpublished_directory(self):
        real_ln = shlex.quote(shutil.which("ln"))
        wrapper = self.tools / "ln"
        wrapper.write_text(
            "#!/bin/sh\nfor target; do :; done\n"
            + real_ln
            + ' "$1" "$target/" || exit\nkill -TERM "$PPID"\nexit 1\n'
        )
        wrapper.chmod(0o700)
        result = self.stage()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list((self.runtime / "sessions").iterdir()), [])
        self.assertTrue(all(p.stat().st_nlink == 1 for p in self.source.iterdir()))

    def test_manifest_symlink_refused_without_changing_the_target(self):
        manifest = self.source / "files.sha256"
        sealed = self.root / "sealed-manifest"
        manifest.rename(sealed)
        manifest.symlink_to(sealed)
        before = sealed.stat()
        result = self.stage()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sealed.stat().st_ctime_ns, before.st_ctime_ns)
        self.assertEqual(sealed.stat().st_nlink, 1)
        self.assertEqual(list((self.runtime / "sessions").iterdir()), [])


class InstallerPrivateStaging(unittest.TestCase):
    @unittest.skipUnless(shutil.which("clang"), "Clang required")
    def test_expired_admission_is_reclaimed_by_stop_and_replacement(self):
        for action in ("stop", "start"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                runtime = root / "runtime"
                old = runtime / "sessions/session-old"
                old.mkdir(parents=True, mode=0o700)
                old.parent.chmod(0o700)
                runtime.chmod(0o700)
                source = root / "source"
                source.mkdir(mode=0o700)
                tools = root / "tools"
                tools.mkdir()
                if shutil.which("gstat"):
                    (tools / "stat").symlink_to(shutil.which("gstat"))
                from tests.host_bins import copy_host_flush

                copy_host_flush(tools / "flush")
                for path in (old, source):
                    shutil.copyfile(tools / "flush", path / "flush")
                    (path / "flush").chmod(0o700)
                    service = (
                        (ASSETS / "service.sh")
                        .read_text()
                        .replace("/tmp/open-connect", str(runtime))
                    )
                    service += (
                        "\nservice_lock() { :; }\nstop_listener() { :; }\n"
                        'service_files() { runtime="$R/sessions/session-new"; '
                        'mkdir -m 700 "$runtime"; cp "$P/"* "$runtime/"; }\n'
                        'service_listen() { ln -sfn "$1" "$service_runtime"; }\n'
                    )
                    (path / "service.sh").write_text(service)
                    usb = (
                        (ASSETS / "usb-service.sh")
                        .read_text()
                        .replace("/tmp/open-connect", str(runtime))
                        .replace("/tmp/mnt/data_persist/open-connect", str(root / "absent-data"))
                    )
                    # No native requests/listeners in this host lifetime replay.
                    usb = usb.replace(
                        "for cmd in /proc/[0-9]*/cmdline; do", 'for cmd in "$R"/no-processes/*; do'
                    )
                    (path / "usb-service.sh").write_text(usb)
                    (path / "files.sha256").write_text("fixture manifest\n")
                (old / "closed").touch()
                (old / "admitted").symlink_to("OCUSB1|0|-")
                (runtime / "usb-runtime").symlink_to(old)
                env = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]}
                script = old if action == "stop" else source
                result = subprocess.run(
                    ["sh", script / "usb-service.sh", action],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                deadline = time.monotonic() + 3
                while old.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(old.exists())

    def test_retirement_rejects_unknown_symlink_without_following_admitted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            session = root / "sessions/session-owned"
            session.mkdir(parents=True, mode=0o700)
            tools = root / "tools"
            tools.mkdir()
            if shutil.which("gstat"):
                (tools / "stat").symlink_to(shutil.which("gstat"))
            for name in ("service.sh", "usb-service.sh"):
                text = (ASSETS / name).read_text().replace("/tmp/open-connect", str(root))
                text = text.replace(
                    "for cmd in /proc/[0-9]*/cmdline; do", 'for cmd in "$R"/no-processes/*; do'
                )
                (session / name).write_text(text)
            (session / "closed").touch()
            outside = root / "outside"
            outside.write_text("untouched\n")
            (session / "admitted").symlink_to(outside)
            env = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]}
            for name in ("unknown", ".unknown"):
                unknown = session / name
                unknown.symlink_to(outside)
                result = subprocess.run(["sh", session / "usb-service.sh", "retire"], env=env)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue((session / "closed").exists())
                unknown.unlink()
            subprocess.run(["sh", session / "usb-service.sh", "retire"], env=env, check=True)
            self.assertFalse(session.exists())
            self.assertEqual(outside.read_text(), "untouched\n")

    def test_boot_flush_shares_only_mode700_and_verifies_shared_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / "source"
            source.mkdir(mode=0o700)
            runtime = root / "runtime"
            runtime.mkdir(mode=0o700)
            ignition = runtime / "ignition"
            ignition.mkdir(mode=0o700)
            shared = ignition / "flush"
            shared.write_text("verified flush fixture\n")
            for name in (
                "service.sh",
                "console.sh",
                "preferences.awk",
                "services.tsv",
                "VERSION",
                "api",
                "flush",
                "runtime.js",
                "dialog.js",
                "settings.js",
            ):
                (source / name).write_text("fixture bytes\n")
            shutil.copyfile(shared, source / "flush")
            (source / "service.sh").write_text((ASSETS / "service.sh").read_text() + STAGING_SHA)
            (source / "files.sha256").write_text(
                "".join(
                    hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                    for p in sorted(source.iterdir())
                )
            )
            identity = hashlib.sha256((source / "files.sha256").read_bytes()).hexdigest()
            source_mode = (source / "flush").stat().st_mode & 0o777
            tools = root / "tools"
            tools.mkdir()
            if shutil.which("gstat"):
                (tools / "stat").symlink_to(shutil.which("gstat"))
            for mode, damaged in ((0o700, False), (0o400, False), (0o755, False), (0o700, True)):
                with self.subTest(mode=oct(mode), damaged=damaged):
                    shared.chmod(mode)
                    if damaged:
                        shared.write_text("foreign shared executable\n")
                    result = subprocess.run(
                        [
                            "sh",
                            "-c",
                            'set -eu; umask 077; P=$1; R=$2; . "$P/service.sh"; '
                            "uuid() { openssl rand -hex 16; }; "
                            'service_files "$3" boot; printf "%s\\n" "$runtime"',
                            "staging",
                            source,
                            runtime,
                            identity,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
                    )
                    if damaged:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("damaged_runtime", result.stderr)
                    else:
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        staged = Path(result.stdout.strip()) / "flush"
                        self.assertEqual(
                            staged.stat().st_ino == shared.stat().st_ino, mode == 0o700
                        )
                        self.assertEqual(staged.stat().st_mode & 0o777, 0o700)
                        self.assertEqual(staged.read_bytes(), (source / "flush").read_bytes())
                        token = staged.parent / "token"
                        self.assertEqual(token.stat().st_ino, (runtime / "token").stat().st_ino)
                        self.assertEqual(token.read_bytes(), (runtime / "token").read_bytes())
                    self.assertEqual(shared.stat().st_mode & 0o777, mode)
                    self.assertEqual((source / "flush").read_text(), "verified flush fixture\n")
                    self.assertEqual((source / "flush").stat().st_mode & 0o777, source_mode)
                    self.assertEqual(
                        shared.read_text(),
                        "foreign shared executable\n" if damaged else "verified flush fixture\n",
                    )

    def test_failed_installed_staging_removes_only_its_unpublished_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / "source"
            source.mkdir(mode=0o700)
            runtime = root / "runtime"
            runtime.mkdir(mode=0o700)
            sessions = runtime / "sessions"
            sessions.mkdir(mode=0o700)
            published = sessions / "session-published"
            published.mkdir(mode=0o700)
            (published / "reader").write_text("preserve published bytes\n")
            (runtime / "runtime").symlink_to(published)
            feature = runtime / "feature"
            feature.mkdir(mode=0o700)
            (feature / "runtime.js").write_text("foreign shared bytes\n")
            for name in (
                "service.sh",
                "console.sh",
                "preferences.awk",
                "services.tsv",
                "VERSION",
                "api",
                "flush",
                "install",
                "runtime.js",
                "dialog.js",
                "settings.js",
            ):
                (source / name).write_text("fixture bytes\n")
            (source / "service.sh").write_text((ASSETS / "service.sh").read_text() + STAGING_SHA)
            (source / "files.sha256").write_text(
                "".join(
                    hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                    for p in sorted(source.iterdir())
                )
            )
            tools = root / "tools"
            tools.mkdir()
            if shutil.which("gstat"):
                (tools / "stat").symlink_to(shutil.which("gstat"))
            for kind in ("boot", "full"):
                with self.subTest(kind=kind):
                    manifest = hashlib.sha256((source / "files.sha256").read_bytes()).hexdigest()
                    if kind == "full":
                        (source / "install").unlink()
                    result = subprocess.run(
                        [
                            "sh",
                            "-c",
                            'set -eu; umask 077; P=$1; R=$2; . "$P/service.sh"; '
                            'service_files "$3" "$4"',
                            "test",
                            source,
                            runtime,
                            manifest,
                            kind,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(
                        list(sessions.iterdir()), [published], result.stdout + result.stderr
                    )
                    self.assertEqual(
                        (published / "reader").read_text(), "preserve published bytes\n"
                    )
                    self.assertEqual((runtime / "runtime").resolve(), published)
                    self.assertEqual((feature / "runtime.js").read_text(), "foreign shared bytes\n")


@unittest.skipUnless(
    HAS_TCPSVD and shutil.which("clang"), "Linux /proc, flock, BusyBox tcpsvd and Clang required"
)
class InstallerService(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "oc-usb-ABC123"
        self.source.mkdir(mode=0o700)
        self.runtime = self.root / "runtime"
        self.busybox = str(Path(BUSYBOX).resolve())
        source = (ASSETS / "service.sh").read_text()
        source = source.replace("/tmp/open-connect", str(self.runtime))
        source = source.replace("usb:/tmp:oc-usb-", f"usb:{self.root}:oc-usb-")
        source = source.replace("/bin/busybox", self.busybox)
        source = source.replace('test "$(id -u)" = 0', f'test "$(id -u)" = {os.getuid()}')
        source = source.replace("700:0:0", f"700:{os.getuid()}:{os.getgid()}")
        source = source.replace(" = 36:0:0", f" = 36:{os.getuid()}:{os.getgid()}")
        # Modern host BusyBox replaced the target 1.19.2 timeout's -t syntax.
        source = source.replace("timeout -t 180", "timeout 180")
        (self.source / "service.sh").write_text(source)
        (self.source / "api").write_text(
            "#!/usr/bin/python3\n"
            "import json,sys\nfrom pathlib import Path\n"
            "while sys.stdin.buffer.readline().strip(): pass\n"
            "sess=Path(sys.argv[1]).parent\n"
            "body=json.dumps({'token':Path(sys.argv[1]).read_text().strip(),"
            "'backend':(sess/'install').read_text() if (sess/'install').exists() else 'native-boot\\n'}).encode()\n"
            "sys.stdout.buffer.write(b'HTTP/1.0 200 OK\\r\\nContent-Length: '+"
            "str(len(body)).encode()+b'\\r\\n\\r\\n'+body)\n"
        )
        from tests.host_bins import copy_host_flush

        copy_host_flush(self.source / "flush")
        (self.source / "install").write_text("backend-one\n")
        for name in (
            "console.sh",
            "preferences.awk",
            "services.tsv",
            "sm-profile.awk",
            "VERSION",
            "runtime.js",
            "dialog.js",
            "settings.js",
        ):
            shutil.copyfile(ASSETS / name, self.source / name)
        usb = (
            (ASSETS / "usb-service.sh").read_text().replace("/tmp/open-connect", str(self.runtime))
        )
        usb = usb.replace("/tmp/mnt/data_persist/open-connect", str(self.root / "data"))
        (self.source / "usb-service.sh").write_text(usb)
        self.manifest()
        self.addCleanup(self.stop_listener)

    def manifest(self):
        for item in self.source.iterdir():
            item.chmod(0o700 if item.name in ("api", "flush", "install") else 0o600)
        (self.source / "files.sha256").write_text(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(self.source.iterdir())
                if p.name != "files.sha256"
            )
        )

    def stop_listener(self):
        for name in ("listener", "usb-listener"):
            record = self.runtime / name
            if not record.exists():
                continue
            pid, start, session = record.read_text().split()
            proc = Path("/proc") / pid
            try:
                fields = (proc / "stat").read_text().split()
                args = (proc / "cmdline").read_bytes().split(b"\0")
                if fields[21] == start and (session + "/api").encode() in args:
                    os.kill(int(pid), signal.SIGTERM)
            except (FileNotFoundError, ProcessLookupError):
                pass

    def invoke(self, env=None):
        return subprocess.run(
            ["sh", self.source / "usb-service.sh"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

    def boot_command(self):
        return (
            'set -eu; P="$1"; R="$2"; . "$P/service.sh"; '
            'service_lock boot; service_stage boot "$(sha "$P/files.sha256")"'
        )

    def boot(self):
        return subprocess.run(
            ["sh", "-c", self.boot_command(), "test", self.source, self.runtime],
            capture_output=True,
            text=True,
            timeout=5,
        )

    def client(self, port=15557):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.request("GET", "/")
            reply = conn.getresponse()
            self.assertEqual(reply.status, 200)
            return json.loads(reply.read())
        finally:
            conn.close()

    def test_boot_closure_omits_build_files_and_shares_verified_ui_inodes(self):
        self.runtime.mkdir(mode=0o700)
        feature = self.runtime / "feature"
        feature.mkdir(mode=0o700)
        for name in ("runtime.js", "dialog.js", "settings.js", "service.sh", "flush"):
            shutil.copyfile(self.source / name, feature / name)
            (feature / name).chmod(0o700 if name == "flush" else 0o600)
        flush_source = (self.source / "flush").read_bytes()
        for name in ("LICENSE", "boot-select", "native.bin"):
            (self.source / name).write_text("not needed by the installed listener\n")
        self.manifest()
        result = self.boot()
        self.assertEqual(result.returncode, 0, result.stderr)
        session = (self.runtime / "runtime").resolve()
        for name in (
            "LICENSE",
            "boot-select",
            "native.bin",
            "install",
            "sm-profile.awk",
            "preferences.awk",
            "services.tsv",
        ):
            self.assertFalse((session / name).exists())
        for name in ("runtime.js", "dialog.js", "settings.js", "service.sh", "flush"):
            self.assertEqual((session / name).stat().st_ino, (feature / name).stat().st_ino)
        self.assertEqual((session / "flush").stat().st_mode & 0o777, 0o700)
        self.assertEqual((feature / "flush").stat().st_mode & 0o777, 0o700)
        self.assertEqual((feature / "flush").read_bytes(), flush_source)
        self.assertEqual((self.source / "flush").read_bytes(), flush_source)
        self.assertEqual((self.source / "flush").stat().st_mode & 0o777, 0o700)
        self.assertEqual(
            (session / "files.sha256").read_bytes(), (self.source / "files.sha256").read_bytes()
        )
        self.assertEqual(self.client(15555)["backend"], "native-boot\n")

    def legacy_selected_client(self):
        self.runtime.mkdir(mode=0o700)
        (self.runtime / "selected").write_text("a" * 64 + "\n")

    def test_usb_before_delayed_worker_keeps_endpoints_independent(self):
        worker, _, _ = self.installed_worker()
        process = subprocess.Popen(
            ["sh", worker, "boot"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            result = self.invoke()
            self.assertEqual(result.returncode, 0, result.stderr)
            before = (self.runtime / "usb-listener").read_bytes()
            out, error = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, (out, error))
            self.assertEqual((self.runtime / "usb-listener").read_bytes(), before)
            self.assertEqual(self.client()["backend"], "backend-one\n")
            self.assertEqual(self.client(15555)["backend"], "native-boot\n")
            self.assertNotEqual(
                (self.runtime / "token").read_text(),
                (Path(result.stdout.strip()) / "token").read_text(),
            )
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=3)

    def test_installed_port_collision_does_not_block_usb(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 15555))
            occupied.listen()
            result = self.invoke()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.client()["backend"], "backend-one\n")

    def test_boot_closure_rejects_wrong_shared_bytes_before_listener(self):
        self.runtime.mkdir(mode=0o700)
        feature = self.runtime / "feature"
        feature.mkdir(mode=0o700)
        shared = feature / "runtime.js"
        shared.write_text("foreign bytes\n")
        shared.chmod(0o400)
        result = self.boot()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "listener").exists())
        self.assertEqual(shared.read_text(), "foreign bytes\n")
        self.assertEqual(shared.stat().st_mode & 0o777, 0o400)
        self.assertEqual(list((self.runtime / "sessions").iterdir()), [])

    def test_usb_cancel_leaves_installed_endpoint_token_and_bytes_unchanged(self):
        result = self.boot()
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = (self.runtime / "runtime").resolve()
        record = (self.runtime / "listener").read_bytes()
        token = (self.runtime / "token").read_bytes()
        started = self.invoke()
        self.assertEqual(started.returncode, 0, started.stderr)
        usb = Path(started.stdout.strip())
        stopped = subprocess.run(
            ["sh", usb / "usb-service.sh", "stop"], capture_output=True, text=True, timeout=5
        )
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertFalse((self.runtime / "usb-listener").exists())
        self.assertEqual((self.runtime / "runtime").resolve(), installed)
        self.assertEqual((self.runtime / "listener").read_bytes(), record)
        self.assertEqual((self.runtime / "token").read_bytes(), token)
        self.assertEqual(self.client(15555)["backend"], "native-boot\n")

    def test_ready_usb_shares_verified_packet_and_each_insertion_has_its_own_token(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        old = Path(first.stdout.strip())
        token = (old / "token").read_text().strip()
        self.assertEqual(self.client(), {"token": token, "backend": "backend-one\n"})
        for line in (self.source / "files.sha256").read_text().splitlines():
            digest, name = line.split()
            self.assertEqual(hashlib.sha256((old / name).read_bytes()).hexdigest(), digest)
            self.assertEqual((old / name).stat().st_ino, (self.source / name).stat().st_ino)
        # Another scan starts with another verified private staging directory.
        other = self.root / "oc-usb-DEF456"
        shutil.copytree(self.source, other)
        self.source = other
        (other / "install").write_text("backend-two\n")
        self.manifest()
        second = self.invoke()
        self.assertEqual(second.returncode, 0, second.stderr)
        new = Path(second.stdout.strip())
        self.assertNotEqual((new / "token").read_text().strip(), token)
        self.assertEqual(self.client()["backend"], "backend-two\n")

    def test_boot_starts_independently_of_live_usb(self):
        self.assertEqual(self.invoke().returncode, 0)
        before = (self.runtime / "usb-listener").read_bytes()
        result = self.boot()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.runtime / "usb-listener").read_bytes(), before)
        self.assertEqual(self.client()["backend"], "backend-one\n")
        self.assertEqual(self.client(15555)["backend"], "native-boot\n")

    def test_closed_generation_keeps_bytes_until_request_child_drains(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        old = Path(first.stdout.strip())
        token = (old / "token").read_text().strip()
        with socket.create_connection(("127.0.0.1", 15557), timeout=3) as reader:
            reader.sendall(b"GET / HTTP/1.0\r\n")
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                pending = False
                for cmd in Path("/proc").glob("[0-9]*/cmdline"):
                    try:
                        args = cmd.read_bytes().split(b"\0")
                    except OSError:
                        continue
                    if args[:2] == [b"/usr/bin/python3", str(old / "api").encode()]:
                        pending = True
                        break
                if pending:
                    break
                time.sleep(0.01)
            else:
                self.fail("request child did not start")
            other = self.root / "oc-usb-DEF456"
            shutil.copytree(self.source, other)
            self.source = other
            (other / "install").write_text("backend-two\n")
            self.manifest()
            second = self.invoke()
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertTrue((old / "closed").is_file())
            self.assertEqual((old / "install").read_text(), "backend-one\n")
            self.assertEqual(self.client()["backend"], "backend-two\n")
            # Retirement must still see this old child after its listener stops.
            time.sleep(1.1)
            self.assertTrue(old.is_dir())
            reader.sendall(b"\r\n")
            with reader.makefile("rb") as response_file:
                response = response_file.read()
            self.assertEqual(
                json.loads(response.split(b"\r\n\r\n", 1)[1]),
                {"token": token, "backend": "backend-one\n"},
            )
        deadline = time.monotonic() + 3
        while old.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(old.exists())

    def installed_worker(self):
        data = self.root / "data"
        data.mkdir(mode=0o700)
        (data / "packages").mkdir(mode=0o700)
        service = self.source / "service.sh"
        service.write_text(
            service.read_text().replace("/tmp/mnt/data_persist/open-connect", str(data))
        )
        self.manifest()
        package_id = hashlib.sha256((self.source / "files.sha256").read_bytes()).hexdigest()
        package = data / "packages" / package_id
        shutil.copytree(self.source, package)
        boot = "12345678-1234-1234-1234-123456789abc"
        current = "c" * 64
        (data / "record").write_text(
            f"OC1|active|{'a' * 32}|{package_id}|{'b' * 64}|{current}|-|-|-|2|-|{boot}|-\n"
        )
        (data / "record").chmod(0o600)
        self.runtime.mkdir(mode=0o700)
        (self.runtime / "lock").touch(mode=0o600)
        (self.runtime / "selected").write_text(current + "\n")
        (self.runtime / "boot-id").symlink_to(boot)
        feature = self.runtime / "feature"
        feature.mkdir(mode=0o700)
        worker = feature / "service.sh"
        shutil.copyfile(service, worker)
        return worker, package, data

    def test_sm_worker_verifies_installed_source_and_serves_settings(self):
        worker, _, _ = self.installed_worker()
        result = subprocess.run(["sh", worker, "boot"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.client(15555)["backend"], "native-boot\n")
        self.assertTrue((self.runtime / "selected").is_file())

    def test_sm_worker_skips_deferral_sleep_only_for_installed_notice(self):
        for notice, expect_sleep in (("installed", False), ("-", True)):
            with self.subTest(notice=notice):
                self.stop_listener()
                shutil.rmtree(self.runtime, ignore_errors=True)
                shutil.rmtree(self.root / "data", ignore_errors=True)
                worker, _, data = self.installed_worker()
                record = (data / "record").read_text()
                (data / "record").write_text(record.rsplit("|", 1)[0] + "|" + notice + "\n")
                tools = self.root / f"tools-{notice}"
                tools.mkdir(mode=0o700, exist_ok=True)
                sleeps = self.root / f"sleeps-{notice}"
                fake_sleep = tools / "sleep"
                fake_sleep.write_text(
                    f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> {shlex.quote(str(sleeps))}\nexit 0\n"
                )
                fake_sleep.chmod(0o700)
                env = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]}
                result = subprocess.run(
                    ["sh", worker, "boot"], capture_output=True, text=True, timeout=10, env=env
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(sleeps.exists(), expect_sleep)
                if expect_sleep:
                    self.assertEqual(sleeps.read_text().strip(), "4")
                self.stop_listener()

    def test_sm_worker_refuses_missing_malformed_or_stale_boot_identity(self):
        worker, _, _ = self.installed_worker()
        marker = self.runtime / "boot-id"
        for value in (
            None,
            "invalid",
            "12345678-1234-1234-1234-123456789abc\n",
            "87654321-1234-1234-1234-123456789abc",
        ):
            with self.subTest(value=value):
                marker.unlink(missing_ok=True)
                if value is not None:
                    marker.symlink_to(value)
                result = subprocess.run(["sh", worker, "boot"], capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertFalse((self.runtime / "listener").exists())
                self.assertFalse((self.runtime / "runtime").exists())

    def test_sm_worker_refuses_corrupt_library_before_sourcing(self):
        worker, package, _ = self.installed_worker()
        marker = self.root / "unverified-ran"
        with (package / "service.sh").open("a") as target:
            target.write("\ntouch " + str(marker) + "\n")
        result = subprocess.run(["sh", worker, "boot"], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())
        self.assertFalse((self.runtime / "listener").exists())

    def test_sm_worker_does_not_replace_a_preceding_usb_listener(self):
        worker, _, _ = self.installed_worker()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        before = (self.runtime / "usb-listener").read_bytes()
        result = subprocess.run(["sh", worker, "boot"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.runtime / "usb-listener").read_bytes(), before)
        self.assertEqual(self.client()["backend"], "backend-one\n")
        self.assertEqual(self.client(15555)["backend"], "native-boot\n")

    def test_ash_sm_worker_refuses_missing_or_symlinked_selection(self):
        worker, _, _ = self.installed_worker()
        selected = self.runtime / "selected"
        selected.unlink()
        for symlink in (False, True):
            with self.subTest(symlink=symlink):
                if symlink:
                    selected.symlink_to(self.source / "service.sh")
                result = subprocess.run(
                    [self.busybox, "sh", worker, "boot"], capture_output=True, timeout=10
                )
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertFalse((self.runtime / "listener").exists())
                self.assertFalse((self.runtime / "runtime").exists())

    def test_ash_sm_worker_refuses_nonprivate_prerequisite_directories(self):
        worker, package, data = self.installed_worker()
        for folder in (data, self.runtime, package):
            with self.subTest(folder=folder.name):
                folder.chmod(0o755)
                result = subprocess.run(
                    [self.busybox, "sh", worker, "boot"], capture_output=True, timeout=10
                )
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertFalse((self.runtime / "listener").exists())
                folder.chmod(0o700)

    def recovery_files(self):
        return subprocess.run(
            [
                "sh",
                "-c",
                'set -eu; P=$1; R=$2; . "$P/service.sh"; '
                'service_lock usb; service_files "$(sha "$P/files.sha256")"; printf "%s\\n" "$runtime"',
                "test",
                self.source,
                self.runtime,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_recovery_files_preserve_existing_usb_listener(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        before = (self.runtime / "usb-listener").read_bytes()
        result = self.recovery_files()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((Path(result.stdout.strip()) / "service.sh").is_file())
        self.assertEqual((self.runtime / "usb-listener").read_bytes(), before)
        self.assertEqual(self.client()["backend"], "backend-one\n")

    def test_recovery_files_do_not_require_an_available_port(self):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 15555))
            listener.listen()
            result = self.recovery_files()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((Path(result.stdout.strip()) / "install").is_file())
        self.assertFalse((self.runtime / "runtime").exists())
        self.assertFalse((self.runtime / "listener").exists())

    def test_foreign_socket_causes_failure_without_publishing_new_runtime(self):
        self.runtime.mkdir(mode=0o700)
        old = self.root / "old"
        old.mkdir()
        (self.runtime / "runtime").symlink_to(old)
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 15557))
            listener.listen()
            started = time.monotonic()
            result = self.invoke()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("listener_start_failed", result.stderr)
            self.assertLess(time.monotonic() - started, 3)
            self.assertEqual((self.runtime / "runtime").resolve(), old)
            self.assertFalse((self.runtime / "usb-listener").exists())

    def test_corrupt_shared_packet_refuses_and_removes_unpublished_links(self):
        tools = self.root / "tools"
        tools.mkdir()
        link = tools / "ln"
        link.write_text(
            "#!/bin/sh\n" + shutil.which("ln") + ' "$@" || exit\n'
            "for target; do :; done\n"
            'if test -d "$target"; then printf "corrupt" >> "$target/api"; fi\n'
        )
        link.chmod(0o700)
        result = self.invoke({**os.environ, "PATH": str(tools) + ":" + os.environ["PATH"]})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("damaged_runtime", result.stderr)
        self.assertFalse((self.runtime / "usb-runtime").exists())
        self.assertFalse((self.runtime / "usb-listener").exists())
        self.assertEqual(list((self.runtime / "sessions").iterdir()), [])

    def test_boot_refuses_real_lock_contention_without_runtime_effects(self):
        self.runtime.mkdir(mode=0o700)
        with (self.runtime / "lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            started = time.monotonic()
            result = self.boot()
            self.assertLess(time.monotonic() - started, 1)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("busy", result.stderr)
            self.assertFalse((self.runtime / "runtime").exists())

    def test_usb_waits_for_existing_operation_lock_before_staging(self):
        self.runtime.mkdir(mode=0o700)
        with (self.runtime / "lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            process = subprocess.Popen(
                ["sh", self.source / "usb-service.sh"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(0.15)
            self.assertIsNone(process.poll())
            self.assertFalse((self.runtime / "usb-runtime").exists())
            fcntl.flock(lock, fcntl.LOCK_UN)
            out, err = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, err)
            self.assertTrue(out.strip())
            self.assertEqual(self.client()["backend"], "backend-one\n")

    def assert_interrupted_start(self, needle):
        script = self.source / "service.sh"
        script.write_text(
            script.read_text().replace(needle, self.busybox + " usleep 500000\n" + needle, 1)
        )
        self.manifest()
        process = subprocess.Popen(
            ["sh", self.source / "usb-service.sh"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if any(
                fields[1] == "0100007F:3CC5" and fields[3] == "0A"
                for line in Path("/proc/net/tcp").read_text().splitlines()[1:]
                if len(fields := line.split()) > 3
            ):
                break
            time.sleep(0.01)
        else:
            process.kill()
            self.fail("new listener did not reach the interrupted-start window")
        self.assertFalse((self.runtime / "usb-runtime").exists())
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=3)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse((self.runtime / "usb-runtime").exists())
        self.assertFalse((self.runtime / "usb-listener").exists())
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", 15557))

    def test_signal_during_unpublished_start_reaps_child_and_cannot_publish_later(self):
        self.assert_interrupted_start("service_tick; deadline=")

    def test_parent_term_between_fork_and_pid_capture_reaps_unpublished_child(self):
        self.assert_interrupted_start("pid=$!")

    def test_term_at_ready_handoff_is_not_forgotten(self):
        script = self.source / "service.sh"
        needle = "trap - EXIT HUP INT TERM\nunset p_pid p_st p_wk p_can p_pub"
        source = script.read_text()
        self.assertEqual(source.count(needle), 1)
        script.write_text(source.replace(needle, self.busybox + " usleep 500000\n" + needle, 1))
        self.manifest()
        process = subprocess.Popen(
            ["sh", self.source / "usb-service.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        deadline = time.monotonic() + 2
        while not (self.runtime / "usb-runtime").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue((self.runtime / "usb-runtime").exists())
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=3)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse((self.runtime / "usb-runtime").exists())
        self.assertFalse((self.runtime / "usb-listener").exists())
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", 15557))
