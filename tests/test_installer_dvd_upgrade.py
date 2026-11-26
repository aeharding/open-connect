"""Real OC2 install/recovery handoffs across the retired NA DVD preference."""

import hashlib
import itertools
import json
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "tests/fixtures/dev20-dvd"


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class DVDUpgrade(unittest.TestCase):
    def fixture(self, version, base, dvd):
        from tests.test_installer_boot import InstallerBoot

        f = InstallerBoot("test_populated_fast_path_keeps_budget_and_original_dependency_guards")
        f.setUp()
        self.addCleanup(f.doCleanups)
        old = f.data / "packages/.old-dvd"
        shutil.copytree(f.package, old)
        for name in ("preferences.awk", "services.tsv", "sm-profile.awk", "ui-profile.awk"):
            shutil.copyfile(OLD / name, old / name)
        # Reuse the fixture's authored plugin pins, retaining the frozen policy.
        pins = {
            row.split("\t")[1]: row.split("\t")[3]
            for row in (f.package / "ui-modules.tsv").read_text().splitlines()
            if row.startswith("vui\t")
        }
        rows = []
        for line in (OLD / "ui-modules.tsv").read_text().splitlines():
            if line.startswith("vui\t"):
                kind, name, group, _ = line.split("\t")
                line = "\t".join((kind, name, group, pins[name]))
            rows.append(line)
        (old / "ui-modules.tsv").write_text("\n".join(rows) + "\n")
        with (old / "firmware.sh").open("a") as out:
            out.write("\n" + (OLD / "render.sh").read_text())
        (old / "VERSION").write_text(version + "\n")
        self.manifest(old)
        old_id = hashlib.sha256((old / "files.sha256").read_bytes()).hexdigest()
        old.rename(old.with_name(old_id))
        shutil.copytree(f.data / "composed" / f.package_id, f.data / "composed" / old_id)
        f.composed_manifest(old_id)
        f.shell(
            '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; record_read; '
            f"old={old_id}; R_BACKEND=$old; "
            'prefs=$(awk -v operation=write -v catalog="$D/packages/$old/services.tsv" '
            '-v catalog_bytes="$(wc -c < "$D/packages/$old/services.tsv")" '
            '-v package_id="$old" -v nvram_value=disable -v metadata_value="755:$(id -u):$(id -g)" '
            '-f "$D/packages/$old/preferences.awk"); '
            f'prefs=$(printf "%s\\n" "$prefs" | sed "s/base=0/base={base}/;s/service.dvd=0/service.dvd={dvd}/;s/service.pandora=1/service.pandora=0/"); '
            'deps=$(mktemp "$D/.dvd-deps-XXXXXX"); dependencies_capture "$old" > "$deps"; '
            'R_CURRENT=$(snapshot_create "$AUTOSTART" "$old" disable "755:$(id -u):$(id -g)" "$deps" - "$prefs"); '
            'rm "$deps"; record_write; snapshot_read "$R_CURRENT"'
        )
        self.policy(f, base, dvd=dvd)
        return f, old_id

    def manifest(self, folder):
        (folder / "files.sha256").write_text(
            "".join(
                hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                for p in sorted(folder.iterdir())
                if p.name != "files.sha256"
            )
        )

    def policy(self, f, base, dvd=None):
        snapshot = f.data / "snapshots" / f.record()[5]
        config = (snapshot / "config").read_text()
        self.assertIn(f"base={base}\n", config)
        self.assertIn("service.pandora=0\n", config)
        if dvd is None:
            self.assertNotIn("dvd", config)
            self.assertIn("service-ids=android-auto,pandora,siriusxm\n", config)
        else:
            self.assertIn(f"service.dvd={dvd}\n", config)
            self.assertIn("service-ids=android-auto,dvd,pandora,siriusxm\n", config)
        for profile in ("normal", "wcp"):
            jobs = {
                n.get("name"): n for n in ET.parse(snapshot / f"sm-{profile}.conf").iter("service")
            }
            stopped = base if dvd is None else not dvd
            self.assertEqual(jobs["jcidvd"].get("autorun"), "no" if stopped else "yes")
            self.assertEqual(jobs["blm_ira_pandora"].get("autorun"), "no")
        nodes = {n.get("name") for n in ET.parse(snapshot / "mmui.xml").getroot()}
        self.assertEqual("dvd" in nodes, not base or (dvd is not None and bool(dvd)))
        plugins = (snapshot / "vui-plugins.list").read_text().splitlines()
        self.assertEqual("vui_plugin_dvd.so" in plugins, bool(base and dvd))
        index = (snapshot / "index.html").read_text()
        self.assertEqual(",dvd" in index, bool(base if dvd is None else not dvd))

    def client(self, f):
        client = f.runtime / "client"
        shutil.copytree(f.package, client)
        (f.runtime / "usb-runtime").symlink_to(client)
        # Only physical installation preparation is adapted: the real backend,
        # target-owned writers/renderers, manifests and transactions run intact.
        login = f.root / "runlogin"
        login.write_text("authored stock login\n")
        backend = (client / "backend.sh").read_text().replace("/usr/bin/runlogin", str(login))
        backend = backend.replace("/usr/bin/.open-connect-runlogin-", str(f.root / ".login-"))
        backend = backend.replace(
            "b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8",
            hashlib.sha256(login.read_bytes()).hexdigest(),
        )
        backend = backend.replace(
            '. "$P/transaction.sh"\n',
            '. "$P/transaction.sh"\n'
            "originals_save() { :; }; stock_dependencies() { :; }\n"
            'package_save() { printf "%s\\n" "$DVD_TARGET"; }; compose() { :; }\n'
            "access_capture() { :; }; access_compose() { :; }\n"
            "selector_capture() { :; }; selector_compose() { :; }\n",
        )
        (client / "backend.sh").write_text(backend)
        self.manifest(client)
        return client

    def backend(self, f, client, operation, target=None):
        result = subprocess.run(
            ["sh", client / "backend.sh", "api", f.record()[5], operation, "-", "-", "-"],
            capture_output=True,
            text=True,
            env={**f.env, "DVD_TARGET": target or f.package_id},
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def boot(self, f, number):
        entry = f.package
        f.package = f.data / "packages" / f.record()[3]
        try:
            result = f.boot(number)
        finally:
            f.package = entry
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_dev19_dev20_install_downgrade_and_uninstall_preserve_originals(self):
        for version, base, dvd in itertools.product(
            ("0.3.0-dev.19", "0.3.0-dev.20"), (0, 1), (0, 1)
        ):
            with self.subTest(version=version, base=base, dvd=dvd):
                f, old = self.fixture(version, base, dvd)
                baseline = f.record()[4]
                legacy = f.data / "snapshots" / f.record()[5]
                original = {p.name: p.read_bytes() for p in legacy.iterdir()}
                client = self.client(f)
                # New media can read/status/boot/uninstall the untouched old record.
                self.assertTrue(self.backend(f, client, "status")["installed"])
                self.boot(f, 1)
                installed = self.backend(f, client, "install")
                self.assertTrue(installed["installed"])
                self.assertEqual(f.record()[4], baseline)
                self.policy(f, base)
                self.assertEqual(original, {p.name: p.read_bytes() for p in legacy.iterdir()})
                self.boot(f, 2)
                # The older target writer restores its own DVD default (Off).
                # It accepts the reduced key set without inventing a new schema.
                self.backend(f, client, "install", old)
                self.assertEqual(f.record()[4], baseline)
                self.policy(f, base, dvd=0)
                self.boot(f, 3)
                self.backend(f, client, "uninstall")
                self.assertFalse(f.data.exists())
                self.assertEqual((f.root / "data-target").read_bytes(), b"stock\n")
                self.assertEqual((f.root / "data-nvram").read_text(), "absent\n")

    def test_pending_upgrade_reconciles_both_package_readers_and_uninstalls(self):
        for dvd in (0, 1):
            with self.subTest(dvd=dvd):
                f, _ = self.fixture("0.3.0-dev.20", 1, dvd)
                baseline = f.record()[4]
                f.shell(
                    '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; '
                    'record_read; snapshot_read "$R_CURRENT"; prefs=$S_PREFS; '
                    'deps=$(mktemp "$D/.dvd-deps-XXXXXX"); '
                    # f.shell initializes R_BACKEND to the new target package.
                    'target=${P##*/}; dependencies_capture "$target" > "$deps"; '
                    'after=$(snapshot_create "$AUTOSTART" "$target" "$S_NVRAM" "$S_META" "$deps" - "$prefs"); '
                    'rm "$deps"; R_BACKEND=$target; transaction_prepare install "$R_CURRENT" "$after"'
                )
                self.assertEqual(f.record()[1], "install")
                f.shell(
                    '. "$P/access.sh"; . "$P/transaction.sh"; AUTOSTART=$D-target; record_read; transaction_reconcile'
                )
                self.assertEqual(f.record()[1], "active")
                self.assertEqual(f.record()[4], baseline)
                self.policy(f, 1)
                self.backend(f, self.client(f), "uninstall")
                self.assertFalse(f.data.exists())
