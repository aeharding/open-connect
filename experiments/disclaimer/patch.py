"""OEM55-only HOST prototype. Builds private artifacts; never installs to a CMU."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

FIRMWARE = '55.00.750B/cmu150_NA'
TARGET = '/jci/gui/apps/system/js/systemApp.js'
BASE_SHA256 = '985cbcbeb1dedf11b76f61ffa1224e43165f80d8eb9c8d5d853d118d2eec3432'
BASE_LENGTH = 94058
START = b'systemApp.prototype._displayedDisclaimer = function()'
END = b'systemApp.prototype._selectCallbackDisclaimer = function('
OLD = b'this._disclaimerTime.remaining = 3500;'
NEW = b'this._disclaimerTime.remaining = 0;'
REPO = Path(__file__).resolve().parents[2]
DEFAULT_ORIGINAL = REPO / 'runs/20261113T022134-0600-t14-oem-disclaimer/originals/jci/gui/apps/system/js/systemApp.js'


class Rejected(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _replace_initial_timer(data):
    """Scope the one replacement to display entry, never the retry callback."""
    if data.count(START) != 1 or data.count(END) != 1:
        raise Rejected('missing/ambiguous OEM display/select function boundaries')
    start, end = data.index(START), data.index(END)
    if end <= start:
        raise Rejected('invalid function order')
    body = data[start:end]
    if body.count(OLD) != 1 or NEW in body:
        raise Rejected('missing/ambiguous initial timer assignment')
    return data[:start] + body.replace(OLD, NEW, 1) + data[end:]


def patch_original(original, firmware=FIRMWARE):
    if firmware != FIRMWARE or len(original) != BASE_LENGTH or sha(original) != BASE_SHA256:
        raise Rejected('unsupported firmware/base bytes; no fuzzy patch or hash override')
    return _replace_initial_timer(original)


def rollback(current, original):
    """Return saved original ONLY if current is our exact candidate."""
    expected = patch_original(original)
    if current != expected:
        raise Rejected('unknown/later changes preserved; refusing blind restore')
    return original


def plan(original):
    candidate = patch_original(original)
    return {
        'status': 'HOST_ONLY_UNINSTALLED', 'feature': 'disclaimer-fast-initial-timeout',
        'firmware': FIRMWARE, 'target': TARGET,
        'original': {'bytes': len(original), 'sha256': sha(original)},
        'candidate': {'bytes': len(candidate), 'sha256': sha(candidate)},
        'change': 'Only initial display timer3500ms ->0ms; stock retry remains3500ms',
        'event': 'Existing system Timeout; no synthetic Agree/Global.Yes',
        'semantics': 'Queue OEM timeout after displayed callback; a rendered frame may remain visible',
        'unchanged': ['OEM context/template', 'manual Agree', 'timeout context guard',
                      '3500ms retry', 'pause/resume and teardown', 'GuiFramework/heartbeat'],
        'rollback': 'Require exact candidate bytes, then restore preserved original94058B; conflict otherwise',
        'missing': ['target install/atomic replacement and read-only filesystem procedure',
                    'actual Opera/native MMUI timing, quick/cold startup and visible behavior',
                    'owned live rollback and restart/access recovery validation'],
    }


def build(original_path, output_dir):
    original = Path(original_path).read_bytes()
    candidate = patch_original(original)
    destination = Path(output_dir).resolve()
    if not any(destination.is_relative_to(REPO / name) and destination != REPO / name
               for name in ('runs', 'backups')):
        raise Rejected('full OEM/candidate artifacts must stay under private runs/ or backups/')
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, data in (('original.bin', original), ('candidate.bin', candidate)):
        with (destination / name).open('xb') as stream:
            stream.write(data)
    diff = ''.join(difflib.unified_diff(original.decode('utf-8').splitlines(True),
                                      candidate.decode('utf-8').splitlines(True),
                                      fromfile='original/systemApp.js', tofile='candidate/systemApp.js'))
    (destination / 'patch.diff').write_text(diff, encoding='utf-8', newline='')
    result = plan(original)
    result['original_source'] = str(Path(original_path).resolve())
    result['original_source_unchanged'] = Path(original_path).read_bytes() == original
    result['rollback_byte_exact'] = rollback(candidate, original) == original
    (destination / 'plan.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, default=DEFAULT_ORIGINAL)
    parser.add_argument('--output-dir', type=Path, help='NEW private runs/ or backups/ directory; no device write')
    args = parser.parse_args(argv)
    try:
        result = build(args.original, args.output_dir) if args.output_dir else plan(args.original.read_bytes())
    except (Rejected, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
