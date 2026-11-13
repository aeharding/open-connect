"""One-file HOST FIXTURE experiment, not a CMU/device installer or product policy."""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

MARKER = b'CMU BENCH HOST FIXTURE ONLY v1\n'
FEATURE = 'demo-bench-badge'
BASELINE = b'# disposable host fixture\nui_label=STOCK\n'
MODE = 0o640
LABELS = ('DEMO', 'READY')


class Conflict(RuntimeError):
    """Unsupported or later changes: preserve current files, require inspection."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def content(label):
    if label is not None and (type(label) is not str or label not in LABELS):
        raise Conflict('unsupported synthetic configuration')
    return BASELINE + (b'' if label is None else b'bench_badge=' + label.encode() + b'\n')


def state(label):
    data = content(label)
    return {'label': label, 'sha256': sha(data), 'bytes': len(data), 'mode': MODE}


def regular(path, limit=4096):
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise Conflict('missing file: ' + path.name) from exc
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
        raise Conflict('not a small private regular file: ' + path.name)
    return path.read_bytes(), stat.S_IMODE(info.st_mode)


def atomic(path, data, mode=0o600):
    """Fsync a temporary image, replace, fsync parent. Single fixture writer only."""
    fd, name = tempfile.mkstemp(prefix='.proof-write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def create_fixture(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or list(root.iterdir()):
        raise Conflict('requires a new empty host temporary directory')
    (root / 'HOST_FIXTURE_ONLY').write_bytes(MARKER)
    (root / 'fixture.conf').write_bytes(BASELINE)
    (root / 'fixture.conf').chmod(MODE)
    (root / 'unrelated.txt').write_bytes(b'not owned by this feature\n')
    return Engine(root)


class Engine:
    """Shared transition logic for one host fixture file and exact byte images."""
    def __init__(self, root, *, images=None, feature=FEATURE, mode=MODE):
        # Small private adapter seam, not a manifest/plugin or device architecture.
        self._images = ({None: BASELINE, **{name: content(name) for name in LABELS}}
                        if images is None else dict(images))
        if (None not in self._images or not 1 <= len(self._images) <= 3
                or any(key is not None and (type(key) is not str or not key or len(key) > 32)
                       for key in self._images)
                or any(type(value) is not bytes or len(value) > 100000 for value in self._images.values())
                or type(mode) is not int or not 0 <= mode <= 0o777
                or type(feature) is not str or not feature or len(feature) > 64):
            raise Conflict('invalid host byte-image profile')
        self._feature, self._mode = feature, mode
        self._limit = max(4096, *(len(data) for data in self._images.values()))
        self.root = Path(root)
        if self.root.is_symlink() or not self.root.is_dir():
            raise Conflict('invalid fixture root')
        if regular(self.root / 'HOST_FIXTURE_ONLY')[0] != MARKER:
            raise Conflict('host fixture marker required')
        self.target = self.root / 'fixture.conf'
        self.store = self.root / '.proof'
        if self.store.exists() or self.store.is_symlink():
            if self.store.is_symlink() or not self.store.is_dir():
                raise Conflict('invalid journal directory')
        self.journal_path = self.store / 'journal.json'

    def _content(self, label):
        try:
            return self._images[label]
        except (KeyError, TypeError) as exc:
            raise Conflict('unsupported configuration') from exc

    def _state(self, label):
        data = self._content(label)
        return {'label': label, 'sha256': sha(data), 'bytes': len(data), 'mode': self._mode}

    def _read(self):
        return regular(self.target, limit=self._limit)

    def _image(self, descriptor):
        return regular(self.store / (descriptor['sha256'] + '.bin'), limit=self._limit)[0], descriptor['mode']

    def _store(self, descriptor):
        self.store.mkdir(mode=0o700, exist_ok=True)
        path = self.store / (descriptor['sha256'] + '.bin')
        wanted = self._content(descriptor['label'])
        if path.exists() or path.is_symlink():
            if regular(path, limit=self._limit)[0] != wanted:
                raise Conflict('damaged stored image; preserving it')
        else:
            if descriptor['label'] is None:
                observed, mode = self._read()
                if (observed, mode) != (wanted, self._mode):
                    raise Conflict('original changed before snapshot')
                wanted = observed  # preserve observed original bytes, not a reconstructed restore
            atomic(path, wanted)

    def _journal(self):
        if not self.journal_path.exists() and not self.journal_path.is_symlink():
            return None
        try:
            j = json.loads(regular(self.journal_path)[0])
            if j['schema'] != 1 or j['feature'] != self._feature or j['target'] != 'fixture.conf':
                raise ValueError('wrong schema/feature/target')
            descriptors = [j['original'], j['current']]
            if j['original'] != self._state(None):
                raise ValueError('unsupported original')
            if j['pending'] is not None:
                descriptors += [j['pending']['before'], j['pending']['after']]
                if j['pending']['before'] != j['current']:
                    raise ValueError('inconsistent transaction')
            for item in descriptors:
                if item != self._state(item['label']) or self._image(item) != (self._content(item['label']), self._mode):
                    raise ValueError('damaged/unsupported stored image')
            return j
        except (KeyError, TypeError, ValueError) as exc:
            raise Conflict('invalid journal/images: ' + str(exc)) from exc

    def _save(self, journal):
        atomic(self.journal_path, (json.dumps(journal, sort_keys=True, indent=2) + '\n').encode())

    def _current(self, journal):
        if journal and journal['pending'] is not None:
            raise Conflict('interrupted operation; explicit recover required')
        current = journal['current'] if journal else self._state(None)
        if self._read() != (self._content(current['label']), self._mode):
            raise Conflict('unsupported base or later changes; preserving bytes/mode')
        return current

    def plan(self, label='DEMO'):
        after = self._state(label)
        current = self._current(self._journal())
        action = ('no_op' if current == after else 'uninstall' if label is None
                  else 'apply' if current['label'] is None else 'reconfigure')
        return {'feature': self._feature, 'target': 'fixture.conf', 'action': action,
                'before': current, 'after': after, 'original_sha256': sha(self._content(None))}

    def apply(self, label='DEMO', _checkpoint=None):
        return self._transition(label, _checkpoint)

    def uninstall(self, _checkpoint=None):
        return self._transition(None, _checkpoint)

    def _replace(self, before, after):
        # Guard observed edits, but no atomic CAS/concurrent-writer guarantee.
        if self._read() != (self._content(before['label']), self._mode):
            raise Conflict('changed before replace; preserving current file')
        image, mode = self._image(after)
        atomic(self.target, image, mode)
        if self._read() != (image, mode):
            raise Conflict('post-write verification failed')

    def _transition(self, label, checkpoint):
        plan = self.plan(label)
        if plan['action'] == 'no_op':
            return {'status': 'no_op', 'verified': True, 'label': label}
        journal = self._journal()
        self._current(journal)
        for item in (self._state(None), plan['before'], plan['after']):
            self._store(item)
        if journal is None:
            journal = {'schema': 1, 'feature': self._feature, 'target': 'fixture.conf',
                       'original': self._state(None), 'current': plan['before'], 'pending': None}
        journal['pending'] = {'operation': plan['action'], 'before': plan['before'], 'after': plan['after']}
        self._save(journal)  # originals/images + intent durable before target mutation
        if checkpoint:
            checkpoint('prepared')
        self._replace(plan['before'], plan['after'])
        if checkpoint:
            checkpoint('written')
        journal.update(current=plan['after'], pending=None)
        self._save(journal)
        return {'status': plan['action'], 'verified': True, 'label': label}

    def verify(self):
        journal = self._journal()
        if journal and journal['pending'] is not None:
            before, after = journal['pending']['before'], journal['pending']['after']
            observed = self._read()
            known = [item for item in (before, after) if observed == (self._content(item['label']), self._mode)]
            if not known:
                raise Conflict('unknown bytes during incomplete transaction; preserved')
            return {'status': 'incomplete', 'verified': False, 'observed_label': known[0]['label']}
        current = self._current(journal)
        return {'status': 'uninstalled' if current['label'] is None else 'installed',
                'verified': True, 'label': current['label']}

    def recover(self):
        """Explicit abort to previous stable image, never auto-retry or guess."""
        journal = self._journal()
        if journal is None or journal['pending'] is None:
            return self.verify()
        before, after = journal['pending']['before'], journal['pending']['after']
        current = self._read()
        if current == (self._content(after['label']), self._mode):
            self._replace(after, before)
        elif current != (self._content(before['label']), self._mode):
            raise Conflict('recovery conflict; unknown/later bytes preserved')
        journal.update(current=before, pending=None)
        self._save(journal)
        return {'status': 'recovered_previous', 'verified': True, 'label': before['label']}
