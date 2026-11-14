# Open Connect — roadmap

Updated 2026-11-13. Primary developer owns delivery. This is the working roadmap,
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

## Support contract

Required today: **55.00.750B NA / cmu150_NA**, with exact original-file/API guards.
One supported firmware at a time. The planned successor is the latest officially
applicable NA release; **74.00.324(A) remains an unverified candidate**.
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
| **M3: Maintainable USB developer preview** | Install and maintain one optional feature without the original stick | Selected-firmware feature qualification; real install/update/reinstall/uninstall and replacement-USB test; scoped interruption evidence; reproducible public build/test instructions | [#6 qualification](https://github.com/aeharding/open-connect/issues/6), [#7 USB preview](https://github.com/aeharding/open-connect/issues/7), [#10 contributors](https://github.com/aeharding/open-connect/issues/10) |
| **M4: Measured everyday reliability** | More dependable CarPlay and responsive interaction | Comparable stock/modified connection success and timing; source-backed diagnosis; real-car confirmation of relevant claims; ship only improvements supported by results | [#8 CarPlay](https://github.com/aeharding/open-connect/issues/8), [#9 resources](https://github.com/aeharding/open-connect/issues/9) |

Milestones overlap where useful: firmware research starts now; USB host design
does not wait for the upgrade. Live qualification uses the finally selected baseline.
Hardware dependencies gate only experiments that actually need them.
A developer preview is not a general end-user car release.

## Execution order now

**Whole-startup architecture before another loader increment:** [#25](https://github.com/aeharding/open-connect/issues/25)
now covers service/configuration features as well as optional native/JS code.
The current MMUI loader is host-built only and cannot select earlier service
startup. Next: establish a practical boundary before affected consumers, then
prove baseline versus one composed trial. Validate one service change, one logging
setting and the existing paired bypass against the same global-disable contract.
See [the revised proposal](docs/extension-architecture.md#next-proof-and-implementation-order).
Persistent mode needs explicit health/failure semantics; no automatic-recovery
claim follows from installing a loader. No new general plugin framework is needed.

1. **#1, first increment delivered:** one `oc bench setup/status/teardown`
   manages the whole current runtime profile. Host and command-only agent checks,
   live setup/repeat/teardown/setup passed; the bench is intentionally enabled.
   [CLI operations](docs/cli.md) and [Audio Manager findings](docs/reverse-engineering.md#silent-entertainment-without-a-tau).
   Persistent startup still needs a verified hook/readiness boundary; it does not
   gate feature work. No per-helper public controls or force-enable daemon.
2. **#2, active research:** resolve the exact supported latest-NA package and upgrade
   route/access implications. Existing source leads are not a current-release proof.
   Produce a concrete recipe and named remaining physical inputs.
3. **#3, next feature experiment:** use saved menu/surface/lifecycle code to test one
   measurable handoff improvement. Keep normal continuation and cleanup. If another
   visual intervention has no demonstrated benefit, record that result and proceed
   with the best supported design; no endless transition tuning.
4. **#5/#7/#10, next:** repeatable startup batch, a small shared USB lifecycle and
   a fresh-checkout contribution path. Reuse working components.

One active implementation at a time. Independent source investigation may fill
hardware waits; it does not imply a standing subagent team. Review a substantive
plan once against real Mazda code, then review the actual diff and result.
Use short-lived branches/PRs and close issues only when their outcome is achieved.
A planning PR does not close implementation work.

## Keep the first release small

One feature, one firmware, **Install/update** and **Uninstall**. Installing again
performs a reinstall; interrupted transactions are handled internally. No separate
Repair or Change options UI. Add feature selection only when multiple useful
features exist.

Conflict uninstall saves the complete affected current state, then restores
pre-install originals. It retains one **Undo this uninstall** checkpoint. Undo
requires the relevant post-uninstall state to remain unchanged; later edits mean
stop, preserve everything and no force/merge fallback.
See [the scoped uninstall contract](docs/uninstall.md).

Necessary infrastructure now: exact-base validation, verified original backups,
repeatable execution and independent undo, plus the small audio helper that
unblocks real UI testing. Reuse existing tools. Require a concrete current consumer
or demonstrated repeated task before adding infrastructure. Keep components easy
to replace; defer frameworks and broad compatibility.

## What we measure

- **Startup experience:** warning presence, visible gap/fade, time to usable target
  screen and preservation of intended last-app/display-off behavior. Distinguish
  camera sampling limits from no-flash proof.
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
been demonstrated. The later local upstream-derived Snap JS comparison is installed
with stock native; it still shows a brief handoff. See
[handoff findings](docs/reverse-engineering.md#disclaimer-and-intro-handoff) and
[current state](docs/bench-state.txt). This is not a release candidate.

The existing audio-manager API opened FM Now Playing and the source list without
a TAU. The CLI then verified setup/teardown and left the runtime profile enabled for
development. No permanent startup hook is installed;
actual playback, ACC/resume behavior and vehicle equivalence are unproved.
See [TAU experiment](experiments/tau-bypass/README.md).

Ethernet/SSH and controlled ACC hardware were last reported in transit; readiness
must be checked when relevant. Continue local source analysis and UART work.
A software reboot is not a cold car start. An audio readiness override must be off
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
