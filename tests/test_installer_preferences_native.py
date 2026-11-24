"""The shell and native selectors admit the same bounded preference data."""

import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_installer_preferences import ASSETS

ROOT = ASSETS.parents[1]


@unittest.skipUnless(shutil.which("clang"), "Clang required")
class NativePreferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.temp.name) / "boot-config"
        subprocess.run(
            [
                "clang",
                "-DOC_HOST",
                "-D_GNU_SOURCE",
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Wno-unused-function",
                "-I" + str(ASSETS),
                ROOT / "tests/fixtures/boot-config.c",
                "-o",
                cls.binary,
            ],
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.folder = Path(self.work.name)
        self.catalog = (ASSETS / "services.tsv").read_bytes()

    def fresh(self):
        catalog = self.folder / "services.tsv"
        catalog.write_bytes(self.catalog)
        return subprocess.check_output(
            [
                "awk",
                "-v",
                "operation=write",
                "-v",
                f"catalog={catalog}",
                "-v",
                f"catalog_bytes={len(self.catalog)}",
                "-v",
                "package_id=" + "a" * 64,
                "-v",
                "nvram_value=disable",
                "-v",
                "metadata_value=775:1000:1000",
                "-f",
                ASSETS / "preferences.awk",
            ]
        )

    def decode(self, config, active=True):
        (self.folder / "services.tsv").write_bytes(self.catalog)
        (self.folder / "config").write_bytes(config)
        manifest = "".join(
            hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
            for p in sorted(self.folder.iterdir())
            if p.name != "files.sha256"
        )
        (self.folder / "files.sha256").write_text(manifest)
        return subprocess.run(
            [
                self.binary,
                self.folder,
                hashlib.sha256(manifest.encode()).hexdigest(),
                "active" if active else "stock",
            ],
            capture_output=True,
            timeout=3,
        ).returncode

    def test_canonical_and_catalog_growth_past_old_buffer_boundary(self):
        self.assertEqual(self.decode(self.fresh()), 0)
        for index in range(12):
            self.catalog += (
                f"z{index:02d}-long-service-name|Service|1|leaf{index}|Load.|Stop.\n".encode()
            )
        config = self.fresh()
        self.assertGreater(len(config), 256)
        self.assertEqual(self.decode(config), 0)
        self.assertNotEqual(
            self.decode(config.replace(b"service.z00-long-service-name=1\n", b"")), 0
        )

    def test_malformed_config_refuses_before_selection(self):
        config = self.fresh()
        self.assertEqual(
            self.decode(config.replace(b"carplay-autoshow=0", b"carplay-autoshow=1")), 0
        )
        self.assertEqual(self.decode(config.replace(b"carplay-autoshow=0\n", b"")), 0)
        for changed in (
            config.replace(b"carplay-autoshow=0", b"carplay-autoshow=2"),
            config.replace(b"carplay-autoshow=0", b"carplay-autoshow=01"),
            config.replace(b"carplay-autoshow=0", b"carplay-autoshow=0\ncarplay-autoshow=1"),
            config.replace(
                b"service-ids=android-auto,dvd,pandora,siriusxm", b"service-ids=pandora"
            ),
            config.replace(
                b"service-ids=android-auto,dvd,pandora,siriusxm",
                b"service-ids=android-auto,android-auto,pandora",
            ),
            config.replace(
                b"service-ids=android-auto,dvd,pandora,siriusxm",
                b"service-ids=pandora,android-auto",
            ),
            config.replace(b"service-ids=android-auto,dvd,pandora,siriusxm\n", b""),
            config[:-1],
            config + b"\n",
            config.replace(b"base=0\n", b"base=0\nbase=0\n"),
            config.replace(b"base=0", b"base=00"),
            config.replace(b"base=0", b"base=0\0"),
            config.replace(b"metadata=775:1000:1000", b"metadata=00001:0:0"),
            config.replace(b"metadata=775:1000:1000", b"metadata=775:4294967296:0"),
            config.replace(b"service.pandora=1", b"service.unknown=1"),
            config.replace(b"wireless=0", b"wireless=2"),
            config + b"z=" + b"0" * 1024 + b"\n",
        ):
            with self.subTest(config=changed[:80]):
                self.assertNotEqual(self.decode(changed), 0)

    def test_decoder_consumes_the_authenticated_key_set_without_catalog_io(self):
        config = self.fresh()
        self.catalog = b"catalog validation belongs to maintenance, not the native decoder"
        self.assertEqual(self.decode(config), 0)

    def test_only_actual_dev9_stock_and_active_forms_are_admitted(self):
        self.assertEqual(self.decode(b"-|0|0|absent|755:0:0\n", False), 0)
        legacy = b"a" * 64 + b"|1|1|disable|755:0:0|0|1|1\n"
        self.assertEqual(self.decode(legacy), 0)
        for changed in (b"-|0|0|absent|755:0:0|1|0|0\n", b"-|2|0|absent|755:0:0\n"):
            self.assertNotEqual(self.decode(changed, False), 0)
        for fields in (5, 6, 7):
            self.assertNotEqual(
                self.decode(b"|".join(legacy.strip().split(b"|")[:fields]) + b"\n"), 0
            )
