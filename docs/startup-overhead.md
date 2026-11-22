# Startup verification overhead

The subsequent **dev.9 native-selector pilot** reached Home at **26.20–26.41 s**
and the wireless dashboard at **52.01–52.22 s** after ACC-on. Both were about
**2.22 seconds earlier than the preceding verification pilot**. This is one
working-candidate start, with installed Settings checked separately; it does not
establish repeated gains or stock parity. Its recorded selector span was 0.56 s.

One passive Wireless CarPlay pilot of [PR #119](https://github.com/aeharding/open-connect/pull/119)
showed about **2.8 seconds earlier Home and 2.4 seconds earlier visible projection**
than the four complete, non-restarting controls from the sealed wireless baseline.
This is a single-pilot result. It does not establish a repeated improvement,
usable early input/audio, long-parked reliability or startup parity with stock.

The change retains synchronous staging and removes repeated verification and a
fixed listener wait. The remaining selector work is measured below; the owner's
target of no measurable added startup delay remains unqualified.

## Results and denominators

| Observation | Sealed controls | Verification pilot |
| --- | --- | --- |
| Primary attempts | Five; one later watchdog restart | One; no observed restart |
| Complete resource traces | Four | One |
| First resource sample, kernel uptime | 15.12–15.36 s | 12.55 s |
| Home, ACC-relative bounds | Conditional median 31.24–31.45 s | 28.42–28.63 s |
| Visible dashboard, ACC-relative bounds | Conditional median 56.64–56.85 s | 54.23–54.44 s |
| CPU busy, matched uptime window | 32.18–35.20% | 33.01% |
| Minimum MemFree, complete trace | 204.93–206.96 MiB | 206.61 MiB |
| Ending MemFree, complete trace | 206.74–208.64 MiB | 208.41 MiB |

The timing medians condition on the four controls without an observed restart.
They do not replace the five-attempt [wireless baseline](wireless-comparison.md),
whose restart remains a failure. [Individual results](assets/performance/startup-overhead/pilot-runs.csv)
retain all five reference attempts, including its missing resource fields, and
the new pilot. Differences use unrounded interval midpoints. CPU and free RAM
remain within the control spread; there is no memory or CPU saving claim.
Timing endpoints are rounded outward to hundredths; resource values are rounded
to the nearest displayed unit. CSVs retain the unrounded values.

The one new primary attempt retained 170 samples from uptime 12.55 to 191.92 s,
with a complete clock bridge and postflight verification. Its setup restart and
two Ethernet-access recovery starts preceded collection and are excluded from
timings; those records remain separate. The pinned control was restored through
normal maintenance and verified after a fresh ACC start. Original preferences,
baseline, service policy and physical read-only root were retained.

## Where the remaining work goes

The candidate records bounded `/proc/uptime` stamps in RAM during selection.
They are diagnostics, not operation authority. This pilot's
[phase data](assets/performance/startup-overhead/pilot-phases.csv) show:

| Completed phase | Uptime | Since preceding stamp |
| --- | --- | --- |
| Hook entry | 6.49 s | — |
| Package verification | 7.08 s | 0.59 s |
| Target/dependency verification | 9.21 s | 2.13 s |
| RAM session ready | 9.60 s | 0.39 s |
| Durable budget commit | 9.85 s | 0.25 s |
| Feature copy | 9.88 s | 0.03 s |
| Selector exit | 10.13 s | 0.25 s |

The selector spans **3.64 seconds**, measured at hundredth-second resolution.
The first resource sample is a later proxy for Service Manager entry, rather
than the selector's duration. These quantities must not be interchanged.
Historical stock measurements used a different wired fixture; they cannot
establish stock parity for this wireless pilot.

## Native selector pilot — dev.9

The [PR #121](https://github.com/aeharding/open-connect/pull/121) candidate selects
sealed inputs natively, hashes selected bytes during RAM copying and stages
Settings after `stage_1`. It retains both durable budget barriers and the full
verifier for drift or recovery. The original table and phase data above remain
PR #119's observations.

| Observation | Working dev.9 pilot |
| --- | --- |
| Primary attempts at the final build | One; no observed restart |
| Samples and complete trace coverage | 172; uptime 11.44–190.82 s |
| Stage-1 hook stamp / first resource sample | 11.23 / 11.44 s |
| Home, ACC-relative bounds | 26.20–26.41 s |
| Visible dashboard, ACC-relative bounds | 52.01–52.22 s |
| CPU busy, matched uptime window | 31.42% |
| Minimum / ending MemFree, complete trace | 207.99 / 209.67 MiB |

Against the four non-restarting sealed controls' conditional medians, Home was
about 5.04 s earlier and the dashboard about 4.63 s earlier. The original fifth
control remains a watchdog-restart failure. CPU was below those controls' range;
free RAM was slightly higher. One new start cannot establish CPU or RAM savings.
[Individual native attempts](assets/performance/startup-overhead/native-pilot-runs.csv)
retain the unrounded bounds and resource values. Timing endpoints are rounded
outward; resource values use the nearest displayed unit. MemFree is the kernel's
free-page metric; coverage before the first sample remains unobserved.

The [native phase stamps](assets/performance/startup-overhead/native-pilot-phases.csv)
span **0.56 s**: 0.15 s checking inputs, 0.22 s copying, 0.03 s writing the
record and 0.16 s flushing it. Rename, directory flush and exit share the final
hundredth-second stamp; a displayed zero does not mean their barriers were omitted.
An earlier UI-failing build recorded 1.07 s with the same native binary; the
excluded transport-recovery boot recorded 1.08 s. Storage flush variation matters.
This measurable selection work and the unmatched historical stock fixture leave
the no-added-delay target unqualified.

[Per-device I/O deltas](assets/performance/startup-overhead/native-pilot-io.csv)
use the contained uptime 20–170 s window, as CPU does. Do not sum whole devices
with their partitions. These counters omit pre-stage-1 work and cannot establish
the change in verification's early flash traffic.

One earlier primary attempt at `06ae21f` reached projection but failed installed
UI qualification: Opera rejected a strict-mode block function declaration.
Its trace and visible timings remain separately listed; they do not qualify the
complete working candidate. The intermediate `152bc77` setup exposed completion
cancellation and status-timeout issues. Neither its setup nor a RAM-only UI
preview is a primary timing run. The final candidate's automatic update restart
and one ACC restart to recover Ethernet access are also excluded setup records.
The working pilot had one Linux banner, one syslog boot marker, a complete
seven-exchange clock bridge and successful postflight checks. The
[native UART events](assets/performance/startup-overhead/native-pilot-uart.csv)
include session-active at 50.412 s on their separate logged clock; that event
does not establish the camera milestone or usable input/audio.

Compatible dev.9 maintenance from the prepared SD payload then completed normal
UI Uninstall and its automatic restart. A fresh stock kernel matched all 20
pinned OEM hashes and modes, the saved access configuration and login inode,
and the original absence of the touchscreen key. Original native mappings and
frontend/SM paths were loaded, physical root was read-only, and the root helper,
product state, runtime and owned holds were absent. The independent bench
observer profile was preserved. This is as-found restoration; physical-input,
audio, broader interruption and matching-car qualification remain deferred.

## Reproduce the observation

Product source is [`3bfda748`](https://github.com/aeharding/open-connect/tree/3bfda748ccc7435247c1feade06d2daa3e515fb9),
with [CI 44976553156](https://github.com/aeharding/open-connect/actions/runs/44976553156).
Setup used a local Make/shell assembly with unchanged compiled members from the
control CI build. All 40 packaged file contents matched the final candidate CI
archive; the ZIP bytes themselves differed. Private per-install identifiers are
not portable artifact checksums.

Use the frozen [`ab8993a5` capture](https://github.com/aeharding/open-connect/tree/ab8993a5c1647d0c1a17a44faa425e1f367de81f)
and [`4da76e1` analysis](https://github.com/aeharding/open-connect/tree/4da76e1fea03647b8621a1dc66a41fef3489fb81).
The [wireless reproduction instructions](wireless-comparison.md#build-and-reproducible-sources)
describe the instrumentation and source checkouts. Keep exactly 74.00.324A NA,
Wireless1/Base1/Pandora1, Allow/Skip1 and UART/SSH0. This fixture used the paired
iPhone8,4 on iOS 15.8.8, USB on the Mac, Ethernet/reference SD, no playing audio
or route, camera exposure105/gain32 and 12.02 V/2 A.

After an excluded setup restart and confirmed idle dashboard, collect one passive
30-second ACC-off start with the candidate's actual installed instance pinned:

```sh
python -m open_connect.startup_reference --live --host my-cmu \
  --ssh-config /path/to/ssh-config --condition open-connect \
  --package INSTALLED_INSTANCE_MANIFEST_SHA --pandora 1 --base 1 --wireless 1 \
  --bundle runs/startup-overhead/trial-1
```

UART/camera must start before ACC. The frozen collector starts at stage_1 and
samples for 180 seconds; SSH retrieval starts at ACC+225 s. Send no input or SSH
commands during primary collection. Then obtain the seven-exchange clock bridge
for the actual kernel, review adjacent video frames, annotate complete Home and
dashboard appearance, and run the frozen analysis. The dashboard definition
allows the map to remain loading; it requires the right-side cards rendered.
Retrieve `/tmp/open-connect/startup-times` only after primary capture closes.

For the native pilot, use product source
[`7e408f0b`](https://github.com/aeharding/open-connect/tree/7e408f0b292b3c63c20775dc2337b8d42f0fadce)
and [CI 44993181116](https://github.com/aeharding/open-connect/actions/runs/44993181116).
The tested **0.3.0-dev.9** ZIP SHA-256 is
`9ee59efe0f6ff79de36d60fd756f8d3a938208ff3054ca512f2ab1372812dcca`;
its public manifest is `1097ffaf30895807ecfccd732ca495162ed8f6d437f3809a3812d38b4ce21ef5`.
All 41 packaged files were checked, including 38 listed payload members. The
same frozen capture/analysis sources, command, configuration, workload and
milestone definitions apply. Use your actual installed instance in `--package`,
clear the installation notice and verify idle projection before collection.
The recorded video pairs were 57.453/57.654 s for Home and 83.263/83.464 s for
the dashboard; the kernel-clock interval was 29.38 ms wide. These frame times
describe this recording, not values to reuse in another observation.

CPU uses the same contained uptime 20–170 s window as the reference. MemFree
minimum and ending values use the complete available trace. Keep UART receiver
times separate from mapped kernel/ACC times. One unit, earlier reference blocks,
day/night palette drift, the small sample and visible-versus-usable milestones
limit attribution. Retain failures; a failed attempt is not a reason to replace
it with a cleaner start.
