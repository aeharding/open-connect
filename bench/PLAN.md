# Bench development profile — plan

Status: planning complete with one focused OEM-code review. 2026-11-13.
Owner: primary developer. User approved a separate persistent development profile,
normally enabled for bench work. No startup hook/profile is installed yet.

Tracking issue: https://github.com/aeharding/open-connect/issues/1

## Outcome
Keep reusable development helpers in bench/, separate from experiments and
end-user releases. First helper: silent Entertainment access without a TAU,
using the shipped audio-manager API already demonstrated on firmware55.
No speakers or sound output required. Do not emulate a whole tuner.

## Small implementation
1. Inspect actual Mazda startup/service lifecycle before choosing the attachment
   point. Prefer an existing suitable extension/config mechanism over editing a
   vendor startup script. Compare CMU startup activation with host-run activation;
   host-run activation is a fallback, not proof of autonomous persistence.
2. One persistent, root-owned Open Connect bench directory with a versioned small
   configuration, helpers and install/undo records. Choose the path after checking
   startup mount availability. No general plugin framework.
3. One optional startup invocation, separate from product modifications. It must
   not block Mazda boot. Wait for the real audio-manager service within a bounded
   deadline, resolve its current owner, query enableStatus, issue enable(true)
   only when needed, then verify the state. Exit with a useful result.
4. Do not continuously force readiness, fake TAU-connected messages or suppress
   watchdogs. Determine whether initial service availability is early enough:
   Mazda may deliberately disable audio later. Review the actual system/AM
   sequence; choose an observed stable event/state rather than arbitrary sleeps.
5. Explicit status/activate/runtime-disable/uninstall controls. Disabling the profile prevents
   future activation; distinguish that from undoing a current runtime effect.
   Record boot/bus identity, current unique service owner, original boolean and
   whether this helper changed it. Already-true state grants no undo ownership.
   An explicit runtime-disable is not complete prior-session restoration; matching
   identity cannot detect a later legitimate enable by another client.
   Serialize profile disable against pending activation and recheck configuration
   generation immediately before changing state.
6. Pin supported firmware/API and record profile version, selected options,
   boot identity and actual observed helper results in each test bundle.
   Unsupported firmware or service-owner changes must be reported; no blind replay.

## Stock and development tests
Routine feature work uses the declared bench profile. A genuine stock baseline
requires both development overrides and feature modifications disabled/restored,
then an original startup when loaded state matters. A test with profile disabled
but modified JS still loaded is not stock.
Startup/TAU-readiness/audio-resume measurements must explicitly choose and report
the profile state; a readiness override changes the system being measured.
Firmware upgrade starts from the appropriate restored state and must not
automatically reuse firmware55 behavior.

## First validation
Reuse existing UART, state verification, camera and file-recovery tools.
Host-check the actual entry point: unavailable service/timeout, owner replacement,
already enabled, delayed state update, malformed reply and disable semantics.
First validate the helper through the existing host entry point and normal
Home/Entertainment navigation. After the actual startup attachment and post-policy
readiness contract are established, install the optional hook, verify one normal
startup, disable/uninstall and verify startup without the override. No extra harness or repeated full-suite audits.
Re-entry after service restart/ACC remains explicitly unproved until exercised;
the explicit status command or existing runner detects later loss of effect;
an exited one-shot cannot monitor it. Do not add a daemon for this.

## Reviewer brief
One ephemeral reviewer, no hardware ownership or standing team. Inspect saved
OEM Lua bytecode listings/config and native callback/startup evidence, not merely
this proposal. Identify:
- a simpler existing Mazda configuration/test mechanism;
- who enables/disables audio and whether boot/service/ACC order defeats one-shot;
- state changes and cleanup beyond the enable boolean;
- the least invasive startup attachment point supported by actual saved evidence.
Give source path/line/function evidence and label missing sources as gaps.
Return actionable findings and a recommended small design; no speculative checklist,
implementation, source-acquisition campaign or extra review layers.

Evidence: experiments/tau-bypass/README.md and runs/open-connect-tau-bypass/.
The demonstrated API toggled false->true->false and opened FM NowPlaying and the
source list; no startup persistence, actual playback or complete settings rollback
was established.

## Review incorporated

The saved OEM test menu already uses the chosen API; no simpler persistent
ignore-TAU configuration was established. Audio Manager owns the boolean,
SYSTEM supplies startup policy, and MMUI consumes status/notifications.
In the captured boot, service readiness at 14.297s precedes SYSTEM's disconnected
TAU policy at 14.316s. Normal-state entry at 25.038s is a candidate boundary, not
a verified startup hook or callable readiness contract. The capture reads an
already-false value; it does not prove a later overwrite of our override.

The API replies before updating state. After one activation, poll strict status
within the shared deadline; reconcile ambiguous returns by reading, not repeated
writes. Owner replacement ends the attempt. Same-value calls produce no signals,
so repeatedly enabling cannot be used as a UI initialization repair.

Next implementation: the small host-invoked helper first; source-backed startup
attachment second. No permanent hook was installed during this planning task.
See REVIEW.md for the concise source-backed review.

## Baseline policy

The required current baseline is exactly 55.00.750B NA, not arbitrary v55.
When issue #2 moves the project baseline, requalify this helper and its startup
attachment on the selected firmware. Do not maintain an expanding compatibility
matrix. Host-invoked capability is the next deliverable; persistent startup remains
a separate step requiring a real hook and post-policy readiness evidence.
