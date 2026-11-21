# Performance evidence

Timings and RAM measurements are release evidence. Publish comparable runs here
before describing an optimization as faster or lighter. CPU and I/O observations
help explain the result; they do not replace a user-visible timing measurement.

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

## Configurations to compare

| Configuration | Purpose |
| --- | --- |
| Stock services with declared instrumentation | Establish the baseline on this unit |
| Pinned Open Connect candidate or release, unchanged service selections | Measure the initial features and installed runtime; identify development candidates explicitly |
| Base optimizations off/on, same individual service selections | Measure the proposed bundle as one setting |
| One service choice changed, other settings fixed | Attribute the effect and detect dependencies |

The proposed **Base optimizations** setting groups qualified internal changes,
such as reduced logging, behind one on/off choice. Its contents and default are
not settled. Identify the exact bundle revision in every result and test the
whole bundle; individual savings cannot simply be added together. Keep optional
service selections explicit. Both the bundle and individual choices need undo
and regression checks. See [Services work #86](https://github.com/aeharding/open-connect/issues/86).

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
| System RAM | Available `/proc/meminfo` fields: total/free memory, buffers, cache, shared memory and slab; `MemAvailable` if this kernel provides it |
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
