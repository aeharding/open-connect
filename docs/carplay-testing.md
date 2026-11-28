# Measure CarPlay startup and lag

Use **stock wired CarPlay** with a compatible hub and phone as the baseline
fixture for release compatibility checks and general
[timing and RAM baselines](performance.md) (tracked in
[#89](https://github.com/aeharding/open-connect/issues/89)).

The owner's car already uses a mod enabling Mazda's **native wireless CarPlay**.
Its long-parked startup can show a black screen and delayed or bunched inputs,
then settles into reliable operation. Developer options, Services/Startup
optimizations, ACC bench control and Open Connect's own native Wireless CarPlay
toggle are now implemented and bench-tested on v74; systematic wired-vs-wireless
startup/input-lag characterization and long-parked/real-car qualification remain
open in the [roadmap](https://github.com/aeharding/open-connect/blob/main/PLAN.md).

Wired projection is the baseline measurement fixture; its results do not establish
wireless reliability or reproduce Miatafy's wireless timings. Measure the actual
reported wireless symptom before choosing a wireless optimization. A faster Home
screen or lower idle RAM is not enough.

## Start with comparable runs

Use one phone/iOS version, firmware, feature revision, audio/navigation workload
and pairing state. Record power-off duration, bench overrides and Wi-Fi
conditions. Keep the TAU/audio override explicit; it cannot substitute for a
vehicle audio baseline.

Test these separately:

| Start | What it tells us |
| --- | --- |
| Normal software reboot | A repeatable warm baseline |
| Full supply off/on | Power-loss startup; not automatically equivalent to a parked car |
| Controlled ACC/resume | Vehicle-like lifecycle using bench ACC relay control |
| Real car after a long park | Whether the reported symptom is reproduced |

In the final wireless phase, compare stock **wired** CarPlay with one pinned
**wireless mod**. This
characterizes the symptom; it does not isolate the mod from the different
transport. A later narrower wireless implementation should be compared against
that same wireless baseline. Change one variable per experiment.

Start with five runs per condition, alternate comparable configurations where
practical, and keep failed connections. Five runs are an initial check, not a
reliable estimate of rare failures or tail latency.

## What to capture

| Measurement | Definition |
| --- | --- |
| Usable CarPlay | Startup reference to visible projection that answers a deliberate input |
| Black-screen intervals | Video-observed start/end, reported with frame uncertainty |
| Input latency | Visible touch/commander action to the resulting screen change |
| Bunched inputs | One deliberately spaced input sequence versus observed responses |
| Settling | Repeat the same sequence early, then at 30, 60 and 120 seconds after projection appears |
| Resources | CPU deltas, available RAM, process RSS where obtainable, and I/O during the same phases |
| Connection | Bluetooth/Wi-Fi/CarPlay readiness and reconnect events aligned with video |

Reuse existing startup video/log capture and resource sampling. The current
roughly 5 fps recordings can show a 1–2 second delay, but cannot resolve fine
input jitter. Keep logs at a fixed level and measure collection overhead before
adding heavier tracing.

Report every attempt, success rate, individual timings and median/range.
A correlation with CPU, I/O or Wi-Fi does not by itself identify the cause.

## Next decision

Reproduce the lag, identify which phase stalls, then choose one source-backed
change. Keep a cleaner enablement mechanism even if it offers no speedup, but
describe its benefit accurately.

See [wireless source findings](cmu/wireless-carplay.md),
[#8](https://github.com/aeharding/open-connect/issues/8) and
[#9](https://github.com/aeharding/open-connect/issues/9).
