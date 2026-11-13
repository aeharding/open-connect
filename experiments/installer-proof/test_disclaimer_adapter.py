from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import disclaimer_adapter as adapter
from engine import Conflict, regular, sha


@unittest.skipUnless(adapter.DEFAULT_ORIGINAL.is_file(), 'private exact55 source absent; no OEM fetch/substitute')
class DisclaimerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='t12-adapter-test-', dir=adapter.PRIVATE)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.master = regular(adapter.DEFAULT_ORIGINAL, limit=100000)
        self.module, self.freeze = adapter.frozen_patch()

    def tearDown(self):
        self.assertEqual(regular(adapter.DEFAULT_ORIGINAL, limit=100000), self.master)

    def test_enable_verify_noop_reapply_disable_exact_bytes_mode(self):
        engine = adapter.create_copy(self.root)
        self.assertFalse(engine.store.exists())
        self.assertEqual(engine.plan(adapter.ENABLED)['action'], 'apply')
        engine.apply(adapter.ENABLED)
        self.assertEqual(engine.verify()['label'], adapter.ENABLED)
        self.assertEqual(engine.target.read_bytes(), self.module.patch_original(self.master[0]))
        self.assertEqual(sha(engine.target.read_bytes()), self.freeze['candidate']['sha256'])
        journal = engine.journal_path.read_bytes()
        self.assertEqual(engine.apply(adapter.ENABLED)['status'], 'no_op')
        self.assertEqual(engine.journal_path.read_bytes(), journal)
        stored_original = engine.store / (self.module.BASE_SHA256 + '.bin')
        self.assertEqual(stored_original.read_bytes(), self.master[0])
        engine.uninstall()
        self.assertEqual(regular(engine.target, limit=100000), (self.master[0], adapter.COPY_MODE))
        self.assertEqual(engine.uninstall()['status'], 'no_op')

    def test_process_exit_recover_from_stored_original_without_master_for_enable_disable(self):
        engine = adapter.create_copy(self.root)
        self.assertEqual(adapter.interrupt(self.root), 86)
        self.assertFalse(adapter.open_copy(self.root).verify()['verified'])
        with self.assertRaises(Conflict): adapter.open_copy(self.root).apply(adapter.ENABLED)
        # Reopen/recovery uses stored original, even if external master path is unavailable.
        with patch.object(adapter, 'DEFAULT_ORIGINAL', self.root / 'absent-master'):
            result = adapter.open_copy(self.root).recover()
        self.assertIsNone(result['label'])
        self.assertEqual(regular(engine.target, limit=100000), (self.master[0], adapter.COPY_MODE))
        engine = adapter.open_copy(self.root); engine.apply(adapter.ENABLED)
        adapter.interrupt(self.root, 'disable')
        self.assertEqual(adapter.open_copy(self.root).recover()['label'], adapter.ENABLED)
        engine.uninstall()
        self.assertEqual(regular(engine.target, limit=100000), (self.master[0], adapter.COPY_MODE))

    def test_conflicting_later_edit_and_pending_recovery_never_overwrite(self):
        engine = adapter.create_copy(self.root); engine.apply(adapter.ENABLED)
        candidate = engine.target.read_bytes()
        later = candidate.replace(b'Copyright', b'CopyRight', 1)
        self.assertNotEqual(later, candidate)
        engine.target.write_bytes(later); journal = engine.journal_path.read_bytes()
        for operation in (engine.verify, lambda: engine.apply(adapter.ENABLED), engine.uninstall):
            with self.assertRaises(Conflict): operation()
            self.assertEqual(engine.target.read_bytes(), later)
            self.assertEqual(engine.journal_path.read_bytes(), journal)
        # Restore only our fixture's known bytes to set up an independent pending conflict.
        engine.target.write_bytes(candidate); engine.uninstall()
        adapter.interrupt(self.root)
        engine.target.write_bytes(later); journal = engine.journal_path.read_bytes()
        with self.assertRaises(Conflict): adapter.open_copy(self.root).recover()
        self.assertEqual(engine.target.read_bytes(), later)
        self.assertEqual(engine.journal_path.read_bytes(), journal)

    def test_missing_or_unsupported_source_never_creates_fixture_or_fuzzy_patch(self):
        with tempfile.TemporaryDirectory(prefix='t12-bad-source-', dir=adapter.PRIVATE) as folder:
            bad = Path(folder) / 'bad.bin'; bad.write_bytes(self.master[0] + b'\n')
            with self.assertRaises(Conflict): adapter.create_copy(self.root, source=bad)
            self.assertEqual(list(self.root.iterdir()), [])
            with self.assertRaises(adapter.MissingSource):
                adapter.create_copy(self.root, source=Path(folder) / 'missing.bin')
            self.assertEqual(list(self.root.iterdir()), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
