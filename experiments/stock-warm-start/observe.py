#!/usr/bin/env python3
"""ONE stock warm restart. Review-only by default; sole operator owns live execution."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from cmu_bench.session import AdapterLock, Bundle, Session, open_adapter, PROMPT, ANSI

REBOOT = b'/sbin/reboot\r'
MAX_RX = 4 * 1024 * 1024
SOURCE = '/jci/gui/apps/system/js/systemApp.js'
ORIGINAL = '64785:9457:1433953097:94058:755:1018:3015:1'
MD5 = '584c67f7186ada6bae9aae1be59b5cd0'
CRC = '376717896 94058'
# Kernel messages may arrive directly, with printk time, or replayed through
# the installed logger while getty's prompt is interleaved on the same line.
KERNEL_BANNER = re.compile(
    rb'(?:^|[\r\n])(?:(?:cmu )?login:[ \t]*)?'
    rb'(?:[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}[ \t]+kernel\[[0-9]*\][ \t]+'
    rb'[A-Za-z]+[ \t]+\([^\r\n)]{0,100}\)[ \t]+)?'
    rb'(?:\[[ \t]*[0-9]+(?:\.[0-9]+)?\][ \t]*)?Linux version [^\r\n]+')
CHECK = r'''set -f
p=/jci/gui/apps/system/js/systemApp.js
for d in /jci /jci/gui /jci/gui/apps /jci/gui/apps/system /jci/gui/apps/system/js;do
 test -d "$d" && test ! -L "$d" && test "$(readlink -f "$d")" = "$d" || exit 1
done
test -f "$p" && test ! -L "$p" && test "$(readlink -f "$p")" = "$p" || exit 1
printf 'SWST|META|';stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' "$p" || exit 1
printf 'SWST|HASH|';md5sum < "$p" || exit 1
printf 'SWST|CRC|';cksum < "$p" || exit 1
awk '$1=="/dev/ffx01p1" && $2=="/" && $3=="relfs" {print "SWST|ROOT|"$0}' /proc/mounts
printf 'SWST|UPTIME|';cat /proc/uptime || exit 1
printf 'SWST|BOOT_ID|';cat /proc/sys/kernel/random/boot_id || exit 1
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_output(status, raw, before=None):
    if status != 0:
        raise RuntimeError('stock persistence check nonzero')
    found = {}
    for line in raw.decode('ascii', 'strict').replace('\r', '').splitlines():
        if line.startswith('SWST|'):
            _, key, value = line.split('|', 2)
            if key in found:
                raise RuntimeError('duplicate persistence field')
            found[key] = value.strip()
    if set(found) != {'META', 'HASH', 'CRC', 'ROOT', 'UPTIME', 'BOOT_ID'}:
        raise RuntimeError('missing/unexpected persistence field')
    meta = found['META'].split(':')
    expected = ORIGINAL.split(':')
    # Before request require the known active inode. After boot record actual inode;
    # persistence promises bytes/mode/UID/GID/mtime, not unchanged inode allocation.
    metadata_ok = (found['META'] == ORIGINAL if before is None else
                   len(meta) == 8 and meta[1].isdigit() and int(meta[1]) > 0 and
                   meta[:1] + meta[2:] == expected[:1] + expected[2:])
    if not metadata_ok or found['HASH'].split() != [MD5, '-'] or ' '.join(found['CRC'].split()) != CRC:
        raise RuntimeError('source is not exact recorded AS-FOUND original/metadata')
    fields = found['ROOT'].split()
    if len(fields) != 6 or fields[:3] != ['/dev/ffx01p1', '/', 'relfs']:
        raise RuntimeError('physical root row mismatch')
    opts = fields[3].split(',')
    if 'ro' not in opts or 'rw' in opts:
        raise RuntimeError('physical root is not RO')
    found['uptime_seconds'] = float(found['UPTIME'].split()[0])
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', found['BOOT_ID']):
        raise RuntimeError('invalid boot identity')
    if before and (found['BOOT_ID'] == before['BOOT_ID'] or found['uptime_seconds'] >= before['uptime_seconds']):
        raise RuntimeError('new kernel boot/uptime not established')
    return found


class BootGate:
    """Parse only RX after request; never send bootloader input or repeat credentials."""
    def __init__(self):
        self.raw = bytearray()
        self.stage = 'boot'
        self.kernel_seen = False
        self.scan = 0
        self.kernels = 0
        self.loaders = 0
        self.events = []

    def feed(self, chunk):
        self.raw.extend(chunk)
        if len(self.raw) > MAX_RX:
            raise RuntimeError('restart RX cap; preserve unknown, no retry')
        clean = ANSI.sub(b'', bytes(self.raw))
        kernels = list(KERNEL_BANNER.finditer(clean))
        loaders = list(re.finditer(rb'(?:^|[\r\n])U-Boot(?: |\b)', clean))
        if len(kernels) > 1 or len(loaders) > 1:
            raise RuntimeError('repeated boot banner; possible loop, no login')
        if kernels and loaders and loaders[-1].start() > kernels[0].start():
            raise RuntimeError('bootloader returned after kernel; stop')
        if kernels and not self.kernel_seen:
            self.kernel_seen = True
            self.scan = kernels[0].end()
            self.events.append('new_kernel_banner')
        if not self.kernel_seen:
            return None
        tail = clean[self.scan:]
        if re.search(rb'(?:^|[\r\n])(?:Login incorrect|Authentication failure)', tail, re.I):
            raise RuntimeError('authentication refused; no retry')
        patterns = [('login', rb'(?:^|[\r\n])(?:cmu )?login:[ \t]*'),
                    ('password', rb'(?:^|[\r\n])Password:[ \t]*'),
                    ('shell', PROMPT.pattern), ('continuation', rb'(?:^|[\r\n])> ')]
        found = []
        for kind, pattern in patterns:
            found += [(m.start(), m.end(), kind) for m in re.finditer(pattern, tail, re.I)]
        if not found:
            return None
        start, end, kind = min(found)
        self.scan += end
        expected = {'boot': 'login', 'username_sent': 'password', 'password_sent': 'shell'}
        if kind != expected.get(self.stage):
            raise RuntimeError('unexpected/repeated ' + kind + '; no further TX')
        self.stage = {'login': 'username_sent', 'password': 'password_sent', 'shell': 'shell'}[kind]
        self.events.append(kind)
        return kind


class Video:
    def __init__(self, bundle, index):
        self.bundle, self.index = bundle, index
        self.proc = None
        self.ready = threading.Event()
        self.rows = []
        self.stop_requests = []

    def start(self):
        self.path = self.bundle.path / 'camera.mkv'
        self.stderr = (self.bundle.path / 'camera.stderr.txt').open('xb')
        self.argv = ['ffmpeg', '-hide_banner', '-nostdin', '-n', '-f', 'avfoundation',
                     '-framerate', '5', '-video_size', '1280x720', '-pixel_format', 'uyvy422',
                     '-i', str(self.index) + ':none', '-an', '-c:v', 'mjpeg', '-q:v', '4',
                     '-t', '185', '-f', 'matroska', '-cluster_time_limit', '1000',
                     '-flush_packets', '1', '-progress', 'pipe:1', '-nostats', str(self.path)]
        self.started = time.monotonic()
        # Explicit child defaults avoid inherited ignored INT/TERM. exec keeps the
        # exact owned Popen PID; no fork-time Python callback or shell is involved.
        self.launch_argv = [sys.executable, '-c',
            'import os,signal,sys; signal.signal(signal.SIGINT,signal.SIG_DFL); '
            'signal.signal(signal.SIGTERM,signal.SIG_DFL); os.execvp(sys.argv[1],sys.argv[1:])',
            *self.argv]
        self.proc = subprocess.Popen(self.launch_argv, stdout=subprocess.PIPE, stderr=self.stderr)
        self.bundle.event('camera_started', pid=self.proc.pid, argv=self.argv,
                          launch_argv=self.launch_argv, child_signal_defaults=['SIGINT','SIGTERM'])
        self.worker = threading.Thread(target=self._progress, daemon=True)
        self.worker.start()
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if self.ready.wait(.05):
                return
            if self.proc.poll() is not None:
                break
        raise RuntimeError('camera produced no confirmed frame before request; no reboot')

    def _progress(self):
        for line in iter(self.proc.stdout.readline, b''):
            row = dict(monotonic_ns=time.monotonic_ns(), line=line.decode('utf8', 'replace').strip())
            self.rows.append(row)
            if row['line'].startswith('frame=') and int(row['line'].split('=')[1].strip()) >= 1:
                self.ready.set()

    def stop(self):
        if not self.proc:
            return
        if self.proc.poll() is None:
            self.stop_requests.append(dict(signal='SIGINT',monotonic_ns=time.monotonic_ns()))
            self.proc.send_signal(signal.SIGINT)  # exact owned child; streamable container
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.stop_requests.append(dict(signal='SIGTERM',monotonic_ns=time.monotonic_ns()))
                self.proc.terminate()
                self.proc.wait(timeout=3)
        self.worker.join(timeout=2)
        self.stderr.close()
        self.bundle.save('camera-progress.json', (json.dumps(self.rows, indent=2)+'\n').encode())
        report = dict(pid=self.proc.pid, argv=self.argv, launch_argv=self.launch_argv,
                      stop_requests=self.stop_requests, returncode=self.proc.returncode,
                      host_elapsed_s=time.monotonic()-self.started)
        try:
            result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_frames', '-select_streams', 'v:0',
                                     '-show_entries', 'frame=best_effort_timestamp_time:stream=nb_read_frames,avg_frame_rate,duration:format=duration',
                                     '-of', 'json', str(self.path)], capture_output=True, timeout=12)
            report.update(ffprobe_rc=result.returncode, ffprobe_stderr=result.stderr.decode('utf8','replace'))
            report['ffprobe'] = json.loads(result.stdout)
            stream = report['ffprobe']['streams'][0]
            duration = float(stream.get('duration') or report['ffprobe']['format']['duration'])
            report['decoded_frames'] = int(stream['nb_read_frames'])
            report['actual_frames_per_video_second'] = report['decoded_frames']/duration
            report['video_duration_s'] = duration
            pts = [float(f['best_effort_timestamp_time']) for f in report['ffprobe']['frames']]
            if (result.returncode != 0 or report['decoded_frames'] != len(pts) or len(pts) < 2
                    or duration <= 0 or any(b <= a for a,b in zip(pts,pts[1:]))):
                raise RuntimeError('video lacks verified frames/increasing timestamps/duration')
            report.update(first_frame_pts_s=pts[0],last_frame_pts_s=pts[-1],
                          actual_interval_fps=(len(pts)-1)/(pts[-1]-pts[0]), video_verified=True)
        except Exception as exc:
            report['probe_error'] = str(exc)
        self.bundle.save('camera-result.json', (json.dumps(report, indent=2)+'\n').encode())
        if report.get('video_verified') is not True:
            raise RuntimeError('camera final validation failed; see camera-result.json')


def private_credentials(path):
    p = Path(path)
    info = p.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
        raise RuntimeError('credentials require owned private regular file')
    value = json.loads(p.read_text())
    if set(value) != {'username', 'password'} or value['username'] != 'root':
        raise RuntimeError('established root credential only')
    result = []
    for key in ('username', 'password'):
        item = value[key].encode('ascii')
        if not item or any(x < 32 or x > 126 for x in item) or len(item) > 128:
            raise RuntimeError('invalid credential data')
        result.append(item + b'\r')
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live', action='store_true')
    p.add_argument('--bundle', type=Path)
    p.add_argument('--credentials', type=Path)
    p.add_argument('--profile', type=Path)
    p.add_argument('--owner', default='t14 sole operator')
    p.add_argument('--camera-index', type=int)
    p.add_argument('--solicit-prompt', action='store_true')
    args = p.parse_args(argv)
    if not args.live:
        print(json.dumps(dict(mode='review_only', reboot_ascii=REBOOT.decode(), seconds=180,
                              credential_attempts=1, bootloader_TX=0, video='1280x720 requested5fps',
                              source='exact AS-FOUND O, physical rootRO before+after'), indent=2))
        return 0
    if not all((args.bundle, args.credentials, args.profile)) or args.camera_index is None or args.camera_index < 0:
        p.error('live requires new bundle, private credentials, checked profile and camera-index')
    profile = json.loads(args.profile.read_text())
    required = {"experiments/stock-warm-start/observe.py", "cmu_bench/session.py"}
    if not required.issubset(profile.get("source_pins", {})):
        raise RuntimeError("missing checked observer/core pins")
    for name, expected in profile['source_pins'].items():
        if sha(ROOT/name) != expected:
            raise RuntimeError('checked source profile mismatch')
    if profile.get('normal_reboot_route_verified') is not True or profile.get('reboot_hex') != REBOOT.hex():
        raise RuntimeError('normal installed reboot/init route unresolved; no request')
    username, password = private_credentials(args.credentials)
    bundle = Bundle(args.bundle, 'ONE stock warm software restart', args.owner, mode='live')
    bundle.meta['profile'] = profile
    video = Video(bundle, args.camera_index)
    outcome, error, port, requested = 'failed_before_request', None, None, False
    with AdapterLock(owner=args.owner, purpose='ONE stock warm restart'):
        try:
            port = open_adapter(bundle)
            session = Session(port, bundle, timeout=20, output_cap=MAX_RX)
            session.observe_prompt(solicit=args.solicit_prompt)
            session.identify()
            before = checked_output(*session.execute(CHECK))
            bundle.save('before.json', (json.dumps(before, indent=2)+'\n').encode())
            video.start()
            # One absolute observation deadline includes request TX, boot and postchecks.
            start = time.monotonic()
            deadline = start + 180
            received = bytearray()
            requested = True  # mark uncertain BEFORE first write attempt
            session.state, session.identity = 'intentional_restart', None
            bundle.event('restart_request', command_hex=REBOOT.hex(), no_framed_END_expected=True,
                         deadline_monotonic=deadline)
            session._send(REBOOT, deadline=min(deadline, start+2), received=received)
            gate = BootGate()
            credentials_sent = []
            pending_rx = bytearray(received)
            while time.monotonic() < deadline:
                if pending_rx:
                    chunk = bytes(pending_rx)
                    pending_rx.clear()
                else:
                    chunk = session._read(received, until=deadline)
                if not chunk:
                    continue
                event = gate.feed(chunk)
                if event:
                    bundle.event('restart_transition', transition=event)
                if event in ('login', 'password'):
                    credential = username if event == 'login' else password
                    credentials_sent.append(event)
                    # Private lossless TX bundle; never print credentials.
                    session._send(credential, deadline=min(deadline, time.monotonic()+2), received=received, on_rx=pending_rx.extend)
                if event == 'shell':
                    session.state = 'shell'
                    session.timeout = min(20, deadline-time.monotonic())
                    if session.timeout <= 1:
                        raise TimeoutError('no time for bounded fresh identity')
                    session.identify()
                    session.timeout = min(20, deadline-time.monotonic())
                    after = checked_output(*session.execute(CHECK), before=before)
                    bundle.save('after.json', (json.dumps(after, indent=2)+'\n').encode())
                    bundle.event('post_restart_verified', elapsed_s=time.monotonic()-start,
                                 root_identity=session.identity, source_O=True, physical_root_RO=True)
                    # Retain visual settling after readiness; never exceed overall deadline.
                    tail = min(deadline, time.monotonic()+20)
                    while time.monotonic() < tail:
                        extra = session._read(received, until=tail)
                        if extra:
                            gate.raw.extend(extra)
                            if len(list(KERNEL_BANNER.finditer(ANSI.sub(b'', bytes(gate.raw))))) > 1:
                                raise RuntimeError('second kernel during settling; stop')
                    outcome = 'stock_restart_access_O_RO_verified'
                    break
            else:
                raise TimeoutError('180s restart readiness deadline; no retry/recovery')
        except BaseException as exc:
            error = type(exc).__name__ + ': ' + str(exc)
            outcome = 'unknown_after_request' if requested else 'failed_before_request'
        finally:
            try:
                video.stop()
            except BaseException as exc:
                error = (error or '') + '; camera cleanup: ' + str(exc)
                if outcome == 'stock_restart_access_O_RO_verified':
                    outcome = 'access_O_RO_verified_video_failed'
                elif requested:
                    outcome = 'unknown_after_request'
            if port is not None:
                port.close()
                bundle.meta['port_closed'] = True
            bundle.finish(outcome, error)
    print(json.dumps(dict(outcome=outcome, error=error, bundle=str(args.bundle))))
    return 0 if outcome == 'stock_restart_access_O_RO_verified' else 2

if __name__ == '__main__':
    raise SystemExit(main())
