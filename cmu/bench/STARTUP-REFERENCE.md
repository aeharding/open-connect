# Stock startup coverage experiment

This playground experiment collects startup resources locally, independently of
SSH readiness. It is not a completed stock/Open Connect comparison. The initial
SSH-started coverage trial (revision 9b2971f) first sampled at uptime 41.09 s,
after native UI was already visible; it cannot establish early memory usage.
That method is superseded here, with its source and evidence kept unchanged.
This experiment uses the existing Mac bench's receive-only
FTDI UART, one camera and a CH340 ACC relay (A001 protocol, 9600 baud).

```sh
python -m open_connect.startup_reference
python -m open_connect.startup_reference --live --host my-cmu \
  --bundle runs/startup-1
```

Supply `--ssh-config` for a separate trusted alias configuration. Other benches
must set their `OC_UART_SERIAL`, relay `--relay-location` and `--camera-uid`
explicitly. The reference resolves the unique UID to a unique camera name, then
uses its freshly enumerated FFmpeg index; unrelated continuity cameras are allowed.
The code must be committed and unchanged before a live run. The preflight
requires exact 74.00.324A NA stock startup/login/service/capability files,
Open Connect absent, absent touch override, ACC on and root read-only.

Install the temporary profile before running the observer. Build `flush` using
the repository Makefile, and stage it with `startup-profile.sh`, `startup-hook.sh`,
`startup-launch.sh` and the maintained `metrics.sh` in a new
`/tmp/oc-dev-startup-*` directory. Supply a five-line `files.sha256` containing
SHA256 and basename for those files. Verify the complete upload before running
`sh /tmp/oc-dev-startup-NAME/startup-profile.sh install CURRENT_BOOT_UUID`.
It requires the exact empty OEM `stage_1.sh` and preserves its bytes, metadata
and original inode before atomically replacing it. Independent undo is
`sh /tmp/mnt/data_persist/oc-bench-startup/startup-profile.sh --check` or
`--restore`. Unknown target edits are refused. Restoration needs a subsequent
normal restart to verify original startup and absence of the RAM observer.
Do not remove the recovery directory before that verification.

The hook backgrounds a detached, finite system-only collector at Service
Manager's stage 1. It records 180 seconds with a minimum one-second pause to
`/tmp/oc-bench-startup`, limited to 4 MiB per file. The actual first sample uptime
establishes early coverage; the hook is not assumed to cover kernel startup.
The profile is separate from product startup files and stays identical across
future stock/Open Connect measurements. Describe this condition as stock features
with bench instrumentation, not a byte-identical stock filesystem. RAM output
itself consumes memory; retain its size with results.

The relay is turned off once for 30 seconds, then on once. UART receives only;
no login or input events are sent. Video/UART observe 120 seconds after ACC on.
There is no SSH polling during startup. At 195 seconds the host retrieves the
completed trace, checking new boot identity, source digests, exit status, full
trace digest and sample framing. If it failed, RAM/raw evidence is retained;
retrieval never starts a replacement collector. The supply is untouched.

Retain actual sample bounds and any interval before the first sample. Kernel uptime
and host ACC times have different origins. The AVFoundation input start and video
PTS are recorded in the existing camera artifacts; qualify their relation to the
host monotonic clock before computing external startup durations. Actual frame
spacing, camera exposure/settings and uncertainty belong with the results.
Camera launch time is not the first frame's capture time.

The optional host-only clock probe uses an already authorized camera and does
not request permission or change CMU state:

```sh
clang -fobjc-arc -Wall -Wextra -Werror -Wno-deprecated-declarations \
  -include stdatomic.h -framework Foundation -framework AVFoundation \
  -framework CoreMedia tooling/avfoundation-clock.m -o runs/avfoundation-clock
runs/avfoundation-clock CAMERA_UID
```

It prints raw sample PTS, that PTS converted to the CoreMedia host clock,
current CoreMedia host time and current mach_absolute_time in seconds. The
reference camera produced identical raw/converted timestamps on this Mac, and
CoreMedia host time matched the clock used by Python monotonic. This qualifies
the clock domain, not physical sensor/display latency. FFmpeg 7.1.1 assigns the
[sample presentation time to video packet PTS](https://github.com/FFmpeg/FFmpeg/blob/n7.1.1/libavdevice/avfoundation.m)
and [subtracts input start time by default](https://github.com/FFmpeg/FFmpeg/blob/n7.1.1/fftools/ffmpeg_demux.c).
Retain the input start from stderr and the decoded frame timestamps. This initial
coverage trial still makes no precise external startup-duration claim.

After capture, `python -m open_connect.clock_reference --live --host my-cmu
--expect-boot BOOT_UUID --bundle runs/clock-1` bounds the CMU kernel-uptime origin
against host monotonic using seven exchanges in one existing trusted SSH session.
Use `--ssh-config` where needed. It installs nothing, retains raw exchanges,
accounts for uptime quantization and rejects inconsistent bounds. Do not confuse
its clock bound with camera sensor latency or physical ACC relay latency.

This trial sends no UI input and does not qualify usable touch/commander input,
audio or projection solely because a process/network interface appears. Keep
observer failures separate from CMU behavior. Never blindly repeat an uncertain
relay transmission.
