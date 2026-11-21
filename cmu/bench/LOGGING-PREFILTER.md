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

## Declared comparison

Collect five new Info starts, then five Warn starts, with original features and
all original service selections. Keep the phone/Ethernet/reference SD, supply,
camera manual exposure, idle map/Not Playing, no route/audio and30-second ACC-off
fixed. The map changed to its daytime palette during the unmeasured mechanism
check; use fresh daytime controls. Phone/iOS are unrecorded and block order/drift
remain limitations. Do not pool the mechanism boot or earlier stock controls.

Before each block save the exact four-letter choice plus LF in the existing
profile's native-log-level, then complete an unmeasured setup restart. The
assertion flag below never changes it. Pre/postflight require that desired file,
the exact native RAM bytes, the unchanged physical Info original, and initialized
MMUI logger levels agree. Undeclared RAM policy makes default capture refuse.
The seven early initialized contexts that remained Info in the mechanism check
are outside this late-service filter; do not describe it as turning all logs off.

```sh
python -m open_connect.startup_batch --live --host my-cmu \
  --condition stock --log-level Info --bundle runs/logging/logging-info
python -m open_connect.startup_batch --live --host my-cmu \
  --condition stock --log-level Warn --bundle runs/logging/logging-warn
python -m open_connect.startup_export runs/logging runs/logging-public --logging
python -m open_connect.startup_plot runs/logging-public/startup-samples.csv \
  runs/logging-public/startup-resources.svg
```

Annotate the same completed Home entrance and first fully visible dashboard
between adjacent decoded frames. Report individual results and annotation
sensitivity, CPU and separate-device I/O over actual endpoints in uptime20–170s,
and named RAM counters. Early resource pressure remains unobserved. The observed
policy affects normal CommonLog levels; peak-load defaults and early contexts
remain distinct. No result is presumed from the lower setting or process count.
The exporter independently reparses raw traces/clocks and the effective policy
records. Old default and Services export modes retain their original labels.
