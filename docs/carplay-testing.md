# Measure CarPlay startup and lag

**Measure the user's problem before tuning services:** a black screen at cold
startup, followed by delayed or bunched touch/commander inputs. A faster Home
screen or lower idle RAM is not enough.

This is the next experiment plan. Live CarPlay measurements await the compatible
hub, phone and a qualified modern-firmware bench. Existing v55 results do not
establish CarPlay performance.

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
| Controlled ACC/resume | Vehicle-like lifecycle once ACC control is available |
| Real car after a long park | Whether the reported symptom is reproduced |

First compare stock **wired** CarPlay with one pinned **wireless mod**. This
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
