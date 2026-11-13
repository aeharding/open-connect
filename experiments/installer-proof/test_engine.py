from pathlib import Path
import json
import tempfile
import unittest
from engine import BASELINE, MODE, Conflict, Engine, content, create_fixture, regular, sha
from demo import interrupt


class InstallerProofTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='cmu-installer-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.engine = create_fixture(self.root)

    def test_plan_apply_verify_reapply_reconfigure_uninstall(self):
        e = self.engine
        self.assertEqual(e.plan()['action'], 'apply')
        self.assertFalse(e.store.exists())
        self.assertEqual(e.apply()['status'], 'apply')
        self.assertEqual(e.verify(), {'status': 'installed', 'verified': True, 'label': 'DEMO'})
        before = e.journal_path.read_bytes()
        self.assertEqual(e.apply()['status'], 'no_op')
        self.assertEqual(e.journal_path.read_bytes(), before)
        self.assertEqual(e.plan('READY')['action'], 'reconfigure')
        self.assertEqual(e.apply('READY')['status'], 'reconfigure')
        self.assertEqual(e.verify()['label'], 'READY')
        self.assertEqual(e.uninstall()['status'], 'uninstall')
        self.assertEqual(regular(e.target), (BASELINE, MODE))
        self.assertEqual(e.uninstall()['status'], 'no_op')
        self.assertEqual((e.store / (sha(BASELINE) + '.bin')).read_bytes(), BASELINE)

    def test_unsupported_base_and_config_are_not_adopted(self):
        e = self.engine
        for data in (BASELINE + b'# unsupported\n', content('DEMO')):
            e.target.write_bytes(data)
            with self.assertRaises(Conflict): e.apply()
            self.assertEqual(e.target.read_bytes(), data)
            self.assertFalse(e.store.exists())
        e.target.write_bytes(BASELINE)
        for label in ('', 'OTHER', '../DEMO', True, 1):
            with self.assertRaises(Conflict): e.plan(label)
        self.assertFalse(e.store.exists())

    def test_later_edits_and_mode_conflict_preserved_unrelated_file_kept(self):
        e = self.engine; e.apply()
        unknown = content('DEMO') + b'# later edit\n'
        e.target.write_bytes(unknown)
        journal = e.journal_path.read_bytes()
        for operation in (e.plan, e.apply, lambda: e.apply('READY'), e.uninstall, e.verify):
            with self.assertRaises(Conflict): operation()
            self.assertEqual(e.target.read_bytes(), unknown)
            self.assertEqual(e.journal_path.read_bytes(), journal)
        # Same bytes but changed permissions also conflict.
        e.target.write_bytes(content('DEMO')); e.target.chmod(0o600)
        with self.assertRaises(Conflict): e.uninstall()
        self.assertEqual(regular(e.target)[1], 0o600)
        e.target.chmod(MODE)
        later_unrelated = b'another owner changed the other file\n'
        (self.root / 'unrelated.txt').write_bytes(later_unrelated)
        e.uninstall()
        self.assertEqual((self.root / 'unrelated.txt').read_bytes(), later_unrelated)

    def test_actual_process_exit_recovery_for_apply_reconfigure_and_uninstall(self):
        e = self.engine
        # Exit after durable intent, before target write.
        self.assertEqual(interrupt(self.root, label='DEMO', point='prepared'), 86)
        self.assertFalse(Engine(self.root).verify()['verified'])
        self.assertIsNone(Engine(self.root).recover()['label'])
        # Exit after target write; each new Engine uses stored bytes and journal only.
        self.assertEqual(interrupt(self.root, label='DEMO'), 86)
        self.assertEqual(Engine(self.root).verify()['observed_label'], 'DEMO')
        self.assertIsNone(Engine(self.root).recover()['label'])
        self.assertEqual(regular(e.target), (BASELINE, MODE))
        e.apply('DEMO')
        self.assertEqual(interrupt(self.root, label='READY'), 86)
        self.assertEqual(Engine(self.root).recover()['label'], 'DEMO')
        self.assertEqual(regular(e.target), (content('DEMO'), MODE))
        self.assertEqual(interrupt(self.root, action='uninstall'), 86)
        self.assertEqual(Engine(self.root).recover()['label'], 'DEMO')
        e.uninstall()
        self.assertEqual(regular(e.target), (BASELINE, MODE))

    def test_incomplete_blocks_reapply_and_unknown_recovery_preserves_everything(self):
        e = self.engine
        interrupt(self.root, label='DEMO')
        before = e.journal_path.read_bytes()
        with self.assertRaises(Conflict): Engine(self.root).apply()
        unknown = b'unknown later bytes\n'; e.target.write_bytes(unknown)
        with self.assertRaises(Conflict): Engine(self.root).recover()
        self.assertEqual(e.target.read_bytes(), unknown)
        self.assertEqual(e.journal_path.read_bytes(), before)

    def test_damaged_original_and_symlink_target_refuse(self):
        e = self.engine; e.apply()
        original = e.store / (sha(BASELINE) + '.bin')
        original.write_bytes(b'broken')
        installed = e.target.read_bytes()
        with self.assertRaises(Conflict): e.uninstall()
        self.assertEqual(e.target.read_bytes(), installed)
        # New fixture, target symlink points to an unowned sibling: never follow it.
        with tempfile.TemporaryDirectory() as folder:
            other = create_fixture(Path(folder))
            sibling = Path(folder) / 'outside.txt'; sibling.write_bytes(BASELINE)
            other.target.unlink(); other.target.symlink_to(sibling)
            with self.assertRaises(Conflict): other.apply()
            self.assertEqual(sibling.read_bytes(), BASELINE)
            self.assertFalse(other.store.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
