# Bench CLI operations

For physical assembly, start with [the hardware setup guide](README.md).

Current reference: **55.00.750B North America / cmu150_NA**.
One bench profile, operated by an agent or developer through the CLI.
There is no new CMU menu, graphical UI or per-helper public activation workflow.

[CLI contract](../docs/cli.md) · [Profile issue #1](https://github.com/aeharding/open-connect/issues/1)
· [Current device handoff](../notes/afk-session-status.txt)

## What the profile does today

`setup` enables silent Entertainment through Mazda's existing Audio Manager API
when needed. `teardown` disables it only if setup owned that change on the same
boot/bus/service instance. If audio was enabled beforehand, teardown leaves it on.
`status` reports desired profile state, actual audio state and whether ownership
still applies. Setup/teardown always operate the whole current profile.

This enables UI testing without a TAU or speakers. It is not tuner emulation,
working sound output or proof that USB/Bluetooth/CarPlay playback works.
Normal source navigation can change ordinary last-source state; teardown does not
restore every user setting.

Current setup is **runtime-only**. No vendor file, service script or startup hook
is installed. After reboot/service replacement, run status and then setup when
bench overrides are wanted. An expired receipt does not authorize disabling the
new service. Persistent startup remains a separate task with a real OEM readiness
boundary; do not add repeated force-enable calls.

Product mods are separate. Teardown of this profile alone does not make a modified
CMU stock. Disable this override when measuring actual missing-TAU/audio readiness.

## Host and hardware prerequisites

- A powered CMU and display, assembled using [the hardware guide](README.md).
- The reference FTDI adapter is pinned by VID/PID/serial (0403:6001/A9048JM0).
  UART is 115200 8N1, no flow control. The runner enumerates identity, not a remembered
  device pathname. Other adapters require deliberate configuration/qualification.
- An established idle root shell on the exact firmware. The CLI does not guess
  login state, send credentials or reset the CMU.
- Python 3 and the repo dependency, pySerial 3.5. Current checks ran on Python 3.13.
  A webcam/FFmpeg is useful for visual experiments but is not required for this API
  profile. No network or SSH is needed yet.

From the checkout, run host setup through Herdr:

```sh
hc exec --cwd "$PWD" python3 -m venv .venv
hc exec --cwd "$PWD" "$PWD/.venv/bin/python" -m pip install -r requirements.txt
hc exec --cwd "$PWD" "$PWD/.venv/bin/python" scripts/oc --help
```

Do not recreate the environment when it already works.

## Commands

A convenient shell function, using the existing Herdr execution convention:

```sh
oc() { hc exec --cwd "$PWD" "$PWD/.venv/bin/python" "$PWD/scripts/oc" "$@"; }
```

Preview without opening a device:

```sh
oc bench setup
```

This reports `dry_run_not_executed`. It does **not** set up the bench or write a
receipt. Exit 0 means the preview worked, not that the profile is active.

For an established idle shell, use a fresh private bundle for each live operation:

```sh
oc bench status --live --solicit-prompt --bundle "runs/bench-profile/$(date -u +%Y%m%dT%H%M%SZ)-status"
oc bench setup --live --solicit-prompt --bundle "runs/bench-profile/$(date -u +%Y%m%dT%H%M%SZ)-setup"
oc bench teardown --live --solicit-prompt --bundle "runs/bench-profile/$(date -u +%Y%m%dT%H%M%SZ)-teardown"
```

Choose the operation you need; do not run all three to leave the bench enabled.
Existing bundle paths are refused, preserving prior evidence. `--owner` is optional:
Herdr identity is used when available, otherwise a host-process label is generated.
`--solicit-prompt` sends one CR and must not be used after an uncertain operation
or while another foreground command may be running. Keep one UART operator.

## Results and state

The live result is JSON with `outcome`, `error`, `bundle`, and `bench_profile`.
For active setup, require `outcome=verified` and `bench_profile.active=true`.
A verified status can truthfully report off, expired or pending state.
No empty method return, launched process or agent summary establishes success.

Exit 0: verified operation (or explicitly labeled offline preview).
Exit 1: failed/refused; inspect error and saved evidence.
Exit 2: uncertain UART delivery/execution; do not automatically retry.

The private host receipt is `.bench-state/profile.json`. Keep it to preserve setup
ownership across separate CLI invocations. Raw UART and result evidence live under
the chosen ignored `runs/` bundle. Test reports should carry the emitted
`bench_profile` object so stock and overridden conditions remain distinguishable.

A pending setup/teardown survives uncertain completion. Use read-only status after
access is deliberately reconciled; teardown can finish the owned runtime disable.
Do not delete the receipt to silence a conflict or repeatedly rerun setup.
Owner/boot changes invalidate old ownership. The receipt cannot detect another
client legitimately changing the same boolean within the same service instance;
teardown remains an explicit bench action, not a full session rollback.

## SSH/networking

SSH is planned, not implemented in this entry point. The intended design reuses
the same operations/results with the Mac's OpenSSH client, verified host identity
and a lock shared with UART. DHCP/IP is routing information, not device identity.
Keep keys/config outside the repository. Check actual remote transfer support.
A dropped write must be reconciled before any retry or transport switch.

See [the CLI issue](https://github.com/aeharding/open-connect/issues/14) and [SSH follow-up](https://github.com/aeharding/open-connect/issues/15) for the implementation boundary. Do not infer an available
`--transport ssh` option or install a CMU network daemon from this plan.

## Host checks

```sh
hc exec --cwd "$PWD" "$PWD/.venv/bin/python" -B bench/test_profile.py -v
```

These use a local shell and synthetic D-Bus executable, the actual renderer,
receipt logic, CLI and Bundle boundary. They open no CMU port. They cover repeated
setup, pre-enabled state, delayed/ambiguous replies, identity changes, malformed
data, uncertain completion, receipt conflicts, deadlines and resource closure.
Live validation and limitations are in [RESULT.md](RESULT.md).
