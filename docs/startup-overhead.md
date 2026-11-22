# Startup verification overhead

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

The dev.9 candidate replaces ordinary pre-Service-Manager verification with a
native selection of sealed inputs and moves the Settings listener after
`stage_1`. It retains the durable budget barriers and the full verifier for
drift or recovery. Its stamps distinguish input checks, feature copying, record
write, file flush, rename, directory flush and selector exit. No dev.9 timing or
stock-parity result is claimed here; the measurements above remain PR #119's.

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

CPU uses the same contained uptime 20–170 s window as the reference. MemFree
minimum and ending values use the complete available trace. Keep UART receiver
times separate from mapped kernel/ACC times. One unit, earlier reference blocks,
day/night palette drift, the small sample and visible-versus-usable milestones
limit attribution. Retain failures; a failed attempt is not a reason to replace
it with a cleaner start.
