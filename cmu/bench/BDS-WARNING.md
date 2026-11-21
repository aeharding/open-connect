# Experimental Base BDS warning pilot

Question: does reducing BDS/Bluego logging improve startup resource pressure or
visible wireless projection enough to extend Base optimizations? This branch is
a one-variable experiment, not a qualified change to the published preset.

The control is the final dev.8 CI bundle from source `764d76e0`, with Base1,
Wireless1, Pandora1, Allow/Skip1 and product UART/SSH0. Retain the existing
stage-1 collector, receive-only UART/video, reference SD/Ethernet, iPhone8,4 on
iOS15.8.8 with USB on the Mac, existing pairing and Apple CarPlay Wi-Fi mode,
12.02V/2A supply and fixed camera exposure105/gain32. Keep the idle night-palette
dashboard without a route or playing audio. Primary measurements remain passive.

The experimental build uses the existing Base bit and boot RAM directory. It
changes exactly the two `logLevel="info"` XML fields to lowercase `warning` and
adds two BDS argument tokens: `-configFilePath` and
`/tmp/open-connect/feature/bds-warning.xml`. Both selected SM profiles retain
their original `-interface dbus` and applicable `-wcp`. The XML source stays
unchanged on the physical root. No new snapshot field, startup hook, persistent
trial selector or external RAM publication is introduced.

The pinned OEM XML SHA256 is
`33a2450c5c932f2ae3523f21e148effcce7db8341f163f7cb72ac277d96e301d`.
The warning data SHA256 is
`e2ebaed22f3a506d3c14f789a16b1efd780c79afe3f31774760589397e1fac0d`.
Refuse an existing `/tmp/BdsConfiguration.xml`, including a dangling symlink,
before SM starts: BDS ignores a failed copy and can otherwise use stale data.
After the pilot independently verify its copied destination hash and live
common logger level 3, not only the selected profile or source XML.

Build with standard tools:

```sh
make release OUT=runs/bds-warning-build
```

For the live pilot, retain the exact compiled members from CI44951500558 if
the local compiler differs. The C/assembly inputs are unchanged. Package the
authored static delta with the existing Make/shell build; record that provenance
as a local experimental bundle, rather than a new CI-built artifact.

Verify the bundle and pin its actual source/ZIP/public and installed manifest
hashes. Compare compiled members with the control before claiming a single
semantic variable. Use the maintained installer to update once, preserving
current eight-field settings, original baseline and undo record. An unmeasured
setup restart applies the package. Do not rewrite the frozen baseline manifests.

Run one 30-second ACC-off pilot with the frozen wireless capture runner, asserting
the new installed instance hash and Base1/Wireless1/Pandora1. After capture,
verify BDS argv, copied XML, live level, received BDS/BLUEGO messages and native
Bluetooth/wireless association/session plus visible dashboard. Retain failures,
actual clock origins, first-sample gap, all CPU/RAM/I/O counters and unknowns.
Compare with the published Base-on spread; a single pilot cannot qualify a
general speedup, physical audio/input or long-parked reliability. Repeat only
if the result answers a concrete unresolved question.

Independent undo is the pinned final dev.8 CI ZIP and existing native maintenance
flow, with the separately preserved baseline. Restore that control before the
next service experiment, complete a fresh ACC boot, and verify stock BDS argv,
copied XML SHA above, native level 5, retained settings and physical root read-only.
Do not claim restoration from disk bytes or deleted RAM data while BDS remains
loaded. The pre-existing bench SSH recovery and stage-1 independent restore
remain available and are separate from product access.

Keep OEM XML, generated copies, raw captures, phone identifiers and credentials
private. Only authored source, sanitized findings and reviewed derived data may
be published.
