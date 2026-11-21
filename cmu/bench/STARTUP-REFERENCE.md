# Stock startup coverage experiment

This playground experiment asks whether a post-SSH resource collector starts
early enough to observe the useful part of stock startup. It is not a completed
stock/Open Connect comparison. It uses the existing Mac bench's receive-only
FTDI UART, one camera and a CH340 ACC relay (A001 protocol, 9600 baud).

```sh
python -m open_connect.startup_reference
python -m open_connect.startup_reference --live --host my-cmu \
  --bundle runs/startup-1
```

Supply `--ssh-config` for a separate trusted alias configuration. Other benches
must set their `OC_UART_SERIAL`, relay `--relay-location` and `--camera-uid`
explicitly. This reference only supports one camera at AVFoundation index 0.
The code must be committed and unchanged before a live run. The preflight
requires exact 74.00.324A NA stock startup/login/service/capability files,
Open Connect absent, absent touch override, ACC on and root read-only.

The relay is turned off once for 30 seconds, then on once. UART receives only;
no login or input events are sent. Video/UART observe 120 seconds after ACC on.
Read-only SSH readiness attempts bind to a new boot; the first successful query
launches one 120-second system-counter trace. Every attempt and raw failure is
retained. The resource trace can outlast the video. No files/settings are changed
on the CMU; normal ignition handling and SSH may update normal operating state.
The supply is untouched.

Retain actual sample bounds and the unobserved interval before SSH. Kernel uptime
and host ACC times have different origins. The AVFoundation input start and video
PTS are recorded in the existing camera artifacts; qualify their relation to the
host monotonic clock before computing external startup durations. Actual frame
spacing, camera exposure/settings and uncertainty belong with the results.
Camera launch time is not the first frame's capture time.

This trial sends no UI input and does not qualify usable touch/commander input,
audio or projection solely because a process/network interface appears. Keep
observer failures separate from CMU behavior. Never blindly repeat an uncertain
relay transmission.
