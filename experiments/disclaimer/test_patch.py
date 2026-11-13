import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch as mock_patch
import patch as feature

ROOT = Path(__file__).resolve().parent


class PatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = feature.DEFAULT_ORIGINAL.read_bytes()
        cls.candidate = feature.patch_original(cls.original)

    def test_exact_one_initial_assignment_and_byte_exact_rollback(self):
        old, new = self.original, self.candidate
        self.assertEqual(feature.sha(old), feature.BASE_SHA256)
        self.assertEqual(len(new), len(old) - 3)
        a, b = old.index(feature.START), old.index(feature.END)
        self.assertEqual(new[:a], old[:a])
        self.assertEqual(new[a:b-3], old[a:b].replace(feature.OLD, feature.NEW, 1))
        self.assertEqual(new[b-3:], old[b:])
        self.assertEqual(new.count(feature.OLD), old.count(feature.OLD) - 1)
        self.assertEqual(new.count(b'\r\n'), old.count(b'\r\n'))
        self.assertEqual(feature.rollback(new, old), old)

    def test_base_hash_firmware_and_reapplication_refusal(self):
        for data in (b'', self.original + b'\n', self.original.replace(b'3500', b'3501', 1), self.candidate):
            with self.assertRaises(feature.Rejected):
                feature.patch_original(data)
        with self.assertRaises(feature.Rejected):
            feature.patch_original(self.original, '73/other')

    def test_rollback_preserves_unknown_or_later_bytes(self):
        later = self.candidate + b'// unrelated later edit\r\n'
        with self.assertRaises(feature.Rejected):
            feature.rollback(later, self.original)
        self.assertTrue(later.endswith(b'// unrelated later edit\r\n'))
        with self.assertRaises(feature.Rejected):
            feature.rollback(self.candidate, self.original + b' ')

    def test_synthetic_scoping_and_ambiguous_anchor_refusal(self):
        # Independently authored fixture; not an OEM source copy.
        fragment = feature.START + b'{ INITIAL ' + feature.OLD + b' }\n' + feature.END + b'){} RETRY ' + feature.OLD
        result = feature._replace_initial_timer(fragment)
        self.assertIn(b'INITIAL ' + feature.NEW, result)
        self.assertTrue(result.endswith(b'RETRY ' + feature.OLD))
        for data in (fragment + feature.START, fragment.replace(feature.OLD, feature.OLD * 2, 1),
                     fragment.replace(feature.START, b'unknown'), feature.END + feature.START):
            with self.assertRaises(feature.Rejected):
                feature._replace_initial_timer(data)

    def test_private_build_is_non_destructive_and_refuses_existing_or_public_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / 'runs').mkdir()
            source = root / 'source.bin'; source.write_bytes(self.original)
            with mock_patch.object(feature, 'REPO', root):
                with self.assertRaises(feature.Rejected):
                    feature.build(source, root / 'public')
                output = root / 'runs' / 'new'
                result = feature.build(source, output)
                self.assertTrue(result['rollback_byte_exact'])
                self.assertEqual(source.read_bytes(), self.original)
                self.assertEqual((output / 'original.bin').read_bytes(), self.original)
                self.assertEqual((output / 'candidate.bin').read_bytes(), self.candidate)
                saved = (output / 'plan.json').read_bytes()
                with self.assertRaises(FileExistsError):
                    feature.build(source, output)
                self.assertEqual((output / 'plan.json').read_bytes(), saved)

    def test_actual_oem_functions_with_host_timer_and_native_event_stubs(self):
        with tempfile.TemporaryDirectory() as folder:
            candidate = Path(folder) / 'candidate.js'
            candidate.write_bytes(self.candidate)
            syntax = subprocess.run(['node', '--check', str(candidate)], capture_output=True, text=True, timeout=10)
            self.assertEqual(syntax.returncode, 0, syntax.stderr)
            result = subprocess.run(['node', str(ROOT / 'test_behavior.js'),
                                     str(feature.DEFAULT_ORIGINAL), str(candidate)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            observed = json.loads(result.stdout)
            self.assertEqual(observed['result'], 'PASS')
            self.assertEqual(observed['initial_candidate_ms'], 0)
            self.assertEqual(observed['retry_ms'], 3500)
            print('HOST_OEM_SEMANTICS ' + json.dumps(observed, sort_keys=True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
