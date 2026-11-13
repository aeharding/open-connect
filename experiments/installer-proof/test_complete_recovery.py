from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from engine import BASELINE, MODE, Conflict, Engine, content, create_fixture, regular, sha
from demo import interrupt
import disclaimer_adapter as adapter


class CompletionTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix='cmu-complete-test-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        return root, create_fixture(root)

    def pending_disable(self, point='written'):
        root, engine = self.fixture()
        engine.apply('DEMO')
        self.assertEqual(interrupt(root, action='uninstall', point=point), 86)
        return root, Engine(root)

    def assert_disabled(self, engine):
        self.assertEqual(regular(engine.target), (BASELINE, MODE))
        self.assertEqual(engine.verify(), {'status': 'uninstalled', 'verified': True, 'label': None})
        journal = json.loads(engine.journal_path.read_text())
        self.assertIsNone(journal['pending'])
        self.assertEqual(journal['current'], journal['original'])
        self.assertEqual((engine.store / (sha(BASELINE) + '.bin')).read_bytes(), BASELINE)
        return journal

    def test_original_already_visible_commits_without_target_rewrite(self):
        root, engine = self.pending_disable('written')
        self.assertFalse(engine.verify()['verified'])
        inode = engine.target.stat().st_ino
        with patch.object(engine, '_replace', side_effect=AssertionError('original must not be rewritten')):
            result = engine.complete_uninstall()
        self.assertEqual(result['status'], 'completed_uninstall')
        journal = self.assert_disabled(engine)
        self.assertEqual(engine.target.stat().st_ino, inode)
        saved = engine.journal_path.read_bytes()
        with patch.object(engine, '_save', side_effect=AssertionError('no-op must not write journal')):
            self.assertEqual(engine.complete_uninstall()['status'], 'already_uninstalled')
        self.assertEqual(engine.journal_path.read_bytes(), saved)
        print('COMPLETE_CASE ' + json.dumps({'observed': 'original', 'target_rewritten': False,
              'committed_label': journal['current']['label'], 'pending': journal['pending']}))

    def test_candidate_visible_restores_stored_original_then_commits_disabled(self):
        root, engine = self.pending_disable('prepared')
        self.assertEqual(engine.target.read_bytes(), content('DEMO'))
        with patch.object(engine, '_replace', wraps=engine._replace) as replace:
            result = engine.complete_uninstall()
        self.assertEqual(result['status'], 'completed_uninstall')
        self.assertEqual(replace.call_count, 1)
        self.assert_disabled(Engine(root))
        print('COMPLETE_CASE ' + json.dumps({'observed': 'candidate', 'restored_original': True,
                                             'committed_label': None, 'pending': None}))

    def test_wrong_or_missing_intent_refuses_implicit_uninstall(self):
        for case in ('no_journal', 'enabled_no_pending', 'pending_enable', 'pending_reconfigure', 'wrong_operation', 'wrong_after'):
            with self.subTest(case=case):
                root, engine = self.fixture()
                if case != 'no_journal':
                    if case == 'pending_enable':
                        interrupt(root, label='DEMO', point='prepared')
                    else:
                        engine.apply('DEMO')
                        if case == 'pending_reconfigure':
                            interrupt(root, label='READY', point='prepared')
                        elif case in ('wrong_operation', 'wrong_after'):
                            interrupt(root, action='uninstall', point='prepared')
                            journal = json.loads(engine.journal_path.read_text())
                            if case == 'wrong_operation':
                                journal['pending']['operation'] = 'apply'
                            else:
                                journal['pending']['after'] = journal['current']
                            engine.journal_path.write_text(json.dumps(journal))
                before = regular(engine.target)
                journal_before = engine.journal_path.read_bytes() if engine.journal_path.exists() else None
                with self.assertRaises(Conflict): Engine(root).complete_uninstall()
                self.assertEqual(regular(engine.target), before)
                self.assertEqual(engine.journal_path.read_bytes() if engine.journal_path.exists() else None, journal_before)

    def test_unknown_metadata_and_bad_backup_or_journal_preserved(self):
        for case in ('unknown', 'mode', 'missing_target', 'bad_backup', 'missing_backup', 'bad_journal', 'missing_journal'):
            with self.subTest(case=case):
                root, engine = self.pending_disable('written')
                original = engine.store / (sha(BASELINE) + '.bin')
                if case == 'unknown': engine.target.write_bytes(BASELINE + b'# later edit\n')
                elif case == 'mode': engine.target.chmod(0o600)
                elif case == 'missing_target': engine.target.unlink()
                elif case == 'bad_backup': original.write_bytes(b'broken')
                elif case == 'missing_backup': original.unlink()
                elif case == 'bad_journal': engine.journal_path.write_bytes(b'{}')
                elif case == 'missing_journal': engine.journal_path.unlink()
                before = regular(engine.target) if engine.target.exists() else None
                j_before = engine.journal_path.read_bytes() if engine.journal_path.exists() else None
                with self.assertRaises(Conflict): Engine(root).complete_uninstall()
                self.assertEqual(regular(engine.target) if engine.target.exists() else None, before)
                self.assertEqual(engine.journal_path.read_bytes() if engine.journal_path.exists() else None, j_before)

    def test_reinterruption_before_registry_commit_stays_pending(self):
        root, engine = self.pending_disable('prepared')
        before = engine.journal_path.read_bytes()
        with patch.object(engine, '_save', side_effect=RuntimeError('synthetic stop before commit')):
            with self.assertRaises(RuntimeError): engine.complete_uninstall()
        self.assertEqual(regular(engine.target), (BASELINE, MODE))
        self.assertEqual(engine.journal_path.read_bytes(), before)
        self.assertEqual(Engine(root).verify()['status'], 'incomplete')
        self.assertIsNotNone(json.loads(before)['pending'])
        fresh = Engine(root)
        with patch.object(fresh, '_replace', side_effect=AssertionError('already original')):
            fresh.complete_uninstall()
        self.assert_disabled(fresh)

    @unittest.skipUnless(adapter.DEFAULT_ORIGINAL.is_file(), 'private AS-FOUND55 source absent')
    def test_frozen_disclaimer_copy_both_disable_windows(self):
        master = regular(adapter.DEFAULT_ORIGINAL, limit=100000)
        for point in ('prepared', 'written'):
            with self.subTest(point=point), tempfile.TemporaryDirectory(prefix='t12-complete-copy-', dir=adapter.PRIVATE) as folder:
                root = Path(folder); engine = adapter.create_copy(root); engine.apply(adapter.ENABLED)
                if point == 'prepared':
                    def checkpoint(stage):
                        if stage == 'prepared': raise RuntimeError('synthetic pre-write stop')
                    with self.assertRaises(RuntimeError): engine.uninstall(_checkpoint=checkpoint)
                else:
                    adapter.interrupt(root, 'disable')
                fresh = adapter.open_copy(root)
                inode = fresh.target.stat().st_ino
                result = fresh.complete_uninstall()
                self.assertEqual(result['status'], 'completed_uninstall')
                self.assertEqual(regular(fresh.target, limit=100000), (master[0], adapter.COPY_MODE))
                self.assertEqual(fresh.verify()['status'], 'uninstalled')
                journal = json.loads(fresh.journal_path.read_text())
                self.assertIsNone(journal['pending']); self.assertEqual(journal['current'], journal['original'])
                if point == 'written': self.assertEqual(fresh.target.stat().st_ino, inode)
                print('COMPLETE_COPY_CASE ' + json.dumps({'window': point, 'original_sha256': sha(master[0]),
                                                         'mode': adapter.COPY_MODE, 'committed_disabled': True}))
        self.assertEqual(regular(adapter.DEFAULT_ORIGINAL, limit=100000), master)


if __name__ == '__main__':
    unittest.main(verbosity=2)
