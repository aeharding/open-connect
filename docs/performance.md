# Performance evidence

Timings and RAM measurements are release evidence. Publish comparable runs here
before describing an optimization as faster or lighter. CPU and I/O observations
help explain the result; they do not replace a user-visible timing measurement.

## Published dev.20 cold ACC-off comparison 2026-11-25

**Primary COHORT-9: Stock versus published v0.3.0-dev.20, Base=0 and Base=1.**
There were **11 attempts and nine clean resource traces: n=3 per condition**.
Both failures remain in the attempt ledger below. **[#9](https://github.com/aeharding/open-connect/issues/9)
remains open**: these data do not establish zero boot/CPU/RAM overhead, real-car
qualification or long-parked CarPlay reliability.

Published build: source `63de79f896aec5ba16a41df3cb97b2cce5d6afd2`,
[CI 45591321686](https://github.com/aeharding/open-connect/actions/runs/45591321686),
ZIP SHA-256 `dd165194295807d6386f7222eacf0217e9e53f01bb517600897c79c40fa41d63`.
Normal UI Install and all 47 shipped / 48 installed manifest members were verified.
The later PR #149 candidate and its screenshots are **separate qualification**;
it received no new performance cohort. Do not relabel these results as that build.

### Fixture, settings and measurement

One physical **74.00.324A NA/cmu150_NA** unit, the **same working Navigation SD**
in its OEM read/write mount, with zero agent writes or staging on that card.
Each start followed a real **30 s ACC-off interval with B+ retained**. No B+ cut
or supply-setting change occurred. Bluetooth stayed on, with the same as-found
phone/peripherals and **no foreground projection**. The installation USB was
deauthorized for the measurements, with its bytes untouched.

Stock used its original disclaimer **Show** and stock services. Both installed
blocks used Touchscreen Allow, disclaimer **Skip**, Wireless off, Show CarPlay on
connection Factory, Android Auto/Pandora/SiriusXM on and the published build's
separate DVD choice off; developer UART/SSH choices stayed unchanged.
**Base=0/1 means Startup optimizations off/on**, the only difference between
installed blocks. Stock-to-installed Home gains include disclaimer bypass and
service choices; this is not isolated Open Connect overhead or read-ahead benefit.

Acquisition order was Stock → excluded Install/setup → Base=0 → excluded
Base-enable Apply changes restart → Base=1. The clean medians exclude the two
failed resource captures, while all attempts stay visible below. One unit,
blocked acquisition order/drift, phone/Navigation activity and the small sample
limit causal attribution.

Home is the first stable actual HomeScreen with visible portions of all five
icons at final geometry, excluding the introductory carousel. Camera frame PTS
and host-monotonic mapping give ACC-command bounds; relay/sensor latency is
uncalibrated. Home is **not first accepted physical touch/Commander input or
usable CarPlay**. Native SM timestamps use a separate clock.

Boot CPU is cumulative `/proc/stat` from kernel start to the nearest ~60 s
sample, excluding idle+iowait, with USER_HZ=100. Percentages use **total two-core
capacity = 100%**; busy CPU-seconds sum both cores. Settled CPU uses samples
wholly within uptime **60–170 s**. RAM minima/end use observed samples wholly
within **20–170 s**, ending near 169 s. Collection starts around 18–20 s;
**earlier RAM is unobserved**. Post-window PSS snapshots have different ages and
are not shared-window peak or per-library heap measurements.

### Primary timing and CPU medians (n=3 clean traces per condition)

| Condition | Attempts / clean traces | Home ACC bounds, s (median endpoints) | Native stage1 start, s | Native MMUI STARTED, s | Boot CPU % | Busy CPU-s | Settled CPU % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stock, Show | 3 / 3 | 39.794–39.995 | 8.314 | 22.994 | 68.32 | 81.78 | 12.62 |
| Base=0, Skip | 4 / 3 | 35.479–35.680 | 8.554 | 23.158 | 69.05 | 82.35 | 13.13 |
| Base=1, Skip | 4 / 3 | 32.082–32.283 | 8.434 | 20.410 | 63.53 | 75.76 | 12.19 |

Home midpoint medians are **39.9 / 35.6 / 32.2 s**. The Stock Show → Base=0
Skip difference is about **4.3 s** and includes skipping the disclaimer as well
as other installed configuration differences. It does not measure the disclaimer
wait in isolation; there is no isolated Show/Skip toggle trial here. Base=1 is about **3.4 s earlier
than Base=0 Skip**, or **7.7 s earlier than Stock Show**. Versus Stock, Base=0
boot CPU is **+0.72 percentage points** and Base=1 **−4.79 points**, with Base=1
busy CPU **−6.02 CPU-s**. A faster Home does not establish zero runtime overhead.

Differences below are calculated before rounding the displayed medians.

### Named RAM medians

**Linux 3.0.35 has no kernel `MemAvailable` field.** The **available-RAM proxy** is
`MemFree + Buffers + Cached + SReclaimable − Shmem`; it is not guaranteed
allocatable RAM. Raw `MemFree` is a different counter. `AnonPages` counts
resident anonymous pages; **Committed_AS** is the separate commit-accounting
counter. A cache-to-free shift is not equivalent to an AnonPages reduction. Raw used = MemTotal − MemFree and includes cache. MemTotal is
746.160 MiB; MiB = 1,024 KiB (decimal MB = MiB × 1.048576).

| Condition | Min MemFree MiB | End MemFree MiB | End raw used MiB | End available proxy MiB | Cached MiB | Shmem MiB | AnonPages MiB | Slab MiB | Own allocated tmpfs KiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stock | 122.43 | 131.04 | 615.12 | 377.74 | 237.39 | 4.10 | 269.82 | 21.38 | 0 |
| Base=0 | 121.86 | 130.89 | 615.27 | 378.36 | 239.78 | 5.93 | 267.38 | 21.50 | 396 |
| Base=1 | 208.20 | 209.72 | 536.44 | 398.92 | 179.55 | 4.18 | 252.06 | 20.77 | 500 |

Against Stock, Base=0 has **+0.61 MiB available proxy**, **−2.45 MiB AnonPages**
and **396 KiB own allocated tmpfs**. Base=1 has **+21.18 MiB available proxy**
and **−17.77 MiB AnonPages**; its much larger raw MemFree gain partly replaces
cache. Own tmpfs counts allocated 512-byte blocks once per unique device/inode,
excluding persistent symlink targets. It is not all process memory and must not
be blindly added to PSS/private pages.

| Condition | Post-window Opera PSS MiB | MMUI PSS MiB | VUI PSS MiB |
| --- | ---: | ---: | ---: |
| Stock | 50.00 | 14.51 | 2.64 |
| Base=0 | 48.01 | 14.44 | 2.64 |
| Base=1 | 48.05 | 13.09 | 2.54 |

One separate Base=0 helper snapshot at uptime 251.50 s measured listener
85 KiB PSS / 72 KiB private and ignition 160 KiB PSS / 136 KiB private.
It is **n=1 supplemental**, not an n=3 helper-RAM result.

### All 11 primary attempts, including both failures

| Condition / trial | Home ACC bounds, s | Resource disposition |
| --- | ---: | --- |
| Stock / 1 | 39.794–39.995 | Clean primary; runner GPIO receipt rejected, independently adjudicated from hardware ACC OFF and fresh kernel. |
| Stock / 2 | 40.990–41.191 | Clean primary. |
| Stock / 3 | 37.119–37.321 | Clean primary. |
| Base=0 / 1 | 35.476–35.677 | Clean primary. |
| Base=0 / 2 | 35.679–35.880 | Clean primary. |
| Base=0 / 3 | 35.289–35.490 | OEM **sshd:36000 bind collision**, “Address already in use”; camera/UART retained, resource/clock/boot-marker receipts unavailable. |
| Base=0 / 4 | 35.479–35.680 | Recovery ACC cycle supplies third clean resource trace. |
| Base=1 / 1 | 31.651–31.852 | Clean primary. |
| Base=1 / 2 | 79.070–79.271 | **Uncommanded restart at ACC+42.657 s** (second kernel epoch); delayed Home retained. |
| Base=1 / 3 | 33.287–33.488 | Clean primary. |
| Base=1 / 4 | 32.082–32.283 | Recovery ACC cycle supplies third clean resource trace. |

**Neither failure is erased by a replacement trace.** Base=0 trial 3 is a
transport/retrieval failure caused by the OEM SSH bind collision; no missing
resource values or boot identity are invented. Base=1 trial 2 lost first-boot
RAM; its later-retrieved 173-sample trace belongs to the **recovery kernel** and
is excluded from primary CPU/RAM medians. The restart cause is **unestablished**;
native `_isStack` errors alone do not establish causation. Recovery budget was
1 on that boot and 2 on clean ACC starts.

A separate Base=1 admission check confused a persistent restart notice with a
pending restart; it opened no UART/camera/relay and is **not a cold attempt**.
All six clean installed starts have fresh matching boot-identity symlinks.
Trial 4 compares the last confirmed Base=0 trial 2 identity; trial 3 has none.

### Receipts and reproduction boundary

The authoritative private packet is `runs/acc-bench-20261125/COHORT-9.md`, with
`cohort.csv`, `resource-analysis.json`, raw camera/UART/resource captures,
per-trial analysis, clock bounds and boot-identity receipts. Host-only analysis
uses `analyze.py`, reviewed `score-camera.py` / `score-disclaimer.py` frame
choices and `report-cohort.py`. Original capture manifests are not rewritten to
claim newer code. This page publishes sanitized derived values, not raw captures,
OEM files, credentials or device identifiers.

## Stage 2B isolated toggle sweep (n=1)

**TOGGLES-IMPACT is separate from COHORT-9:** five additional real 30 s ACC-off
starts on the **same published dev.20 build and Nav SD fixture**, with B+
retained, a 180 s passive observer and the same Bluetooth-on phone fixture.
Each profile was applied through the normal guarded installed Set/restart
backend before its measured boot; setup restarts are excluded. No package
patch, direct snapshot edit or verification bypass was used.

Touch Allow, disclaimer Skip, Show CarPlay on connection Factory and legacy DVD
off were held fixed. The first four cases keep **Base=0**, changing only the
named choice. **Max-off** uses Base=1 with Android Auto/Pandora/SiriusXM/Wireless
off; it is a combined feature-removing preset, not an isolated toggle or a
feature-neutral improvement. Controls are the **earlier n=3 primary medians**;
these observations do not increase primary cohort counts.

### Single-trial Home and CPU observations

| Configuration | Home ACC bounds s | Home Δ vs Stock Show s | Home Δ vs matching Base Skip s | Boot CPU % | Boot CPU Δ vs Stock pp | Busy CPU-s | Settled CPU % | Settled CPU Δ vs Stock pp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SiriusXM off | 34.278–34.480 | −5.515 | −1.201 | 67.70 | −0.62 | 81.32 | 12.31 | −0.31 |
| Android Auto off | 35.096–35.297 | −4.698 | −0.383 | 69.24 | +0.92 | 83.00 | 14.62 | +2.00 |
| Pandora off | 35.899–36.100 | −3.895 | +0.420 | 70.75 | +2.43 | 83.90 | 12.55 | −0.07 |
| Wireless on, iPhone connected | 34.682–34.883 | −5.112 | −0.797 | 70.48 | +2.16 | 84.77 | 16.03 | +3.41 |
| Max-off (Base=1) | 28.865–29.066 | −10.929 | −3.217 | 64.03 | −4.30 | 75.80 | 10.05 | −2.57 |

“Matching Base” means Base=0 for the isolated toggles and Base=1 for Max-off.
CPU definitions/windows match the primary table; **pp means percentage points**,
not relative percent. Stock Show versus installed Skip confounds total Home
gains. With n=1 against earlier blocked controls, small timing/CPU differences
can be run variation; Pandora's +0.420 s does not establish a repeatable slowdown
or benefit. Home is not CarPlay readiness or input latency.

### Single-trial named RAM observations

| Configuration | Min MemFree MiB | Min MemFree Δ vs Stock MiB | Min MemFree Δ vs matching Base MiB | End available proxy MiB | Proxy Δ vs Stock MiB | End raw used MiB | Own tmpfs KiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SiriusXM off | 135.02 | +12.59 | +13.16 | 385.13 | +7.39 | 602.52 | 392 |
| Android Auto off | 129.66 | +7.23 | +7.80 | 382.33 | +4.59 | 607.89 | 396 |
| Pandora off | 124.32 | +1.89 | +2.46 | 379.60 | +1.86 | 613.30 | 396 |
| Wireless on | 122.75 | +0.32 | +0.89 | 377.85 | +0.11 | 616.28 | 432 |
| Max-off (Base=1) | 234.86 | +112.43 | +26.66 | 414.46 | +36.71 | 511.29 | 500 |

Available proxy uses the formula above, **not kernel MemAvailable, raw MemFree
or AnonPages**. Against Base=0, ending available-proxy differences are
**+6.77 / +3.98 / +1.24 / −0.50 MiB** for SiriusXM off / Android Auto off /
Pandora off / Wireless on. Thus the compact **+7.4 / +4.6 / +1.9 MiB** labels
are **versus Stock**, not Base=0. Do not add isolated differences to predict a
combined configuration. Max-off's **29.0 s Home / +36.7 MiB proxy / −4.3 pp boot
CPU versus Stock** is a single observed combined result that removes features.

Wireless setup confirmed AP on, one associated station and a post-ACC connected
CarPlay session. Autoshow stayed off and Home remained visible: session state
is separate from visible projection. No new pairing or phone move was requested.
Wi-Fi off and clean defaults were restored before PR #149 qualification.

The separate private `TOGGLES-IMPACT.md`, `toggles-impact.csv`, `toggles-pss.csv`
and `toggles-mapped-modules.csv` retain exact profiles, named global RAM fields,
post-window PSS ages and mapped-library limits. Analysis used
`analyze-toggles.py`, reviewed `score-camera.py` choices and `report-toggles.py`.
Mapped library pages exclude plugin-owned heaps; no n=3 per-library baseline is
invented. A post-Uninstall Stock snapshot is explicitly nonprimary and not
another ACC trial. PR #149 restoration is recorded separately in `PR149-QUAL.md`.
These are limited observations, not stock parity, release qualification or
long-parked reliability; **#9 remains open**.

## Earlier measurements

The [dev.17 maintenance UI checks](maintenance-loading.md) pair one normal boot
per version and Base setting. Home was unchanged at camera resolution and own
allocated tmpfs changed 0 B. Opera memory increased in the single snapshots,
and first use of the animated style added 588 KiB PSS after a static dialog.
The CPU outlier, supplemental repeat, uncommanded restart and explicit RAM
disposition requirement remain visible; this is not a zero-overhead claim.

The [dev.15/dev.16 sparse-loading comparison](sparse-native-loading.md) retains
three primary Home observations per version, all connection misses and a
supplemental control. Home was about 0.385 s earlier; own allocated tmpfs rose
104 KiB. The controls never qualified as visible Maps, so comparative CarPlay
speed, CPU parity and net-system memory savings remain unestablished.

The [dev.13/dev.14 Base startup comparison](base-startup-tuning.md) retains three
starts per version. Median visible Maps moved **47.09 → 44.67 s**, Home
**24.97 → 24.70 s**, and shared-window flash reads **86.85 → 52.17 MiB**.
CPU's median was 0.67 percentage points lower with overlapping ranges. Own tmpfs
rose **12 KiB**; the roughly 57 MiB higher MemFree mostly replaced file cache.
The slow control, all attempts, memory categories and restoration checks are explicit.

The [dev.12/dev.13 wireless-startup comparison](wireless-startup-speed.md) retains
three starts per version with Base and Wireless enabled. Median visible Maps was
about **2.21 seconds earlier**, while Home was unresolved at camera resolution.
CPU busy rose **1.16 percentage points**; measured own-RAM components were
identical and MemFree differences were within the run spread. The owner accepted
this specific tradeoff. It does not close the no-overhead or long-parked targets.

The [matched stock/dev.12 comparison](stock-startup-comparison.md) retains
four stock attempts (three complete traces) and three complete active starts,
without projection. Native SM `stage_1` started **0.085 seconds later**, within
its declared margin, but Home's **midpoint estimate was about 0.40 seconds later**;
its +0.196..+0.598 s frame bounds straddle the +0.20 s margin, so Home parity was
not established. CPU was 0.83 percentage points higher and minimum MemFree
3.11 MiB lower with Base off. Runtime tmpfs, private process pages and raw memory
categories are accounted separately. A Base-on warm restart confirmed overlap
and Warn logging; it is not matched Base-on performance qualification. The
no-overhead/no-unapproved-RAM target remains open.

The [first stock/Open Connect comparison](startup-comparison.md) found **slower
startup with the development candidate**: the median wired CarPlay dashboard
milestone moved from about 48.3 to 56.7 seconds after ACC-on. CPU busy increased;
minimum free RAM was similar. Five accepted runs per condition, the excluded
attempts, numeric samples and reproduction commands are published with the result.
This is a regression to investigate before service optimizations, with no claim
of reproducing Miatafy's wireless timings.

The [first verification optimization](startup-verification.md) recovers about
1.2 seconds to Home and 2.2 seconds to the dashboard in a five-run dev.5 block.
CPU and RAM remain similar, and stock is still faster. The original controls
are reused explicitly; their collection identities are unchanged.

The [Pandora comparison](pandora-comparison.md) adds five starts enabled and five
disabled on the same dev.6 build. Minimum MemFree was about 3.2 MiB higher with
Pandora off; the wired dashboard timing difference was below camera resolution.
All individual results and reproduction commands are published. The first
Services control remains optional and defaults to running.

The [native logging comparison](logging-comparison.md) tests a narrow Warn filter
with original features/services: five Info starts followed by five Warn starts.
The visible wired dashboard median was about 3.2 seconds earlier; minimum MemFree
in the matched window was about 8.7 MiB higher, with only about 1.4 MiB higher ending
free RAM. The source, spread and limits are published. This is evidence for
qualifying a Base optimizations candidate, not an installed-bundle claim.

The [installed Base comparison](base-comparison.md) then measures five Base-on
starts followed by five Base-off starts of the same dev.7 CI bundle, with Pandora
and the initial features held fixed. Dashboard median was about 3.8 seconds earlier;
minimum MemFree was about 9.9 MiB higher and ending free RAM about 2.58 MiB higher.
All ten primary starts completed without failures or exclusions. The optional
preset defaults off. Its 14.55–14.94-second early resource gap, block order and
single-bench limits are explicit; these results do not qualify wireless or a vehicle.

The [wireless startup baseline](wireless-comparison.md) retains five Base-off
and five Base-on attempts on one dev.8 bundle. First-dashboard medians were about
58.1 and 55.2 seconds after ACC-on, but one Base-on attempt later watchdog-restarted
and another took about 68 seconds. Only three off/four on resource traces were
retrieved. Minimum MemFree differed by 6.4 MiB, ending free RAM by only 0.3 MiB.
All attempts, the restart, Ethernet failures and the day/night-map drift remain
explicit. These blocks do not establish isolated Base benefit, usable early
input/audio, long-parked reliability or Miatafy reproduction.

The [startup verification pilot](startup-overhead.md) then measured one revised
dev.8 start against that sealed reference. Home and visible wireless projection
appeared about 2.8 and 2.4 seconds earlier than the four non-restarting controls'
conditional medians; CPU and MemFree remained within their spread. Individual
attempts, remaining 3.64-second selector work and single-pilot limits are explicit.
This does not meet or qualify the target of no added delay versus stock.

The [native-selector follow-up](startup-overhead.md#native-selector-pilot-dev9)
records one working dev.9 start: Home at 26.20–26.41 s and the wireless dashboard
at 52.01–52.22 s, both about 2.22 seconds earlier than the verification pilot.
CPU was 31.42%; minimum/ending MemFree were 207.99/209.67 MiB. The earlier
UI-failing attempt and setup failures remain explicit. The 0.56-second selector
span is a measured reduction; stock parity and repeated gains remain unqualified.

The [Services pilots](service-pilots.md) retain the subsequent single-boot
voice-deferral and four-leaf experiments. Delayed voice startup showed no
projection/RAM gain and is parked. Suppressing DAB, TV and two Stitcher services
left roughly 6 MiB more free RAM in one matched Maps pair. That is candidate
selection evidence; it does not establish repeated benefit or a CPU gain.

The [complete dev.10 Services preset](services-comparison.md) compares two Base-off
and two Base-on dashboard starts with Android Auto, Pandora and wireless held on.
Median minimum MemFree was 14.21 MiB higher with Base; ending free RAM was 8.31 MiB
higher. The dashboard median was about 3.2 seconds earlier. All four matched
attempts completed; two preliminary native-foreground misses are retained
separately. The small blocked sample and night/day rendering change limit
attribution. This is a bundle comparison, not stock parity.

The [dev.14/dev.15 Services expansion](services-expansion.md) retains three
matched starts per version plus one explicitly excluded wrong-foreground attempt.
Own tmpfs fell 448→444 KiB, while CPU was nearly unchanged. Median Maps was
1.407 s later and Home's midpoint 0.200 s later, with overlapping run ranges.
The owner accepted the candidate-specific timing tradeoff; #9 remains open.
The page includes the full native timeline, named RAM metrics, applied-source
checks and an unresolved reboot during a test-only post-purge page reload.

## Configurations to compare

| Configuration | Purpose |
| --- | --- |
| Stock services with declared instrumentation | Establish the baseline on this unit |
| Pinned Open Connect candidate or release, unchanged service selections | Measure the initial features and installed runtime; identify development candidates explicitly |
| Base optimizations off/on, same individual service selections | Measure the installed bundle as one setting |
| One service choice changed, other settings fixed | Attribute the effect and detect dependencies |

The current development candidate groups the logging, service and startup policies
described in [Startup optimizations](startup-optimizations.md) behind one optional **Base optimizations**
choice, initially off. Identify the exact bundle revision in every result and
test the whole bundle; individual savings cannot simply be added together.
Future preset contents and individual service choices need comparable measurements,
undo and regression checks. See [Services work #86](https://github.com/aeharding/open-connect/issues/86).

## Timings

Define each milestone and its observation before running the batch. Record both
external power/ACC timing and kernel-relative time; `/proc/uptime` does not
include the time before the kernel starts. Keep Home visible, first accepted
input, audio readiness and network readiness separate. Input-device registration
alone does not establish working touch. State the input source and any camera
frame uncertainty.

Record exact firmware/region, board, peripherals, workload, enabled features,
service choices, logging, profiler revision and sampling overhead. Separate warm
reboot, sustained ACC shutdown, quick resume and full supply loss; an overnight
car start needs its own observation. Alternate comparable configurations when
practical, repeat runs and retain failures. Start with a small declared batch,
then increase it when variation or the intended claim requires more evidence.

Publish individual results, attempt/success counts and median/range with the
conditions. Do not equate a process appearing with the feature becoming usable.
Use the [CarPlay plan](carplay-testing.md) for the early wired baseline and the
final native-wireless phase. Qualify stock wired projection before collecting
its timing/RAM batch; wireless implementation changes remain later work.

## RAM, CPU and I/O

RAM is a required part of every performance comparison, during startup and a
matched steady workload. Use the same sampling method and both fixed elapsed
windows and the relevant readiness milestone. Report the observed range and
startup pressure alongside steady-state values, rather than choosing one good
idle snapshot.

| Measurement | Record |
| --- | --- |
| System RAM | Available `/proc/meminfo` fields: total/free memory, buffers, cache, shared memory and slab; no kernel `MemAvailable` on Linux 3.0.35; label the available-RAM proxy explicitly |
| Process RAM | Named process RSS and, where supported, bounded `smaps`/PSS snapshots; process identity and sample phase |
| CPU | Deltas over declared intervals, with profiler overhead checked |
| I/O | Comparable read/write activity, logging volume and any relevant faults/reclaim counters the kernel provides |

Preserve original units and state any KiB/MiB conversion. `MemFree` is not
`MemAvailable`. RSS includes shared resident pages; PSS apportions shared pages.
Do not sum process RSS and call it physical RAM saved, or turn missing counters
into zero. Collect only fields supported by the actual kernel and bound expensive
mapping snapshots. The [Linux proc documentation](https://docs.kernel.org/filesystems/proc.html)
describes these counters; its newer fields are not a promise about the CMU kernel.

## Startup observer coverage — November 21, 2026

Startup collection must begin locally, independently of network readiness. In
the initial stock ACC trial, the SSH-started collector first sampled at kernel
uptime **41.09 seconds**, after native UI was already visible. Camera and
receive-only UART covered the restart from before ACC-on, but RAM, CPU and I/O
before that first sample were unobserved. Those missing values are not zero;
that trace cannot establish whole-startup memory pressure.

The replacement experiment backgrounds the same system-counter collector from
the supported firmware's empty `stage_1.sh`. It records a finite 180-second
trace in RAM, with a one-second minimum pause, and retrieves the finished result
over SSH after startup. There is no SSH readiness polling during that window.
The temporary hook preserves the exact original and an independent restore
entry. It does not change product startup files or service selections.

| Coverage trial | First sample uptime, seconds | Last sample end, seconds | Samples | RAM values |
| --- | --- | --- | --- | --- |
| SSH-started, source 9b2971f | 41.09 | 160.72 | 117 | [CSV](assets/performance/startup-post-ssh-coverage.csv) |
| Local stage-1 hook, source 34d7c29 | 11.16 | 190.32 | 171 | [CSV](assets/performance/startup-local-coverage.csv) |

These are separate single-run coverage checks after 30.015- and 30.017-second
ACC-off intervals, respectively. Both used stock services, owner-key SSH, a wired
phone, Ethernet and FAT SD, with camera/UART observation and no GUI input or supply
commands. Phone model/iOS was not captured. One earlier local-observer attempt
refused before any ACC transmission because an unrelated continuity camera
appeared; selecting the identified bench camera resolved that tooling failure.
After the local trial, the independent restore returned the exact original
script and inode. A further ACC restart verified original startup with no RAM
observer output and physical root read-only.

The local trace covers substantially more startup allocation: kernel `MemFree`
was 639,244 kB in its first sample and 207,052 kB in its last, with a minimum of
198,728 kB in the observed window. This is not `MemAvailable` or a RAM-saving
claim. The first **11.16 seconds still lack resource samples**, so even this
trace does not establish a whole-boot peak. Its completed RAM output was
832,230 bytes, contributing to the memory being observed; do not subtract it
from the counters as though all instrumentation overhead were known.

Use the pinned [playground experiment and setup/undo instructions](https://github.com/aeharding/open-connect/blob/34d7c293a9cc7476884f88c2061164a3d7b5becd/cmu/bench/STARTUP-REFERENCE.md).
Its host command retains the observer sources, raw retrieval, verified boot,
sample bounds and RAM CSV. This is measurement-method qualification, not a
stock-versus-Open-Connect comparison. Describe the condition as stock features
with bench instrumentation; the temporary root hook and RAM output are part of
the measurement setup. The earlier SSH overhead pilot below does not establish
the overhead of this boot-local configuration.

The collector in both checks is
[`metrics.sh` at 34d7c29](https://github.com/aeharding/open-connect/blob/34d7c293a9cc7476884f88c2061164a3d7b5becd/cmu/bench/metrics.sh),
SHA256 `04ce5017e08a4e62823135eb6a560cefbc51289edda256ff5f2b1946b3d5a109`.
The linked experiment uses the maintained `metrics.memory_csv` to produce these
per-sample exports; public copies normalize line endings to LF. Neither check establishes CarPlay usability, input latency
or a product performance difference. Camera clock-domain qualification does not
eliminate sensor/display latency or the roughly five-frame-per-second spacing.

## Collector overhead pilot — November 20, 2026

The first collector disturbed the workload substantially. On one exact
74.00.324A NA bench with Open Connect uninstalled, it raised aggregate CPU busy
by 10.49–12.77 percentage points across three control/sampling pairs. A single
reader reduced that cost; making detailed process discovery opt-in reduced it
further. The default now collects system RAM, CPU, VM, disk and network counters.
Use explicit process names when those additional observations justify their cost.

| Collector/configuration | Paired CPU-busy change, median (range), percentage points | Per-pair results | Experiment revision |
| --- | --- | --- | --- |
| Original per-file programs, with process reads | +11.21 (+10.49 to +12.77) | [CSV](assets/performance/collector-original.csv) | [b5ec28f](https://github.com/aeharding/open-connect/tree/b5ec28fd498511dde776f785218430dced8a6ec8) |
| One reader, direct process discovery | +4.31 (+1.51 to +4.95) | [CSV](assets/performance/collector-processes.csv) | [c9721ac](https://github.com/aeharding/open-connect/tree/c9721ac0e8b9c7086c29e4fcaa244cf0f628a088) |
| Default system counters, no process discovery | +0.81 (+0.50 to +2.38) | [CSV](assets/performance/collector-system.csv) | [ae30a0f](https://github.com/aeharding/open-connect/tree/ae30a0f1126d5f3a5c27d2a6b0592ae6236ed1b3) |

Each row has three pairs in alternating order: control, sampling, sampling,
control, control, sampling. Each reference window lasted about 45 seconds. In
sampling windows the collector ran for 40 seconds, starting two seconds inside
the reference window, with a one-second minimum pause. All sample bounds were
inside their reference window. CPU busy excludes idle and iowait and is computed
from aggregate tick deltas over the **whole reference window**, including the
extra SSH session and collector startup/exit. The CSV retains actual durations.

The same CMU, phone and idle wired CarPlay dashboard were retained throughout;
OEM service selections and logging were unchanged, no audio workload was used,
and the owner-key SSH bench access remained installed. No camera/UART observer
or GUI input ran during these windows. Phone model/iOS version was not captured,
which limits comparisons with other phone workloads. Background load varied;
three pairs do not precisely isolate the collector's CPU use or establish that
startup latency is unaffected. These are observer-qualification results on one
bench, with no Open Connect speedup, RAM saving or wireless-timing claim.

The measured collector sources are respectively
[5b282c5](https://github.com/aeharding/open-connect/blob/5b282c59db30668ad3f5992ed5d7d9d3e3fe8f24/cmu/bench/metrics.sh),
[ded334e](https://github.com/aeharding/open-connect/blob/ded334e9bda5843b85f3f35a607793d98b65c209/cmu/bench/metrics.sh)
and [8c51e53](https://github.com/aeharding/open-connect/blob/8c51e534021b6c11d163b6c5656fc48bf5917b60/cmu/bench/metrics.sh).
Source hashes in the private run manifests matched those revisions; later changes
do not relabel these measurements. All 18 reference windows and nine sampling
commands completed. Earlier short smoke tests were separate qualification steps.

To reproduce, use the linked experiment revision and its
`cmu/bench/METRICS-OVERHEAD.md` command with a declared fixed workload and an
existing trusted SSH alias. The checked-in
[analysis/export command](https://github.com/aeharding/open-connect/blob/412d512/cmu/bench/METRICS-OVERHEAD.md)
recomputes paired results from the original saved CPU endpoints, checks boot,
order and completeness, and exports the CSV without opening a device. Private
raw records remain under `runs/performance-v74-20261120/`; the public CSVs contain
only reviewed derived CPU values and durations.

## Miatafy comparison

[Miatafy’s ScreenTune benchmark page](https://miatafy.com/screentune/boot-benchmarks/),
checked November 20, 2026, reports these timings on one v74.00.324A unit:

| Milestone | Stock typical | ScreenTune typical | Stock range | ScreenTune range |
| --- | --- | --- | --- | --- |
| Touch readiness | ~48 s | ~32 s | 47.0–57.4 s | 31.5–33.7 s |
| Wi-Fi AP readiness | ~55 s | ~39 s | 53.4–67.3 s | 38.8–42.6 s |
| CarPlay session | ~71 s | ~55 s | 64.9–84.8 s | 51.3–71.4 s |

The page describes seven stock and six modified captures, an internal profiler
using `/proc/uptime`, and a combined wireless/startup and service configuration.
Its later unused-RAM examples span revisions and service choices, not a matched
per-option comparison. It does not report menu frame times.

These are external reported results, not Open Connect measurements. Match event
definitions, timing origin, hardware and configuration before claiming
reproduction. Exact profiler triggers and package configuration remain to be
established. Report reproduced, different or not comparable outcomes with the
evidence. A direct product comparison also needs an available compatible package
and identified revision. Wireless CarPlay reproduction waits for that phase;
screen and general-resource comparisons can proceed earlier.

## Publishing a result

Another contributor must be able to repeat each published batch. Include the
exact collector and analysis commits, commands, input configuration, startup
condition and off interval, milestone definitions, sampling cadence, workload,
phone/firmware details, and per-attempt values. Preserve failures and unsupported
counters. Explain clock alignment, video uncertainty and any coverage before the
collector starts. A summary chart alone is insufficient.

The [resource sampling command](cli.md#record-ram-cpu-and-io-over-ssh) retains
read-only traces and a RAM CSV using the checked-in collector. It is one part of
the method; it does not measure startup milestones or early RAM before SSH is
available. Measure collection overhead before using it in a comparison.

Useful temporary service-disable or tuning experiments may live on clearly
labeled playground branches. Cite immutable commits and retain setup, verification
and undo commands, so later readers can reproduce the experiment after the branch
changes. Experimental branches are not supported releases. Publish only original
compatible code and reviewed derived data; OEM files, keys and raw captures stay
private. Extending `oc` is appropriate when it makes these steps repeatable, not a
requirement to create a separate benchmarking framework.

For each completed batch, add its question, configurations and conditions,
collector/build revisions, per-run timing and RAM values, summary spread,
failures, regressions and conclusion. Link concise sanitized evidence to the
implementation PR and retain private raw records for reconciliation. Include
negative and inconclusive results. Keep OEM files, credentials and raw captures
out of Git; follow [documentation guidance](documentation.md).

Keep this page as the evidence entry point. Put detailed per-batch records beside
the relevant findings when needed, rather than maintaining another progress
dashboard. [#9](https://github.com/aeharding/open-connect/issues/9) owns the
baseline comparison; the [roadmap](https://github.com/aeharding/open-connect/blob/main/PLAN.md)
sets delivery order.
