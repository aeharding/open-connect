# Use the host CLI

For wiring, start with [bench setup](bench-setup.md).
The CLI runs on your computer. It sends commands over UART; it does not install
a daemon or package on the CMU.

## Install and preview

From the checkout:

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/oc --help
.venv/bin/oc bench setup
~~~

The last command is a **dry run**: no device opens, changes or receipt writes.
All commands below can also use python -m open_connect.
When operating through Herdr, prefix the command with hc exec --cwd "$PWD".

## Bench profile

The current profile enables silent Entertainment UI testing through Mazda's
Audio Manager API. No TAU or speakers are required. This does not emulate the
tuner or establish working playback.

| Command | Behavior |
| --- | --- |
| oc bench setup | Enable the whole current development profile |
| oc bench status | Read actual state and whether our ownership still applies |
| oc bench teardown | Disable only a change owned by setup on this service instance |

Before live use, establish an idle root shell on **55.00.750B NA**, then close
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

## Developer feature trial

For the pinned release and complete walkthrough, see [Try the disclaimer bypass](disclaimer-development.md).

This is the **FW55 Home-only prototype**, not a USB installer. Use a source
checkout; the installed CLI locates the prototype builders through `--workspace`.
Supply private original files in a filesystem-shaped directory. They are never
downloaded or included in the package.

~~~sh
oc feature build --workspace . --firmware /private/firmware55 \
  --output runs/my-feature --recover-on-timeout
oc feature inspect --build runs/my-feature
oc feature prepare --build runs/my-feature --state runs/my-trial
~~~

Build creates local files and runs native/JS checks. Inspect checks those files.
Prepare defaults to a dry run; add `--live` to stage them and independent undo.
It does **not** publish the startup hook or reboot. An already-modified bench
must explicitly supply its as-found JS with `--baseline-system-app`.

The input tree needs:
`usr/bin/autostart`, `jci/sm/sm.conf`, `jci/mmui/svcjcimmui.so`,
`jci/mmui/mmui_config.xml`, `jci/mmui/uia/libjciuiasystem.so`,
`jci/gui/index.html`, and `jci/gui/framework/js/BaseApp.js` plus
`jci/gui/apps/system/js/systemApp.js`. Exact supported originals are checked.
Build tools: Python, Node.js, clang, llvm-objdump and ld.lld.

~~~sh
oc feature trial --state runs/my-trial --bundle runs/my-start \
  --credentials /private/root.json --camera-index 0 --live
oc feature status --state runs/my-trial --bundle runs/my-status --live
oc feature disable --state runs/my-trial --bundle runs/my-baseline \
  --credentials /private/root.json --camera-index 0 --live
~~~

- **Trial:** publish once, record one reboot, verify selected code and Home acknowledgement.
- **Status:** distinguish installed hook, currently loaded code and current-boot acknowledgement.
- **Disable:** restore the original startup hook, reboot into baseline, verify it and clean holds.

Credentials are a private, owner-only JSON file with `username` and `password`;
the established username must be `root`. Close other serial users first.
The current camera adapter uses macOS AVFoundation; host checks remain Linux CI.
Use a fresh bundle for each operation. Trial/status assume an established idle
shell; after uncertain console activity, reconcile that shell before using them.
An unknown request is never automatically
resent. Keep the state directory: it binds the independent on-device recovery.
Without `--recover-on-timeout`, the build observes readiness but does not request
automatic recovery. Even with it, this is one Home-specific experiment.

CPU/RAM/I/O snapshots accompany the trial and baseline. They are observations,
not repeated performance evidence. Camera footage still establishes visible behavior.

## Low-level UART

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
[Audio Manager findings](reverse-engineering.md#silent-entertainment-without-a-tau) summarize the bench result.
SSH is not implemented; [issue #15](https://github.com/aeharding/open-connect/issues/15)
tracks it. UART works without networking.
