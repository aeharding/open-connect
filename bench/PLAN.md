# Bench development profile

Updated 2026-11-13. One profile, one setup/status/teardown interface.
Issue: https://github.com/aeharding/open-connect/issues/1

## Delivered
`scripts/oc bench setup|status|teardown` manages the whole current profile.
Its first helper uses Mazda's existing audio-manager API for silent Entertainment
without a TAU. No per-helper public activation commands or graphical UI.
See [setup guide](README.md), [actual result](RESULT.md) and [CLI contract](../docs/cli.md).

Setup records original status, boot/bus/service owner and intent before changing
anything. Already-enabled audio grants no disable ownership. One mutation is
followed by bounded readback; repeated setup is a no-op. Teardown undoes only
setup-owned effects on the same instance. Unknown completion retains a pending
receipt, not a blind retry. All operations share the existing exclusive lock.

The private host receipt survives separate CLI runs; the CMU override is runtime-only.
Actual setup/repeat/teardown/status/setup passed, leaving the profile enabled.
No startup attachment, vendor-file edit, daemon or general plugin framework exists.
Profile state is emitted with results for test attribution. Product mods are separate.

## Remaining: persistent startup when useful
The user wants this profile normally available during development. Before adding
automatic startup, establish the actual Mazda attachment and post-policy readiness
contract. Mere service availability is too early. Use one nonblocking invocation;
do not repeatedly force enable or fake TAU connection state.
Validate a real startup and profile teardown without disturbing product mods.
This follow-up does not gate the next feature experiment.

The completed [OEM-code review](REVIEW.md) established that Audio Manager owns the
boolean, SYSTEM supplies missing-TAU startup policy and MMUI consumes notifications.
Replies precede updates; same-value calls do not send signals. The saved Normal-state
entry is a candidate boundary, not a verified hook. Do not repeat this review.

## Test interpretation and compatibility
Current supported baseline: exactly 55.00.750B NA. Requalify when the baseline moves.
A stock baseline requires bench overrides and product mods removed/disabled, with
original startup where loaded state matters. An audio-readiness override changes
startup/TAU/CarPlay measurements; explicitly declare or disable it.
Teardown does not restore every setting changed by ordinary navigation.
Cold ACC, service restarts and playback are separate unproved capabilities.
No multi-firmware framework or additional mod controls are needed now.
