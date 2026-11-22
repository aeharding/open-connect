# Experimental Android Auto leaf pilot

Question: does disabling the two Android Auto leaves reduce startup work/RAM
while retaining wireless CarPlay? This is a one-variable playground experiment.
It does not add Android Auto to the public Base preset. An eventual Android Auto
control belongs among individual Services toggles and defaults to OEM enabled.

Control is dev.8 CI source `764d76e0`, Base1/Wireless1/Pandora1, Allow/Skip1 and
product UART/SSH0. Retain the existing stage-1 collector, receive-only UART/video,
SD/Ethernet, paired iPhone8,4/iOS15.8.8 with USB on the Mac, Apple CarPlay Wi-Fi
mode, 12.02V/2A supply and fixed camera exposure105/gain32. Measure the idle night
dashboard without a route or playing audio. Keep primary timing passive.

For this pilot only, the existing Base bit sets `autorun="no"` on exactly
`aap_service` and `jciAAPA` in both RAM SM profiles. Keep all their other
attributes, native CarPlay, Aha/Wi-Fi/VR dependencies and BDS Info unchanged.
Refuse missing/duplicate leaf stanzas before publishing selected RAM state.
Base0 must remain byte-identical to control. No new setting/schema or trial hook.

Build with `make release OUT=runs/android-auto-leaf-build`. If the local native
compiler differs, retain the unchanged compiled members from CI44951500558 and
package the authored static delta with the existing Make/shell build. Record
actual source/ZIP/public/private hashes and local assembly provenance. Do not
label the result CI-qualified or combine it with BDS/Wi-Fi experiments.

Use maintained native maintenance to update once and retain settings, baseline
and independent CI undo. After the unmeasured setup restart verify the two
processes remain absent and both profiles have the intended policy. Run one
passive 30-second ACC-off pilot with frozen capture `ab8993a5` and analysis
`4da76e1`, pinning actual installed instance and Base1/Wireless1/Pandora1. Retain
all attempts and compare visible dashboard, native connection milestones,
matched CPU, minimum/ending MemFree and I/O with the published control spread.
Name the early collector gap and separate UART timestamps from calibrated ACC.
Check CarPlay reconnect, native Settings and software commander navigation after
capture, with audio routing and physical controls explicitly unqualified.

Independent undo uses the pinned CI bundle and normal maintenance, then fresh
ACC startup. Verify all control members, retained settings/baseline, both Android
Auto leaves restored and running, original Wi-Fi/BDS behavior, wireless reconnect
and physical root read-only. Android-phone projection/audio restoration requires
a later Android fixture; this is a development qualification limit, not a blocker
for this bounded bench experiment. Do not claim it tested.

Keep OEM profiles, raw captures and identifiers private. Only authored source and
reviewed sanitized evidence may be published. Repeat promising results only.
