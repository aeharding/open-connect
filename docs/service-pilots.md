# Services pilots on dev.9

These single-boot experiments select candidates for the next Services change.
They do not establish repeated speed gains, usable early input/audio, or vehicle
reliability. The voice-startup delay is parked. The four-service suppression is
a RAM candidate for Base; the complete installed preset still needs repeated
measurement.

## Voice startup: keep the original delay

The candidate changed only `stage_vr` from a five-second sleep to 35 seconds,
with Base optimizations, Wireless CarPlay and Pandora enabled in both boots.
It preserved the dependency graph and scheduling priorities.

| Observation | Control | VR delay |
| --- | ---: | ---: |
| Home after ACC | 26.27–26.49 s | 26.60–26.81 s |
| CarPlay dashboard after ACC | 48.66–48.87 s | 50.20–50.41 s |
| CPU busy, 20–170 kernel seconds | 30.98% | 32.94% |
| Minimum MemFree, complete trace | 213,340 kB | 213,168 kB |
| Ending MemFree | 215,160 kB | 214,540 kB |
| Resource-partition reads, matched window | 31.15 MiB | 31.15 MiB |

The mechanism worked: CPU busy in the contained 40–60-second window fell from
47.95% to 30.59%, and that window's 23.63 MiB resource read burst moved later.
The contained 80–110-second window then recorded 21.65 MiB. These windows have
sampling gaps at their boundaries and must not be added as a partition of the
whole trace. Total matched-window reads remained unchanged.

Mazda's Service Manager reported native phone, contacts, messaging and voice
started about 31–32 seconds later. All four were running at the final check.
These are service lifecycle states, not tested call, sync, speech or audio
readiness. Dashboard midpoint was 1.54 seconds later in this pair. There was no
demonstrated projection or RAM gain to justify the tradeoff; no repeated batch
was run.

## Four discontinued or non-NA services

The separate candidate suppressed `jciDAB`, `jcitv`, `blm_ira_stitcher` and
`irsstitcher_server`. The VR delay remained five seconds. Neither board profile
has a surviving startup dependent on these leaves: only Stitcher's suppressed
BLM depends on its suppressed server. No offboard settings XML was changed;
this does not claim removal of every Stitcher component.

All four remained stopped in the primary run. Its foreground was the full Maps
app, whereas the earlier control displayed the dashboard. Restoring the reviewed
control bundle provided a matched Maps control and independent undo: all four
services were running again, with the original five-second VR gate.

| Observation, Maps foreground | Leaves suppressed | Restored control |
| --- | ---: | ---: |
| CPU busy, 20–170 kernel seconds | 31.62% | 41.28% |
| Minimum MemFree, complete trace | 220,180 kB | 214,316 kB |
| Ending MemFree | 222,016 kB | 215,848 kB |
| Resource-partition reads, matched window | 31.15 MiB | 31.15 MiB |

Minimum free RAM was 5.73 MiB higher and ending free RAM 6.02 MiB higher with the
leaves suppressed. This is one reversed-order pair, a reason to qualify the
candidate rather than a repeated benefit claim. The higher control CPU remains
unexplained: one short post-capture sample did not identify a busy suppressed
service. Do not attribute that CPU difference to the four leaves. Neither Maps
run observed the dashboard milestone, so no dashboard startup gain is claimed.

## Evidence and reproduction

The [run table](assets/performance/services-pilots/runs.csv),
[phase counters](assets/performance/services-pilots/phases.csv) and
[SM lifecycle events](assets/performance/services-pilots/sm-events.csv) retain
individual results. SM timestamps have not been mapped to the ACC or host clock;
PIDs, boot IDs, phone identifiers and raw captures are excluded.
Acquisition order was dashboard control → VR delay → Maps leaves → Maps control.
All four primary attempts completed with one kernel boot and full resource
retrieval; the Maps foreground change remains part of the evidence.

Firmware was exactly 74.00.324A NA. The phone stayed on the Mac with wireless
pairing retained; Ethernet and a non-navigation FAT SD stayed on the CMU.
ACC was off for 30 seconds with B+ retained at the unchanged supply setting.
These were full restarts, not overnight parked-car trials. The camera, early
local observer and other service selections were held fixed. Primary boots
received no injected input or SSH polling.

Capture used [ab8993a5](https://github.com/aeharding/open-connect/tree/ab8993a5c1647d0c1a17a44faa425e1f367de81f),
with retrieval after ACC+225 seconds, followed by the same-boot clock mapping.
Analysis used [4da76e1f](https://github.com/aeharding/open-connect/tree/4da76e1fea03647b8621a1dc66a41fef3489fb81).
Use the [wireless reproduction commands](wireless-comparison.md#build-and-reproducible-sources)
with Base/Wireless/Pandora all set to 1 and the actual installed package identity.
The control was the reviewed [7e408f0b](https://github.com/aeharding/open-connect/tree/7e408f0b292b3c63c20775dc2337b8d42f0fadce)
CI bundle. The [VR source](https://github.com/aeharding/open-connect/tree/1767e363a900d0891596be86315816000da1df70)
and [leaf source](https://github.com/aeharding/open-connect/tree/9f8a1f7145b0ec309dadd921a917c9ff0ec895b4)
are independent playground revisions based on merged dev.9.

Each experimental assembly reused the exact control's compiled outputs through
the existing shell packager. Only `firmware.sh` and its public manifest changed.
All four normal/WCP × Base compositions were privately compared with the pinned
originals; unrelated attributes and children were preserved. Each source passed
246 host tests, with 18 platform/private-fixture skips.

For phase calculations, select samples wholly inside each requested interval and
subtract the first and last CPU and disk counters, retaining the actual endpoints.
CPU busy excludes idle and I/O-wait ticks. Disk sectors are 512 bytes; do not add
parent devices to their partitions. Minimum and ending MemFree are kernel free
pages in kB, not application PSS or a sum of process RSS. Read `/tmp/smevents.txt`
and terminal `smctl --get --type info --name SERVICE` only after primary capture,
guarding the same boot before and after. Preserve every lifecycle occurrence.

Setup included one separately recorded Ethernet recovery after the fresh control
install. Mazda Wi-Fi mode was Off after stock restoration; selecting its normal
Apple CarPlay mode reused the existing pairing. An injected Done press during
leaf setup did not acknowledge the installation notice; unchanged state was
reconciled and the existing backend dismissed it without another key event.
The foreground change is retained explicitly, not attributed to the service edit.
