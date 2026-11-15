# Test the disclaimer bypass on a bench

**Developer preview · 55.00.750B North America only · one selected boot**

This skips the warning through Mazda's native startup decisions and keeps its
normal Home transition and intro cleanup. It preserves the OEM appearance.
The screen may briefly fade or go black before Home appears.

The preview selects private copies of the native and JavaScript changes for one
boot. It leaves the installed feature files alone. If Home does not acknowledge
startup within 90 seconds, the independent supervisor requests a normal reboot;
the consumed attempt makes the next boot use your previous configuration.

## Before you start

- A wired, working bench with an idle **root shell**, then close your serial terminal.
- Start at Mazda Home. This preview qualifies a warm software restart to Home;
  last-app, display-off and ACC/resume startup remain unqualified.
- Exactly **55.00.750B NA/cmu150_NA** and its private original files listed below.
- macOS for live UART/camera operation; an FT232R **0403:6001** adapter and webcam.
  Linux runs the public host tests; the live camera currently uses AVFoundation.
- Python 3.13, Node.js, clang, llvm-objdump, ld.lld and ffmpeg on your host.
- Private root credentials JSON: `{"username":"root","password":"YOUR_PASSWORD"}`,
  in an owner-only file (`chmod 600 /private/root.json`).

Find your UART adapter's serial number with
`python -m serial.tools.list_ports -v` after installing below. Set it explicitly;
this identifies the FTDI, not the power supply.

## Build from the release

~~~sh
git clone --branch v0.1.0-dev.1 https://github.com/aeharding/open-connect.git
cd open-connect
python3.13 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m serial.tools.list_ports -v
export OC_UART_SERIAL=YOUR_FTDI_SERIAL
~~~

Put these **original** files under a private directory, retaining their paths:

~~~text
firmware55/
├── usr/bin/autostart
└── jci/
    ├── sm/sm.conf
    ├── mmui/svcjcimmui.so
    ├── mmui/mmui_config.xml
    ├── mmui/uia/libjciuiasystem.so
    └── gui/
        ├── index.html
        ├── framework/js/BaseApp.js
        └── apps/system/js/systemApp.js
~~~

~~~sh
.venv/bin/oc feature build --workspace . --firmware /private/firmware55 \
  --output runs/preview-build --recover-on-timeout
.venv/bin/oc feature inspect --build runs/preview-build
~~~

The clean-checkout reproduction used Python 3.13.7, Node 26.7.0,
Apple clang/LLVM 21.0.0, LLD 23.1.5 and ffmpeg 7.1.1.

Build checks the supported originals and compiles/tests the changes locally.
It does not contact the CMU. OEM files, generated patches, credentials and
recordings stay private; the release contains source code only.

## Try once, then return to baseline

Use the same checkout throughout. Replace the credential path and camera index
with yours. Commands that touch the CMU require `--live`.

~~~sh
.venv/bin/oc feature prepare --build runs/preview-build \
  --state runs/preview-trial --live
.venv/bin/oc feature trial --state runs/preview-trial \
  --bundle runs/preview-start --credentials /private/root.json \
  --camera-index 0 --live
.venv/bin/oc feature status --state runs/preview-trial \
  --bundle runs/preview-status --live
.venv/bin/oc feature disable --state runs/preview-trial \
  --bundle runs/preview-baseline --credentials /private/root.json \
  --camera-index 0 --live
~~~

| Step | What happens |
| --- | --- |
| Prepare | Saves the generation and independent undo; no startup hook or reboot yet |
| Trial | Publishes the hook, reboots once, records video and checks selected code/Home |
| Status | Reads what is installed and actually running; never infers success from a build |
| Disable | Restores the original hook, boots your previous configuration and cleans holds |

Keep `runs/preview-trial`: it binds recovery to your device and prepared files.
An already-modified bench must supply its current private JS to prepare through
`--baseline-system-app /private/as-found-systemApp.js`. Baseline means that
previous configuration, not a factory reset.

**If a command returns an unknown outcome, stop and inspect its bundle.** Do not
repeat Trial or send commands into an uncertain console. The existing recovery
binding is preserved. [Result meanings and console requirements](cli.md#read-the-result).

For another trial, build and prepare fresh directories. Attempts are not
automatically renewed. This is not a persistent installation or USB installer.

## What has actually been tested?

The native/JS feature reached Home; a deliberately missing native component
triggered independent fallback to baseline. A fresh clone and fresh virtual environment then built the preview from eight
private originals and passed selected startup and independent Disable/baseline
startup automatically. Both recordings showed Home; no reboot retry or manual
reconciliation was needed. The earlier CLI console-check failure remains recorded.

Home acknowledgement is a scoped test signal, not proof of every screen or
control. ACC/resume, automatic everyday renewal and production installation remain
unfinished. [Evidence and limits](reverse-engineering.md#the-developer-cli-completed-the-featurerecovery-cycle).
