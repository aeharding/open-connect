"""Optional HOST copy adapter. Import frozen patch logic; no device installer."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from engine import Conflict, Engine, MARKER, regular, sha

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PRIVATE = REPO / 'runs'
FREEZE = REPO / 'experiments/disclaimer/freeze.json'
FREEZE_SHA = '42eb3420551c9d647f58f624cfa53e86e5c379c286443bf5ddf53c0b05a37d6d'
DEFAULT_ORIGINAL = PRIVATE / '20261113T022134-0600-t14-oem-disclaimer/originals/jci/gui/apps/system/js/systemApp.js'
ENABLED = 'ENABLED'
COPY_MODE = 0o755  # host fixture mode models observed OEM listing, not ownership/ACLs


class MissingSource(FileNotFoundError):
    pass


def frozen_patch():
    raw = FREEZE.read_bytes()
    if sha(raw) != FREEZE_SHA:
        raise Conflict('independent disclaimer freeze changed')
    freeze = json.loads(raw)
    path = REPO / 'experiments/disclaimer/patch.py'
    if sha(path.read_bytes()) != freeze['code_and_design_sha256']['experiments/disclaimer/patch.py']:
        raise Conflict('frozen patch logic changed')
    spec = importlib.util.spec_from_file_location('frozen_disclaimer_patch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, freeze


def images(original):
    module, freeze = frozen_patch()
    try:
        candidate = module.patch_original(original)  # reuse the independent pure transform verbatim
    except module.Rejected as exc:
        raise Conflict(str(exc)) from exc
    if sha(candidate) != freeze['candidate']['sha256'] or len(candidate) != freeze['candidate']['bytes']:
        raise Conflict('candidate differs from frozen first pass')
    return {None: original, ENABLED: candidate}


def private_root(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or not root.resolve().is_relative_to(PRIVATE.resolve()) or root.resolve() == PRIVATE.resolve():
        raise Conflict('copy fixture must be a private temporary directory under runs/')
    return root


def create_copy(root, source=None):
    root = private_root(root)
    if list(root.iterdir()):
        raise Conflict('requires empty private copy directory')
    source = Path(source) if source is not None else DEFAULT_ORIGINAL
    if not source.exists() and not source.is_symlink():
        raise MissingSource('SKIP: private exact55 source is absent')
    original = regular(source, limit=100000)[0]
    profile = images(original)  # unsupported input fails BEFORE any fixture write
    (root / 'HOST_FIXTURE_ONLY').write_bytes(MARKER)
    (root / 'fixture.conf').write_bytes(original)
    (root / 'fixture.conf').chmod(COPY_MODE)
    (root / 'unrelated.txt').write_bytes(b'unrelated host fixture file\n')
    return Engine(root, images=profile, feature='private-disclaimer55-host-model', mode=COPY_MODE)


def open_copy(root):
    root = private_root(root)
    if regular(root / 'HOST_FIXTURE_ONLY')[0] != MARKER:
        raise Conflict('host copy marker required')
    module, _ = frozen_patch()
    saved = root / '.proof' / (module.BASE_SHA256 + '.bin')
    # Recovery/reopen uses the stored original, not the external master source.
    original = regular(saved if saved.exists() or saved.is_symlink() else root / 'fixture.conf', limit=100000)[0]
    return Engine(root, images=images(original), feature='private-disclaimer55-host-model', mode=COPY_MODE)


def interrupt(root, action='enable'):
    code = '''import os,sys
from disclaimer_adapter import open_copy,ENABLED
e=open_copy(sys.argv[1])
def checkpoint(stage):
 if stage=='written': os._exit(86)
if sys.argv[2]=='disable': e.uninstall(_checkpoint=checkpoint)
else: e.apply(ENABLED,_checkpoint=checkpoint)
'''
    result = subprocess.run([sys.executable, '-B', '-c', code, str(root), action],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    if result.returncode != 86:
        raise AssertionError('copy interruption failed: ' + repr(result))
    return result.returncode


def demo():
    if not DEFAULT_ORIGINAL.exists():
        return {'result': 'SKIP', 'reason': 'private exact55 original absent; no substitute/OEM fetch', 'device_actions': False}
    source_before = regular(DEFAULT_ORIGINAL, limit=100000)
    module, freeze = frozen_patch()
    steps = []
    with tempfile.TemporaryDirectory(prefix='t12-disclaimer-copy-', dir=PRIVATE) as folder:
        root = Path(folder)
        engine = create_copy(root)
        def record(name, result):
            data, mode = regular(engine.target, limit=100000)
            journal = json.loads(engine.journal_path.read_text()) if engine.journal_path.exists() else None
            steps.append({'step': name, 'result': result, 'bytes': len(data), 'sha256': sha(data),
                          'mode': mode, 'journal': journal})  # NO OEM bytes in report
        record('plan', engine.plan(ENABLED)); assert not engine.store.exists()
        record('enable', engine.apply(ENABLED))
        record('verify', engine.verify())
        journal = engine.journal_path.read_bytes()
        record('reapply', engine.apply(ENABLED)); assert engine.journal_path.read_bytes() == journal
        record('disable', engine.uninstall())
        assert regular(engine.target, limit=100000) == (source_before[0], COPY_MODE)
        rc = interrupt(root)
        record('interrupted_enable', {'child_exit': rc, **open_copy(root).verify()})
        record('recover_from_stored_original', open_copy(root).recover())
        assert regular(engine.target, limit=100000) == (source_before[0], COPY_MODE)
        engine = open_copy(root); engine.apply(ENABLED)
        later = engine.target.read_bytes().replace(b'Copyright', b'CopyRight', 1)
        engine.target.write_bytes(later); journal = engine.journal_path.read_bytes()
        try:
            engine.uninstall()
        except Conflict as exc:
            conflict = {'result': 'refused_and_preserved', 'reason': str(exc), 'later_sha256': sha(later)}
        else:
            raise AssertionError('unrelated later edit overwritten')
        assert engine.target.read_bytes() == later and engine.journal_path.read_bytes() == journal
    assert regular(DEFAULT_ORIGINAL, limit=100000) == source_before
    return {'result': 'PASS', 'scope': 'private temporary COPIES, not installed/modified CMU',
            'freeze_sha256': FREEZE_SHA, 'original_sha256': module.BASE_SHA256,
            'candidate_sha256': freeze['candidate']['sha256'], 'steps': steps, 'conflict': conflict,
            'master_source_bytes_mode_unchanged': True, 'temporary_copy_removed': not root.exists(),
            'original_restored_exact_bytes_and_mode': True, 'device_actions': False,
            'limits': 'As-found installed55 byte profile; process exit/host bytes+mode only; no startup/device recovery claim'}


if __name__ == '__main__':
    report = demo()
    print(report['result'] + ': private copy enable/verify/reapply/disable/recovery/conflict')
    if report['result'] == 'SKIP':
        print(report['reason'])
