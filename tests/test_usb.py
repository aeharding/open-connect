"""Check the real Make/shell build and the staged USB entry, without a CMU."""

import hashlib
import os
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cmu/installer"
TRIGGER = next((ASSETS / "usb-root").glob("*.up")).name
STATIC = (
    "run.sh",
    "session.sh",
    "service.sh",
    "usb-service.sh",
    "loader.js",
    "runtime.js",
    "maintenance.js",
    "dialog.js",
    "settings.js",
    "carplay.js",
    "console.sh",
    "startup-hook.sh",
    "startup-join.sh",
    "system-hook.js",
    "wireless.sh",
    "preferences.awk",
    "services.tsv",
    "sm-profile.awk",
    "defer-gap2.sh",
    "defer-nav.sh",
    "ui-profile.awk",
    "ui-modules.tsv",
    "base-logging.js",
    "wireless-device.awk",
    "VERSION",
    "KENATIA-LICENSE",
)
COMPILED = (
    "api",
    "install",
    "flush",
    "boot-select",
    "ignition",
    "touch-disable.so",
    "native.bin",
    "branch.bin",
    "sizes.bin",
    "layout.bin",
    "mmui-path.bin",
    "mmui-sizes.bin",
    "mmui-length.bin",
    "mmui-pointer.bin",
    "mmui-count-pointer.bin",
    "vui-path.bin",
)
PAYLOAD = (*STATIC, *COMPILED, "layout.txt", "LICENSE")


