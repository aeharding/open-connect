# Performance evidence

Timings and RAM measurements are release evidence. Publish comparable runs here
before describing an optimization as faster or lighter. CPU and I/O observations
help explain the result; they do not replace a user-visible timing measurement.

**No completed comparable v74 timing/RAM batch is published yet.** Existing
feature and installer trials do not establish a performance gain. The method
below is the qualification plan; external reference numbers are identified
separately from Open Connect results.

## Configurations to compare

| Configuration | Purpose |
| --- | --- |
| Stock services with declared instrumentation | Establish the baseline on this unit |
| Released Open Connect, unchanged service selections | Measure the initial features and installed runtime, including the qualified wired CarPlay fixture |
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
