# Use the host CLI

For wiring, start with [bench setup](bench-setup.md).
The CLI runs on your computer. Profile commands use UART; resource sampling uses
an existing trusted SSH connection. It does not install a daemon or package on the CMU.

## Install and preview

From the checkout:

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/oc --help
.venv/bin/oc bench setup
~~~

The last command is a **dry run**: no device opens, changes or receipt writes.
Bench commands below can also use python -m open_connect. Run commands directly;
Herdr is used for agent communication.

## Bench profile

The current profile enables silent Entertainment UI testing through Mazda's
Audio Manager API. No TAU or speakers are required. This does not emulate the
tuner or establish working playback.

| Command | Behavior |
| --- | --- |
| oc bench setup | Enable the whole current development profile |
| oc bench status | Read actual state and whether our ownership still applies |
| oc bench teardown | Disable only a change owned by setup on this service instance |

Before live use, establish an idle root shell on **74.00.324A NA**, then close
your serial terminal. Bench-profile commands do not log in or reset the device. Our current
runner accepts FT232R 0403:6001 adapters. Set `OC_UART_SERIAL` to your exact serial
number before launching commands; the project bench defaults to A9048JM0.

Choose one operation; use a fresh bundle directory each time:

~~~sh
.venv/bin/oc bench status --live --solicit-prompt --bundle runs/my-status
.venv/bin/oc bench setup --live --solicit-prompt --bundle runs/my-setup
.venv/bin/oc bench teardown --live --solicit-prompt --bundle runs/my-teardown
~~~

The profile is **runtime-only**, with no startup hook. After reboot/service
replacement, check status before setup. Teardown leaves pre-enabled audio alone
and does not uninstall product mods or restore every user setting.

The private receipt is .bench-state/profile.json relative to the working directory.
Run from the same checkout, or pass the same explicit --state path each time.
Keep it; deleting it discards ownership information. Use --state to select a
different receipt explicitly. Only one program should own UART at a time.
--solicit-prompt sends one CR: use it only when the shell is known to be idle.

## Private firmware checks

Use the [installer development guide](installer-development.md#private-firmware-checks)
to check the actual Make/shell release against private exact-original firmware
files. This is host validation and does not install anything on the CMU.

Use the maintained USB backend for installation, settings, recovery and removal.

## Record RAM, CPU and I/O over SSH

Use an already authenticated UID-0 SSH alias for exact **74.00.324A NA**.
Preview the request, then choose a fresh private output directory:

~~~sh
oc bench sample --seconds 180 --interval 1
oc bench sample --live --host my-cmu --seconds 180 --interval 1 \
  --bundle runs/my-resources
~~~

Pass `--ssh-config /path/to/config` if the alias uses a separate OpenSSH config.
The host key must already be trusted; the tool does not provision access or accept
unknown host keys. It uses the system SSH client and opens no UART or camera.

The finite shell collector runs from stdin and only reads the CMU. It checks the
firmware and binds the trace to one boot. No startup hook, package, settings change
or target output file is created. `--seconds` accepts 1–600; `--interval` is a
1–30 second **minimum pause**, with actual sample start/end times retained.
The default process names are `jci`, `opera`, and `carplayd`; repeated `--process`
options replace that list with exact kernel comm names.

The bundle contains the exact collector sources and hashes, raw SSH output,
`trace.json` with system/process counters, and `memory.csv` with named kernel RAM
fields in their original kB units. Missing fields stay empty; a process that exits
or reuses its PID during a read is marked unstable. CPU ticks and I/O counters are
retained for interval analysis. RSS includes shared pages; do not sum it as physical
RAM usage. This collector does not take PSS snapshots.

`outcome=recorded` establishes a complete resource trace, not a timing result or
performance improvement. Record the phone, workload, feature/service selections
and exact installed build with the batch. Collection starts when SSH runs the
script; it does not cover earlier startup. Keep raw bundles private and publish
reviewed derived results following [Performance evidence](performance.md).

## USB installer build

The owner installer is separate from `oc`. Build its complete USB bundle with
Make, Clang, LLD, llvm-objcopy, OpenSSL and zip:

~~~sh
make release OUT=runs/my-release
~~~

This does not require Python, an installed `oc`, private OEM inputs or a connected
CMU. CI provides the ZIP and `SHA256SUMS` as `usb-installer`. See the
[installer development guide](installer-development.md) for builds and qualification limits
and [Quick start](usb-installer.md) for installation.
Checksums detect damaged payloads; they are not a package-signing scheme.

## Low-level UART

First [open the serial terminal](bench-setup.md#first-boot) and establish an
authenticated UID-0 shell on exact 74.00.324A NA. UART login credentials on the
replacement v74 bench remain unqualified; owner-key SSH works separately.
Close the terminal before running a live command. These operations do not log in
automatically. Read-only receive needs no authenticated shell.

~~~sh
.venv/bin/oc uart --help
.venv/bin/oc uart --action identify
~~~

The second command previews an identity check. Live operations additionally need
--live and a fresh --bundle. The existing receive, identify, command and restricted
exact-file export actions are available; consult help for their arguments.
Receive is read-only and never solicits a prompt.

## Read the result

Exit 0 means the reported operation completed—including a dry run or local build,
which does not prove device state. For any nonzero exit, read `outcome` and the
saved bundle: `refused` with `device_operations=false` means nothing was launched;
`incomplete_preserved` means device work may have happened. UART exit 2 means
uncertain execution. Never infer “nothing changed” from an error or blindly retry.

For active bench setup, require outcome=verified and bench_profile.active=true.
A verified status may correctly report inactive or expired ownership.
Raw UART evidence is private under the requested runs/ bundle.

[Host tests](https://github.com/aeharding/open-connect/blob/main/CONTRIBUTING.md) cover these operations without hardware.
The [v74 qualification record](installer-development.md#qualification) describes
the silent bench fixture and its limits.

## Capture the CMU screen over SSH

With authenticated SSH on the v74 bench, Mazda’s Wayland screenshot utility
returns the current 800 × 480 display as a PNG. Replace `my-cmu` with your
verified SSH host alias. Pick a fresh output filename on your computer.

~~~sh
ssh -T my-cmu 'sh -s' > home.png <<'CMU'
set -eu
d=$(mktemp -d /tmp/oc-screen-XXXXXX)
trap 'rm -f "$d/wayland-screenshot.png"; rmdir "$d"' EXIT
cd "$d"
XDG_RUNTIME_DIR=/tmp WAYLAND_DISPLAY=wayland-0 timeout -t 8 /usr/bin/screenshot >/dev/null
cat wayland-screenshot.png
CMU
~~~

The PNG captures Mazda’s Wayland surface. CarPlay can use a separate projection
plane, so use a hardware camera to establish what that screen actually shows.

This uses the system SSH client, as does resource sampling above. General SSH
support for the other bench operations remains tracked in
[issue #15](https://github.com/aeharding/open-connect/issues/15).