class UsbBuild(unittest.TestCase):
    @unittest.skipUnless(shutil.which("clang"), "Clang required")
    def test_post_restart_scan_only_suppresses_the_observed_selected_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            registry, durable, work = (root / n for n in ("registry", "durable", "work"))
            feature = registry / "feature"
            for folder in (feature, durable, work):
                folder.mkdir(parents=True)
            boot = "12345678-1234-1234-1234-123456789abc"
            current = "c" * 64
            (registry / "selected").write_text(current + "\n")
            (registry / "boot").write_text(boot + "\n")
            index = feature / "index.html"
            page = '<meta name="open-connect-notice" content="installed">\n'
            trailer = f"<!-- OCUSB1|{boot}|1-2:7; -->\n"
            index.write_text(page + trailer)
            manifest = "a" * 64 + "  VERSION\n"
            (work / "files.sha256").write_text(manifest)
            installed = manifest + "b" * 64 + "  INSTANCE\n"
            package = hashlib.sha256(installed.encode()).hexdigest()
            destination = durable / "packages" / package
            destination.mkdir(parents=True)
            (destination / "files.sha256").write_text(installed)
            # Record validation and lock acquisition are tested by their own
            # maintained suites; substitute only those upstream platform facts.
            from tests.host_bins import copy_host_flush

            copy_host_flush(work / "flush")
            facts = durable / "facts"

            def record(phase="active", selected=current, selected_boot=boot):
                facts.write_text(
                    f"R_PHASE={phase}; R_CURRENT={selected}; R_BOOT={selected_boot}; "
                    f"R_BACKEND={package}; R_NOTICE=installed\n"
                )

            record()
            sysroot = root / "sys"
            usb = sysroot / "devices/1-2"
            usb.mkdir(parents=True)
            (usb / "idVendor").write_text("0781\n")
            (usb / "devnum").write_text("7\n")
            enumerated = sysroot / "bus/usb/devices"
            enumerated.mkdir(parents=True)
            (enumerated / "1-2").symlink_to(usb)
            block = usb / "host/block/sda/sda1"
            block.mkdir(parents=True)
            block_class = sysroot / "class/block"
            block_class.mkdir(parents=True)
            (block_class / "sda1").symlink_to(block)
            mounts = root / "mounts"
            mounts.write_text("/dev/sda1 /tmp/mnt/sda1 vfat ro 0 0\n")
            module = (ASSETS / "service.sh").read_text()
            module = module.replace("/sys/", str(sysroot) + "/").replace(
                "/proc/mounts", str(mounts)
            )
            (work / "service.sh").write_text(
                module + '\nfile() { test -f "$1" && test ! -L "$1"; }; '
                'stat() { printf "%s 8\\n" "$(wc -c < "$3")"; }; '
                'private_dir() { test -d "$1"; }; '
                'current_boot_id() { cat "$R/boot"; }; '
                'record_read() { . "$D/facts"; }; '
                "service_lock() { :; }\n"
            )
            source = (ASSETS / "session.sh").read_text().split("navigate()", 1)[0]
            source = source.replace("/tmp/open-connect", str(registry)).replace(
                "/tmp/mnt/data_persist/open-connect", str(durable)
            )
            runner = root / "runner.sh"
            runner.write_text(source + "\nif post_restart; then exit 0; else exit 1; fi\n")

            def suppressed():
                return (
                    subprocess.run(
                        ["sh", runner, work, "/tmp/mnt/sda1/open-connect"],
                        capture_output=True,
                        timeout=5,
                    ).returncode
                    == 0
                )

            self.assertTrue(suppressed())
            # Done clears the mutable record notice; the rendered boot notice
            # and frozen attachment still describe this continuation.
            with facts.open("a") as stream:
                stream.write("R_NOTICE=-\n")
            self.assertTrue(suppressed())
            # A failed observation before Done cannot be replaced by the next
            # insertion's attachment evidence after the notice is acknowledged.
            index.write_text(page)
            self.assertFalse(suppressed())
            self.assertEqual(index.read_text(), page)
            index.write_text(page + trailer)
            (usb / "devnum").write_text("8\n")
            self.assertFalse(suppressed())  # Deliberate reinsertion.
            (usb / "devnum").write_text("7\n")
            for invalid in ("-", "1-2:8;", "1-2:bad;"):
                index.write_text(page + trailer.replace("1-2:7;", invalid))
                self.assertFalse(suppressed())
            index.write_text(page + trailer)
            (work / "files.sha256").write_text("d" * 64 + "  VERSION\n")
            self.assertFalse(suppressed())  # A different maintenance package.
            (work / "files.sha256").write_text(manifest)
            for phase, selected, selected_boot in (
                ("fallback", current, boot),
                ("active", "d" * 64, boot),
                ("active", current, "00000000-0000-0000-0000-000000000000"),
            ):
                record(phase, selected, selected_boot)
                self.assertFalse(suppressed())
            record()
            index.write_text(page.replace("installed", "-") + trailer)
            self.assertFalse(suppressed())
            index.write_text(page + trailer)
            mounts.write_text("/dev/sdb1 /tmp/mnt/sda1 vfat ro 0 0\n")
            self.assertFalse(suppressed())  # The mount name is not USB identity.

    def test_usb_observation_freezes_attachment_and_rejects_bad_trailers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            feature = root / "feature"
            feature.mkdir()
            index = feature / "index.html"
            devices = root / "sys/bus/usb/devices"
            devices.mkdir(parents=True)
            boot = "12345678-1234-1234-1234-123456789abc"
            module = root / "functions.sh"
            module.write_text(
                (ASSETS / "service.sh").read_text().replace("/sys/", str(root / "sys") + "/")
            )
            # Only platform facts are substituted; the actual reader/writer runs.
            prelude = (
                '. "$1"; R=$2; '
                f"current_boot_id() {{ echo {boot}; }}; "
                'file() { test -f "$1" && test ! -L "$1"; }; '
                'stat() { printf "%s %s\\n" "$(wc -c < "$3")" 8; }; '
            )

            def observe():
                return subprocess.run(
                    ["sh", "-c", prelude + "service_usb_observe", "test", module, root],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

            index.write_text("<html>completion</html>\n")
            self.assertEqual(observe().stdout, "-\n")
            empty = index.read_bytes()
            usb = devices / "1-2.3"
            usb.mkdir()
            (usb / "devnum").write_text("7\n")
            self.assertEqual(observe().stdout, "-\n")
            self.assertEqual(index.read_bytes(), empty)
            index.write_text("<html>completion</html>\n")
            self.assertEqual(observe().stdout, "1-2.3:7;\n")
            saved = index.read_bytes()
            (usb / "devnum").write_text("8\n")
            self.assertEqual(observe().stdout, "1-2.3:7;\n")
            self.assertEqual(index.read_bytes(), saved)
            valid = f"<!-- OCUSB1|{boot}|1-2.3:7; -->\n"
            for trailer in (
                valid + valid,
                valid[:-5],
                valid.replace(boot, "00000000-0000-0000-0000-000000000000"),
                valid.replace("1-2.3:7;", "1-2.3:x;"),
                valid + "<!-- OCUSB1",
                valid + "other bytes\n",
                "prefix" + valid,
            ):
                with self.subTest(trailer=trailer):
                    index.write_text("<html></html>\n" + trailer)
                    before = index.read_bytes()
                    self.assertNotEqual(observe().returncode, 0)
                    self.assertEqual(index.read_bytes(), before)
            for body in ("x" * 4090, "<html></html>\n"):
                index.write_text(body)
                if len(body) < 4090:
                    (usb / "devnum").write_text("unavailable\n")
                self.assertNotEqual(observe().returncode, 0)
                self.assertEqual(index.read_text(), body)

    def test_session_teardown_preserves_the_frontend_owner(self):
        cases = (
            "done",
            "done-and-removed",
            "removed",
            "superseded",
            "preclosed",
            "removed-at-publication",
            "superseded-at-publication",
        )
        for receiver, reason in [(v, r) for v in (False, True) for r in cases] + [
            (True, "final-suppressed")
        ]:
            no_entry = reason in (
                "preclosed",
                "removed-at-publication",
                "superseded-at-publication",
                "final-suppressed",
            )
            expected_calls = int(not receiver and not no_entry)
            with (
                self.subTest(receiver=receiver, reason=reason),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp).resolve()
                work, runtime, media, bin_dir = (
                    root / n for n in ("work", "session-abc123", "media", "bin")
                )
                for path in (work, runtime, media, bin_dir):
                    path.mkdir()
                registry = root / "registry"
                registry.mkdir()
                if receiver:
                    feature = registry / "feature"
                    feature.mkdir()
                    (feature / "runtime.js").write_text("/* OC_USB_OFFER_V1: receiver */\n")
                (registry / "usb-runtime").symlink_to(runtime)
                (registry / "usb-listener").write_text(f"1 2 {runtime}\n")
                (runtime / "token").write_text("a" * 32 + "\n")
                (media / "run.sh").touch()
                service = 'service_owns_listener() { test "$4" = 15557; }\nservice_lock() { :; }\n'
                for path in (work / "service.sh", runtime / "service.sh"):
                    path.write_text(service)
                usb_service = (
                    'if test "${1:-}" = stop; then echo stop >> "$OC_TEST_EVENTS";\n'
                    'else case "$OC_TEST_REASON" in\n'
                    ' preclosed) : > "$OC_TEST_RUNTIME/closed";;\n'
                    ' removed-at-publication) rm "$OC_TEST_MEDIA/run.sh";;\n'
                    ' superseded-at-publication) ln -sfn "$OC_TEST_OTHER" "$OC_TEST_REGISTRY/usb-runtime";;\n'
                    'esac; echo "$OC_TEST_RUNTIME"; fi\n'
                )
                for path in (work / "usb-service.sh", runtime / "usb-service.sh"):
                    path.write_text(usb_service)
                stub = bin_dir / "dbus-send"
                stub.write_text(
                    "#!/bin/sh\n"
                    'printf "%s\\n" "$*" >> "$OC_TEST_CALLS"\n'
                    'case "$*" in *loadScript*)\n'
                    ' case "$OC_TEST_REASON" in\n'
                    '  done|done-and-removed) : > "$OC_TEST_RUNTIME/closed";;\n'
                    " esac\n"
                    ' case "$OC_TEST_REASON" in\n'
                    '  removed|done-and-removed) rm "$OC_TEST_MEDIA/run.sh";;\n'
                    '  superseded) ln -sfn "$OC_TEST_OTHER" "$OC_TEST_REGISTRY/usb-runtime";;\n'
                    " esac;;\n"
                    "esac\n"
                )
                stub.chmod(0o700)
                sleep = bin_dir / "sleep"
                sleep.write_text(
                    '#!/bin/sh\ncase "$OC_TEST_REASON" in\n'
                    'done|done-and-removed) : > "$OC_TEST_RUNTIME/closed";;\n'
                    'removed) rm "$OC_TEST_MEDIA/run.sh";;\n'
                    'superseded) ln -sfn "$OC_TEST_OTHER" "$OC_TEST_REGISTRY/usb-runtime";;\n'
                    "*) exit 1;;\nesac\n"
                )
                sleep.chmod(0o700)
                logger = bin_dir / "logger"
                logger.write_text("#!/bin/sh\nexit 0\n")
                logger.chmod(0o700)
                script = root / "session.sh"
                body = (ASSETS / "session.sh").read_text()
                if reason == "final-suppressed":
                    begin, end = body.index("post_restart() ("), body.index("navigate()")
                    body = (
                        body[:begin] + 'post_restart() { test "${1:-}" = locked; }\n' + body[end:]
                    )
                script.write_text(body.replace("/tmp/open-connect", str(registry)))
                calls, events = root / "calls", root / "events"
                env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"])
                env.update(
                    {
                        "OC_TEST_REASON": reason,
                        "OC_TEST_RUNTIME": str(runtime),
                        "OC_TEST_MEDIA": str(media),
                        "OC_TEST_REGISTRY": str(registry),
                        "OC_TEST_OTHER": str(root / "successor"),
                        "OC_TEST_CALLS": str(calls),
                        "OC_TEST_EVENTS": str(events),
                    }
                )
                subprocess.run(
                    ["sh", str(script), str(work), str(media)], env=env, check=True, timeout=5
                )
                sent = calls.read_text().splitlines() if calls.exists() else []
                self.assertEqual(len(sent), expected_calls)
                if sent:
                    self.assertIn("loadScript", sent[0])
                    self.assertIn("oc-maintenance-loader", sent[0])
                    self.assertNotIn("cancelUSB", sent[0])
                    self.assertIn("OpenConnectUSBStart(entry)", sent[0])
                if receiver and not no_entry:
                    self.assertEqual(
                        (runtime / "offer").read_text(), runtime.name + "|" + "a" * 32 + "\n"
                    )
                else:
                    self.assertFalse((runtime / "offer").exists())
                self.assertEqual(events.read_text(), "stop\n")
                self.assertFalse(work.exists())

    def test_packager_refuses_an_extra_ui_page_before_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "cmu/installer"
            assets.mkdir(parents=True)
            out = root / "out"
            out.mkdir()
            (out / "api").touch()
            (assets / "dialog.js").write_bytes(b" " * 8193)
            result = subprocess.run(
                ["sh", ROOT / "tooling/package-usb.sh", out],
                cwd=root,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("dialog.js exceeds its RAM page budget", result.stderr)
            self.assertFalse((out / "usb").exists())

    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_ui_lifetime_and_cancel_during_loading(self):
        for name in ("usb-loader",):
            subprocess.run(
                [
                    "node",
                    str(ROOT / f"tests/fixtures/{name}.js"),
                    str(ASSETS / "loader.js"),
                ],
                check=True,
            )

    def test_trigger_only_selects_our_package(self):
        self.assertLessEqual(len(TRIGGER), 255)
        self.assertFalse(set(TRIGGER) & set(r'\/:*?"<>|'))
        self.assertTrue(all(32 <= ord(c) < 127 for c in TRIGGER))

        def run_trigger(files):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for name, body in files:
                    target = root / "tmp/mnt" / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(body + "\n")
                command = TRIGGER[2:-4].replace("S=${HOME%root}", "S=/")
                command = command.replace("P=${S}tmp", "P=" + shlex.quote(temp) + "${S}tmp")
                return subprocess.run(["sh", "-c", command], text=True, capture_output=True)

        # Single matching Open Connect USB alongside an unrelated run.sh executes our package.
        single = run_trigger(
            [
                ("sda1/run.sh", "echo WRONG"),
                ("sdb1/open-connect/run.sh", "echo OPEN_CONNECT"),
            ]
        )
        self.assertEqual(single.returncode, 0, single.stderr)
        self.assertEqual(single.stdout, "OPEN_CONNECT\n")

        # Ambiguous multi-USB (two Open Connect drives inserted at once) must refuse both.
        ambiguous = run_trigger(
            [
                ("sda1/run.sh", "echo WRONG"),
                ("sdb1/open-connect/run.sh", "echo FIRST"),
                ("sdc1/open-connect/run.sh", "echo SECOND"),
            ]
        )
        self.assertNotEqual(ambiguous.returncode, 0)
        self.assertEqual(ambiguous.stdout, "")

        # Zero matching Open Connect drives runs nothing.
        none_found = run_trigger([("sda1/run.sh", "echo WRONG")])
        self.assertNotEqual(none_found.returncode, 0)
        self.assertEqual(none_found.stdout, "")

    def test_release_is_static_files_and_standard_native_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "build"
            command = ["make", "release", "OUT=" + str(output)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("python", result.stdout.lower())
            version = (ASSETS / "VERSION").read_text().strip()
            prefix = f"open-connect-{version}-usb/"
            with zipfile.ZipFile(output / f"open-connect-{version}-usb.zip") as z:
                self.assertTrue(all(n.startswith(prefix) for n in z.namelist()), z.namelist())
                expected = {prefix + TRIGGER, prefix + "jci-autoupdate"} | {
                    prefix + "open-connect/" + f for f in (*PAYLOAD, "files.sha256")
                }
                self.assertEqual({n for n in z.namelist() if not n.endswith("/")}, expected)
                self.assertEqual(z.read(prefix + TRIGGER), b"")
                self.assertLessEqual(len(z.read(prefix + "open-connect/settings.js")), 28672)
                self.assertLessEqual(
                    sum(
                        (len(z.read(prefix + "open-connect/" + name)) + 4095) // 4096
                        for name in (*PAYLOAD, "files.sha256")
                    ),
                    123,
                )
                for name in STATIC:
                    self.assertEqual(
                        z.read(prefix + "open-connect/" + name), (ASSETS / name).read_bytes()
                    )
                self.assertEqual(
                    z.read(prefix + "open-connect/layout.txt"),
                    (ROOT / "cmu/features/disclaimer/layout.txt").read_bytes(),
                )
                for name in (n for n in PAYLOAD if n.endswith(".sh")):
                    subprocess.run(
                        ["sh", "-n"], input=z.read(prefix + "open-connect/" + name), check=True
                    )
                rows = [
                    line.split()
                    for line in z.read(prefix + "open-connect/files.sha256").decode().splitlines()
                ]
                self.assertEqual({name for _, name in rows}, set(PAYLOAD))
                self.assertEqual(len(rows), len(PAYLOAD))
                for digest, name in rows:
                    self.assertEqual(
                        hashlib.sha256(z.read(prefix + "open-connect/" + name)).hexdigest(), digest
                    )
            self.assertEqual(
                struct.unpack("<II", (output / "sizes.bin").read_bytes()),
                (0x6F79C + len((output / "native.bin").read_bytes()),) * 2,
            )
            self.assertLessEqual(0x6F79C + len((output / "native.bin").read_bytes()), 0x70000)
            self.assertEqual(len((output / "layout.bin").read_bytes()), 68)
            self.assertEqual(len((output / "branch.bin").read_bytes()), 4)
            again = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn("fresh OUT", again.stderr)
            # Re-packaging across distinct host TZ, umask, perturbed mtimes and source modes
            # produces a byte-identical ZIP and SHA256SUMS.
            output2 = Path(temp) / "build2"
            shutil.copytree(
                output, output2, ignore=shutil.ignore_patterns("usb", "*.zip", "SHA256SUMS")
            )
            os.utime(output2 / "api", (1700000000, 1700000000))
            (output2 / "api").chmod(0o700)
            (output2 / "native.bin").chmod(0o600)
            res2 = subprocess.run(
                [
                    "sh",
                    "-c",
                    'umask 077; exec sh "$1" "$2"',
                    "repack",
                    str(ROOT / "tooling/package-usb.sh"),
                    str(output2),
                ],
                cwd=ROOT,
                env={**os.environ, "TZ": "UTC+5"},
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(res2.returncode, 0, res2.stdout + res2.stderr)
            zip1 = output / f"open-connect-{version}-usb.zip"
            zip2 = output2 / f"open-connect-{version}-usb.zip"
            with zipfile.ZipFile(zip1) as z1:
                for info in z1.infolist():
                    self.assertEqual(info.date_time, (2026, 1, 1, 0, 0, 0), info.filename)
                    mode = (info.external_attr >> 16) & 0o777
                    expected_mode = 0o755 if info.is_dir() else 0o644
                    self.assertEqual(mode, expected_mode, (info.filename, oct(mode)))
            self.assertEqual(zip1.read_bytes(), zip2.read_bytes())
            self.assertEqual(
                (output / "SHA256SUMS").read_text(),
                (output2 / "SHA256SUMS").read_text(),
            )

    def test_staging_checks_manifest_before_executing_payload(self):
        # Rewrite physical paths only; exercise the actual staging/hash loop with
        # real local files. No firmware bytes, mount commands or device access.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            package = root / "tmp/mnt/sda1/open-connect"
            package.mkdir(parents=True)
            (root / "version").write_text(
                'JCI_SW_VER="MAZ_CMU-150_74.00.324"\nJCI_SW_VER_PATCH="A"\nJCI_SW_FLAVOR="cmu150_NA"\n'
            )
            tools = root / "tools"
            tools.mkdir()
            if shutil.which("gstat"):
                (tools / "stat").symlink_to(shutil.which("gstat"))
            if not shutil.which("flock"):
                (tools / "flock").write_text(
                    f"#!{sys.executable}\nimport fcntl,sys\n"
                    "fcntl.flock(int(sys.argv[-1]), fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                )
                (tools / "flock").chmod(0o700)
            script = (ASSETS / "run.sh").read_text()
            replacements = {
                "PATH=/sbin:/bin:/usr/sbin:/usr/bin": "PATH="
                + shlex.quote(str(tools) + os.pathsep + os.environ["PATH"]),
                '"$(id -u)" = 0': f'"$(id -u)" = {os.getuid()}',
                "/jci/version.ini": str(root / "version"),
                "/tmp/mnt/sd": str(root / "tmp/mnt/sd"),
                "/tmp/open-connect-usb.lock": str(root / "lock"),
                "/tmp/oc-usb-XXXXXX": str(root / "staged-XXXXXX"),
            }
            for old, new in replacements.items():
                self.assertIn(old, script)
                script = script.replace(old, new)
            (package / "run.sh").write_text(script)
            marker = root / "executed"
            payload = ("loader.js", "session.sh", "api", "flush", "install")
            for name in payload:
                (package / name).write_text("fixture\n")
            (package / "session.sh").write_text(
                "trap 'printf terminated > "
                + shlex.quote(str(marker))
                + "; exit 0' TERM\n"
                + "printf '%s' \"$$\" > "
                + shlex.quote(str(root / "session.pid"))
                + "\n"
                + 'i=0; while [ "$i" -lt 50 ]; do i=$((i+1)); sleep 0.1; done\n'
            )
            manifest = "".join(
                hashlib.sha256((package / name).read_bytes()).hexdigest() + "  " + name + "\n"
                for name in payload
            )
            for broken in (
                manifest.replace("  api", "  ../../elsewhere"),
                manifest.replace("  api", "  loader.js"),
                manifest.replace(manifest.split()[0], "f" * 64),
            ):
                (package / "files.sha256").write_text(broken)
                result = subprocess.run(
                    ["sh", str(package / "run.sh")], capture_output=True, timeout=5
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / "session.pid").exists())
                self.assertFalse(marker.exists())
                self.assertEqual(list(root.glob("staged-*")), [])
            (package / "files.sha256").write_text(manifest)
            result = subprocess.run(["sh", str(package / "run.sh")], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            pid_file = root / "session.pid"
            for _ in range(40):
                if pid_file.exists() and pid_file.read_text().strip().isdigit():
                    break
                time.sleep(0.05)
            self.assertTrue(pid_file.exists(), "session.sh did not launch")
            child_pid = int(pid_file.read_text().strip())
            os.kill(child_pid, signal.SIGTERM)
            for _ in range(40):
                if marker.exists():
                    break
                time.sleep(0.05)
            self.assertEqual(marker.read_text(), "terminated")
