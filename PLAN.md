# Open Connect — roadmap

Updated 2026-11-17. Primary developer owns delivery. This is the working roadmap,
refined as experiments change the evidence; dates are not promised.
[STEERING.md](STEERING.md) defines intent. GitHub issues track execution.

## North star

**Make Mazda Connect feel factory-original, work more reliably, and be easy to
maintain—with optional improvements people can install and undo.**

The intended feature scope spans Miatafy/ScreenTune-style startup, service,
logging/performance, input and connectivity improvements while retaining OEM
appearance. The first release remains small, but its architecture must cover
those different execution points rather than only the disclaimer's UI process.
See the [feature map and architecture](docs/extension-architecture.md#product-scope).
The bench and reverse engineering serve this product, not a separate platform.

The first production release keeps the touchscreen enabled and skips the startup
disclaimer. The owner plans to install it on their Mazda after both features
and uninstall pass together on matching bench firmware. The car reports 74.00.324.
Confirm its build and region against the release target.

Reliable native wireless CarPlay after a cold start is the next product milestone.
[#8](https://github.com/aeharding/open-connect/issues/8) tracks the lag and
[#9](https://github.com/aeharding/open-connect/issues/9) tracks measurements.

For optional online updates, explore an explicit switch between wireless CarPlay
and a phone/home hotspot, then a reliable return to CarPlay. Wired CarPlay plus
hotspot is a fallback option. OEM Wi-Fi controls and an Open Connect settings
entry remain research in [#54](https://github.com/aeharding/open-connect/issues/54).

## Support contract

Required today: **55.00.750B NA / cmu150_NA**, with exact original-file/API guards.
The release target for the owner's 2016 Mazda3 is **74.00.324 NA**. We have
the Mazda-hosted 74.00.324A NA package. For the 2014–2018 Mazda3, Mazda
specifies 74.00.324 or later and says the update cannot be rolled back. The
bulletin directs technicians to the Mazda Connect Update Instructions for the
procedure. The exact route from 55.00.750B NA still needs verification.
[Mazda bulletin 09-018/22](https://static.nhtsa.gov/odi/tsbs/2022/MC-10226834-0001.pdf)
[#2](https://github.com/aeharding/open-connect/issues/2) resolves exact package,
variant, intermediates, development access and power/media procedure before flashing.
Move the required baseline together and requalify features; do not maintain a
v55/v74 compatibility matrix or replay old offsets. Unknown versions are refused.
A future firmware switch supersedes current product support, not historical evidence.

## Milestones and exit criteria

| Milestone | User/developer outcome | Exit evidence | Work |
| --- | --- | --- | --- |
| **M1: Reproducible first feature** | Develop against a declared bench profile; demonstrate a clean OEM-feeling bypass | Small audio helper with explicit disable; measured bypass behavior, independent undo and original startup; independently distributable approach selected | [#1 bench profile](https://github.com/aeharding/open-connect/issues/1), [#3 handoff](https://github.com/aeharding/open-connect/issues/3) |
| **M2: Supported firmware and repeatable starts** | One modern baseline and comparable startup experiments | Verified upgrade/access/stock baseline; warm/cold capabilities distinguished; a useful repeated measurement batch retains failures | [#2 firmware](https://github.com/aeharding/open-connect/issues/2), [#5 starts](https://github.com/aeharding/open-connect/issues/5) |
| **M3: First production release** | Always-enabled touchscreen and startup disclaimer bypass in one release | Verify stock touch on the replacement bench, reproduce the motion restriction, test both features after restart, then uninstall and verify stock touch and warning behavior. Qualify update, reinstall, interrupted installation and replacement-USB maintenance under #7 before publishing on GitHub Releases for the owner’s real-car install. | [#60 touch](https://github.com/aeharding/open-connect/issues/60), [#6 bypass](https://github.com/aeharding/open-connect/issues/6), [#7 delivery](https://github.com/aeharding/open-connect/issues/7) |
| **M4: Measured everyday reliability** | More dependable CarPlay and responsive interaction | Comparable stock/modified connection success and timing; source-backed diagnosis; real-car confirmation of relevant claims; ship only improvements supported by results | [#8 CarPlay](https://github.com/aeharding/open-connect/issues/8), [#9 resources](https://github.com/aeharding/open-connect/issues/9) |

The delivery order below governs current work. Read-only firmware investigation
may fill hardware waits without displacing it. Live qualification uses the declared
baseline. A development prerelease is not a general end-user car release.

## Execution order now

Complete the maintained release implementation. The USB bootstrap and native
Settings controls have bench evidence; the existing host-driven transaction and
startup prototypes are inputs to this work, not the delivered installer.

1. **Standalone installer prerelease — [#7](https://github.com/aeharding/open-connect/issues/7).**
   CI produces one USB bundle for **55.00.750B NA**. Static loader, installer UI
   and CMU-local backend perform install, restart, Settings and uninstall without
   a host computer. Use Make/shell and standard native tools, with generated data
   manifests only. `oc` remains bench instrumentation. Verify reinstall,
   interruption recovery, conflicting edits, undo and compatible replacement-USB
   maintenance using one authoritative transaction record and preserved originals.
   Test the actual CI artifact on the bench and publish it as a development
   prerelease with the limited startup behavior stated plainly.
2. **Persistent startup qualification — immediately next, [#25](https://github.com/aeharding/open-connect/issues/25).**
   Qualify everyday repeated starts and finite failure recovery for the same
   installed features. Establish when a completed ignition shutdown can renew
   attempts; quick ACC resume, intentional reset and watchdog reset must not
   accidentally replenish them. Test interrupted durable updates, late faults,
   last-app and display-off behavior where they affect the delivered features.
   Reaching Home alone is not proof of recovery. Finish this before claiming a
   normal owner release; do not start another unrelated prototype track.
3. **Replacement touch qualification and the separate firmware move.**
   On the replacement CMU, confirm its identity and compare stock touch with the
   same display and cable. Complete [#60](https://github.com/aeharding/open-connect/issues/60)
   and the [#6](https://github.com/aeharding/open-connect/issues/6) feature checks.
   Resolve the supported upgrade route and access under
   [#2](https://github.com/aeharding/open-connect/issues/2), then port and requalify
   on the selected modern baseline before the owner's real-car installation.
   Physical dependencies gate only the checks that actually need them.
4. **Measured CarPlay reliability — [#8](https://github.com/aeharding/open-connect/issues/8)
   and [#9](https://github.com/aeharding/open-connect/issues/9).**
   Define cold-start connection/readiness measurements and investigate the actual
   wireless implementation before choosing a performance change. Keep the
   [v74 findings](docs/cmu/wireless-carplay.md) and
   [measurement plan](docs/carplay-testing.md) as inputs to that later work.

Reuse the [bench workflow](docs/cli.md#developer-feature-trial) for instrumentation
and observation. Existing one-shot composition, fault and power-cut results are
summarized in the [architecture evidence](docs/extension-architecture.md#evidence-so-far).
They establish useful mechanisms, not production persistence. Keep experiments
only when they resolve a named release blocker, then integrate the result.

One primary owns one implementation path, bench qualification and integration.
Use short-lived branches/PRs and the required independent final review. Close
issues only when their user-visible outcomes are achieved.

## Keep the first release small

Two features on one firmware, with **Install/update** and **Uninstall**. Installing again
performs a reinstall; interrupted transactions are handled internally. No separate
Repair or Change options UI. Add feature selection only when multiple useful
features exist.

Intended conflict behavior: save current state before restoring pre-install
originals, and allow that uninstall to be reversed. Later relevant edits mean
stop and preserve everything. Implement one authoritative durable transaction
record with verified original backups and one uninstall checkpoint. The exact
record format and interruption handling must be tested against the actual installer.
See [the working uninstall direction](docs/uninstall.md).

Necessary infrastructure: exact-base validation, verified original backups,
repeatable execution, one clear UI/backend command contract and independent undo.
Reuse existing bench tools for observations. Keep installer logic static and the
build conventional; defer frameworks and broad compatibility.

## What we measure

- **Startup experience:** warning presence, visible gap/fade, time to usable target
  screen and preservation of intended last-app/display-off behavior. Distinguish
  camera sampling limits from no-flash proof.
- **CarPlay startup:** time to usable projection, early control/audio responsiveness
  and time until stable. Correlate CPU, RAM, I/O and Wi-Fi/Bluetooth/service readiness;
  separate long-parked cold starts from software reboot and resume.
- **Reliability:** successful starts/connections divided by actual attempts, time
  to ready and failure categories under declared warm/cold/phone conditions.
  Report tails when sample size supports them, not success-only averages.
- **Responsiveness:** one relevant interaction timing and resource observations
  before/after a change. Resident RSS alone is not reclaimable savings or causality.
- **Maintenance:** observed lifecycle transitions, conflicts correctly refused,
  interruption outcomes, exact as-found undo and original boot. Separate installer recovery,
  UART rescue and unbootable-device recovery.
- **Reproducibility:** feature revision, exact firmware, enabled bench overrides,
  available hardware and useful source-backed notes accompany each result.

No universal numerical performance targets are invented before a comparable
baseline. Each experiment states its expected improvement and success criterion
before running. Findings can justify closing a proposed feature without shipping it.

## Current evidence and dependencies

Firmware55 native bypass/paired renderer handoff and independent restoration have
been demonstrated. The later Snap comparison showed a brief handoff. The
outgoing CMU subsequently booted its original JS and native library. See
[handoff findings](docs/reverse-engineering.md#disclaimer-and-intro-handoff) and
[current state](docs/bench-state.txt). This is not a release candidate.

The existing audio-manager API opened FM Now Playing and the source list without
a TAU. The CLI verified setup and teardown of the runtime profile. No permanent
startup hook is installed;
actual playback remains unverified.
See [TAU experiment](experiments/tau-bypass/README.md).

The DPS150 now provides tested full-output power control; voltage settings must
remain unchanged. The ACC relay now reproduces both [quick resume and fresh startup](docs/reverse-engineering.md#acc-must-be-a-real-transition) on the v55 bench. The Mac also authenticated over USB Ethernet on this CMU. Recheck access on the replacement. An audio readiness override must be off
for measurements where it would hide the behavior under investigation.

## Deliberately deferred

Broad firmware/region/hardware compatibility; themes or non-OEM feature catalogs;
a web configurator; arbitrary old-USB compatibility; general TAU emulation; app
removal without measurable benefit; a new installer/agent orchestration framework.
No impossible-to-brick claim. Real-car rollouts need demonstrated scope beyond the bench.

## Knowledge and release

AGPL-3.0-or-later original code; [third-party boundaries](THIRD_PARTY.md).
The CC BY-NC-SA comparison adaptations and full OEM captures stay outside the
distribution. Each substantive feature PR updates its firmware-scoped how/verify/
undo findings. Private evidence paths are not a public reproduction recipe.

GitHub [issues](https://github.com/aeharding/open-connect/issues) and
[milestones](https://github.com/aeharding/open-connect/milestones) are the work queue.
This roadmap holds intent and dependency order; changing device state stays in
the handoff. Update these after meaningful results, not every command.

Semantic CLI: https://github.com/aeharding/open-connect/issues/14. SSH/network transport: https://github.com/aeharding/open-connect/issues/15.
