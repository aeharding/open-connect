# Native logging prefilter mechanism

Exact74.00.324A NA. This is a playground experiment, not a supported optimization.
The first question is whether a Warn RAM setting supplied by the temporary
stage-1 hook is actually consumed by the normal newly launched native services.
Only after that proof should repeated timing/resource comparisons be interpreted.

The original /config/common/log/settings.txt remains Info and read-only. The
experiment hook accepts optional native-log-level data in the existing bench
profile: exactly Info or Warn plus LF. It creates only the native global RAM
settings file, before launching the unchanged finite collector. Existing RAM
settings or staging files cause refusal; OEM startup continues. Use identical
hook/collector bytes in both conditions and retain mode, source and actual boot.

Before changing the profile, save/verify its original hook and five-file manifest,
keep the original stage-1 inode and qualified independent controller, and verify
root is read-only again. After the experiment restore stage-1 with that controller,
restore the original profile files, restart, and verify original mappings and
actual native Info levels. Removing a file alone does not qualify cached-state
restoration. Keep every failed attempt and distinguish tooling from CMU failures.

logging-state.sh BOOT_UUID reads each matching exact-library mapping's private
logger state with PID/start checks. It writes no process memory. Field8 contains
three little-endian level bytes (Info5, Warn3); field10 is the initialized logger
PID. Report uninitialized contexts separately. Original library SHA256 is pinned
in the reader. Raw output stays private.

logging-probe.c reports the native getters only in a newly spawned, read-only SM
client. Compile it with ordinary Clang/LLD shared-library linking against the
private exact libjcicommon.so input; no OEM bytes are included in the probe. Use
LD_PRELOAD only on that new smctl --get process, never running services. The
bench has verified rootInfo5 -> RAMWarn3 -> RAMInfo5 -> rootInfo5 for this probe;
83 already-running native contexts stayed Info during the separate warm check.
Those mechanism checks are not performance evidence. Files, logs and compiled
OEM dependencies remain private.

The common collector and original comparison commands remain in
STARTUP-COMPARISON.md. First qualify the new startup mechanism and independent
undo, then freeze any comparison source and explicitly declare conditions before
running repeated trials. No SSH during startup; fetch completed traces after225s.
