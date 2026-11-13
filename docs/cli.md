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
your serial terminal. The CLI does not log in or reset the device. Our current
runner is pinned to FTDI 0403:6001/A9048JM0; another adapter needs configuration.

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

- Exit 0: verified live operation, or an explicitly labeled successful dry run.
- Exit 1: failure/refusal. Read the error and saved bundle.
- Exit 2: uncertain delivery/execution. Reconcile the device; do not blindly retry.

For active bench setup, require outcome=verified and bench_profile.active=true.
A verified status may correctly report inactive or expired ownership.
Raw UART evidence is private under the requested runs/ bundle.

[Host tests](../CONTRIBUTING.md) cover these operations without hardware.
[Audio Manager findings](reverse-engineering.md#silent-entertainment-without-a-tau) summarize the bench result.
SSH is not implemented; [issue #15](https://github.com/aeharding/open-connect/issues/15)
tracks it. UART works without networking.
