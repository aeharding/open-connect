# Open Connect CLI — initial surface

Status: first bench-profile CLI implemented and live-verified. No SSH or other
semantic commands implemented yet.
The user asked for semantic commands that a fresh agent can use from a command
alone. Keep this a thin interface over working tools, not a new automation framework.

## First commands

| Command | Meaning | Device effect |
| --- | --- | --- |
| `oc bench setup` | Apply the complete current bench profile | Current helper enables silent Entertainment if needed |
| `oc bench status` | Observe profile and actual service state | Read-only |
| `oc bench teardown` | Undo setup-owned bench effects | Disable the owned override; preserve pre-enabled state |

No per-mod public activation commands, graphical interface or CMU menu.
The current profile contains one helper; adding another means these same operations
handle the combined profile and report partial failure honestly.
These are development tools, separate from product install/update/uninstall.

Entry point: `.venv/bin/python scripts/oc`. Until a command is actually implemented,
it must not appear as an available command. Next potential additions, only when
needed: device status, existing UI navigation/capture and observed restart.
Use actual OEM operations and established recovery, not guessed shell recipes.

## Execution contract

- Help and omitted `--live` are offline: no port, device bytes or state writes.
- Live use requires an owned operation, a fresh evidence bundle and the existing
  exclusive adapter lock. `--owner` defaults to the Herdr terminal identity when available, otherwise a local
  process label; callers do not need to invent one.
- `--solicit-prompt` asserts a known idle shell. Do not infer that state from a
  failed command or retry an uncertain command. No automatic login/bootloader input.
- Current firmware requirement: exact 55.00.750B NA. Identity is checked before
  operation; boot, bus and current service owner bind the bench receipt.
- Setup is idempotent. Record intent before mutation; verify status after the API
  reply. Never automatically repeat a mutation after an uncertain outcome.
- Teardown means bench effects only, not product uninstall or whole-device reset.
  Never disable audio that was already enabled before this setup or belongs to a
  replacement service/boot. Report expired ownership and actual observed state.
- All operations have finite deadlines, release the port and save failure evidence.
  Profile ownership is serialized with the same lock; no daemon or startup hook yet.
- Live JSON returns outcome, error, bundle and observed bench profile. Exit 0 means
  the operation was verified; 1 means failed/refused; 2 means uncertain UART outcome.
  Dry-run JSON explicitly says dry_run_not_executed, executed=false and state_written=false. A verified status can report an inactive,
  expired or pending profile; exit 0 is not shorthand for “profile active.”
- No credentials, raw PIDs or remembered D-Bus unique names in user commands.
  Raw evidence remains private; public results contain sanitized findings.

## Implementation choices

Use Python standard library for command parsing, JSON, state receipts and result
handling; reuse existing pySerial/Session/AdapterLock/Bundle for UART. No new package
or CLI framework. Bash is convenient as a caller but not as the host JSON/state
engine. Target commands use the observed BusyBox POSIX sh and installed dbus-send.
No Bash runtime is required on the CMU.

Preserve the semantic operation/result contract when SSH arrives; add that
transport only when actual SSH is available. UART remains the startup/recovery
channel. Do not build a speculative transport/plugin abstraction now.

## Cold-agent validation

Use ephemeral agents with a command-only brief, no project conversation or standing
specialist roles. First exercise offline help/dry-run, then one serialized read-only
live status command after focused host checks. The primary owns live setup/teardown
and resource state. Collect actual command/result, mistakes, time and unnecessary
steps; fix demonstrated ambiguity rather than adding a manual or another framework.
Agent success must be separate from actual device success. One agent's report
cannot override the underlying command result/evidence.

## SSH and networking direction

Keep the same operations and structured results when adding SSH. Use the host's
OpenSSH client and existing SSH agent/config; avoid a new SSH Python dependency.
Verify the host key and pair the configured endpoint to this bench, then check
fresh device/firmware identity. An IP address alone is not identity.

UART and SSH must share one lock for this configured CMU. SSH is the intended
normal command/transfer path; UART remains useful through boot and connection loss.
A dropped SSH connection after mutation is unknown, never a reason to resend over
UART. Reconnect/readback must establish what happened before any further change.
Check actual remote transfer capabilities; do not assume an SFTP subsystem exists.

Networking is not implemented in this initial CLI. Do not add a transport framework,
install a daemon or expose another API on the CMU. Add a small OpenSSH-backed executor
when the hardware/SSH endpoint is available and test the same semantic operations.

Guide: [bench setup](../bench/README.md). Tracking: https://github.com/aeharding/open-connect/issues/14; SSH: https://github.com/aeharding/open-connect/issues/15.
