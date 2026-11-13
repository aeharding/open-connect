"""Tiny default CLI: temporary synthetic fixtures only, no target/root-path option."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from engine import BASELINE, MODE, Conflict, Engine, create_fixture, regular, sha

ROOT = Path(__file__).resolve().parent


def interrupt(root, action='apply', label='READY', point='written'):
    """Real process exit leaves the durable fixture journal/image for another process."""
    code = '''import os,sys
from engine import Engine
e=Engine(sys.argv[1])
def checkpoint(stage):
 if stage==sys.argv[4]: os._exit(86)
if sys.argv[2]=='uninstall': e.uninstall(_checkpoint=checkpoint)
else: e.apply(sys.argv[3],_checkpoint=checkpoint)
'''
    result = subprocess.run([sys.executable, '-B', '-c', code, str(root), action, label, point],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    if result.returncode != 86:
        raise AssertionError('fault process did not stop at checkpoint: ' + repr(result))
    return result.returncode


def run():
    steps = []
    with tempfile.TemporaryDirectory(prefix='cmu-host-installer-fixture-') as folder:
        root = Path(folder).resolve()
        engine = create_fixture(root)
        original = regular(engine.target)
        unrelated = (root / 'unrelated.txt').read_bytes()
        def record(name, result):
            data, mode = regular(engine.target)
            journal = json.loads(engine.journal_path.read_text()) if engine.journal_path.exists() else None
            steps.append({'step': name, 'result': result, 'observed_bytes_utf8': data.decode(),
                          'sha256': sha(data), 'mode': mode, 'journal': journal})
        plan = engine.plan()
        assert not engine.store.exists() and regular(engine.target) == original
        record('plan_read_only', plan)
        record('apply', engine.apply())
        record('verify', engine.verify())
        journal_before = engine.journal_path.read_bytes()
        record('reapply', engine.apply())
        assert engine.journal_path.read_bytes() == journal_before
        record('reconfigure', engine.apply('READY'))
        assert engine.verify()['label'] == 'READY'
        record('uninstall', engine.uninstall())
        assert regular(engine.target) == original
        engine.apply('DEMO')
        interrupted_rc = interrupt(root)
        record('interrupted_reconfigure', {'child_exit': interrupted_rc, **Engine(root).verify()})
        record('recover_from_disk', Engine(root).recover())
        assert Engine(root).verify()['label'] == 'DEMO'
        record('final_uninstall', Engine(root).uninstall())
        assert regular(engine.target) == original == (BASELINE, MODE)
        assert (root / 'unrelated.txt').read_bytes() == unrelated
        saved_original = engine.store / (sha(BASELINE) + '.bin')
        assert saved_original.read_bytes() == original[0]
        original_preserved = sha(saved_original.read_bytes())
    # Separate conflict case: no attempt to force-repair later edits.
    with tempfile.TemporaryDirectory(prefix='cmu-host-installer-conflict-') as folder:
        root = Path(folder).resolve()
        engine = create_fixture(root); engine.apply()
        later = engine.target.read_bytes() + b'# another owner changed this file\n'
        engine.target.write_bytes(later)
        journal = engine.journal_path.read_bytes()
        try:
            engine.uninstall()
        except Conflict as exc:
            conflict = {'status': 'refused_and_preserved', 'reason': str(exc), 'bytes_sha256': sha(later)}
        else:
            raise AssertionError('later edit was overwritten')
        assert engine.target.read_bytes() == later and engine.journal_path.read_bytes() == journal
    return {'result': 'PASS', 'scope': 'disposable HOST synthetic fixtures only', 'steps': steps,
            'conflict': conflict, 'stored_original_sha256': original_preserved,
            'original_restored_exact_bytes_and_mode': True, 'unrelated_file_unchanged': True,
            'temporary_fixtures_removed': not root.exists(), 'device_actions': False,
            'limitation': 'Process-exit recovery on host filesystem, not CMU/power-loss/recovery proof'}


def main():
    report = run()
    print('HOST DEMO ' + report['result'])
    for row in report['steps']:
        print(row['step'] + ': ' + str(row['result'].get('status', row['result'].get('action', 'recorded'))))
    print('later edit: ' + report['conflict']['status'])
    print('original bytes/mode restored; temporary fixtures removed; no device actions')

if __name__ == '__main__':
    main()
