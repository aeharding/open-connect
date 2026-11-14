# Open Connect — living steering agreement

Last updated: 2026-11-13, from the user's explicit direction.

Read this first when starting or resuming work. It records product intent and how
we work; it is not a run log or an approval checklist. New user direction takes
precedence. Update the relevant paragraph when direction changes, removing
contradictions rather than accumulating layers of instructions. Label proposals
as proposals; never silently turn an agent's suggestion into a user decision.
Keep overview pages short and match design detail to implementation maturity.
Agreeing on an outcome does not settle its implementation mechanics.

## North star

The project name is **Open Connect**. Use **Mazda Open Connect** as the README
title. The bench is part of the project, not its product identity.

**Make Mazda Connect feel factory-original, work more reliably, and be easy to
maintain—with optional improvements people can install and undo.**

Open Connect is an AGPL, contribution-friendly improvement layer for the original
Mazda experience. Success is a better everyday startup, connection or interaction,
with the normal controls and behavior retained. The number of mods, experiments,
tooling components or agent-hours is not a measure of product progress.

Start with one feature and two user-facing actions: **Install/update** and
**Uninstall**. Running Install again reinstalls it using verified originals;
interrupted-operation recovery is internal behavior, not a separate Repair option.
No Change options screen is needed until multiple worthwhile features exist.
For conflicting edits, Uninstall saves the current affected files/state before
restoring pre-install originals. A single Undo this uninstall checkpoint restores
that previous modified state. If relevant state changed after uninstall, undo
stops without writes or force/merge fallback. See docs/uninstall.md.
Maintenance uses a compatible replacement USB stick; the original stick is not
required. Arbitrary old-package compatibility is not promised.
Original-backup restoration is as-found restoration, not a factory reset.

The product scope is comparable to Miatafy/ScreenTune's non-customization
improvements: startup/disclaimer behavior, unused services, logging and performance,
OEM menu/input conveniences, and phone/audio reliability. Preserve Mazda's look
and feel; do not turn this into themes, replacement dashboards or a launcher.
The disclaimer is the first experiment, not the architecture's scope.

Unused Aha/Pandora/Stitcher, TV and other service choices, logging levels and
performance settings are first-class feature candidates. Their dependencies,
benefits and hardware applicability need evidence; reducing process counts or
idle memory alone is not proof of a useful improvement. Similar feature scope is
not a requirement to copy another product's implementation or defaults.

Every performance or optimization change needs comparable baseline and modified
timing trials. Define the timed operation and conditions before the change, run
repeated trials, and retain failures as well as successes. Report the spread and
any regressions; do not call a change faster without measured evidence.
Pair timings with relevant CPU, RAM and I/O measurements under the same workload
and startup phase. Name the memory metric; lower RSS alone is not proof of a
useful improvement. Keep the baseline, feature set and measurement method explicit.

The autonomous bench and published reverse-engineering knowledge enable the
product and help contributors. Build them when they unblock a concrete experiment
or remove repeated effort. A 24/7 autonomous bench is an aspiration, not a
prerequisite for the first usable release or an active background schedule.
The user supplies physical resources; the primary owns software execution.

Bench helpers are managed as one development profile: setup, status and teardown.
No per-helper manual activation, new CMU menu or graphical UI is needed. A thin
semantic CLI reuses working tools; Python on the host and POSIX sh on the CMU are
the initial implementation. Extend it only for concrete tasks. See docs/cli.md. Command-only ephemeral agents can test usability, while the primary
retains ownership of live state and the complete outcome.

## One required firmware baseline

User decision: support **one exact firmware baseline at a time**. Current required
baseline: **55.00.750B, North America (cmu150_NA)**, with exact source/API guards.
A generic v55 label is not permission to apply patches to other v55 builds.

Move the required baseline to the latest officially applicable North American
release after package, upgrade sequence and development access are established.
**74.00.324(A) is a candidate, not a verified latest version or upgrade instruction.**
Determine its exact variant; do not treat 324 and 324A as interchangeable by assumption.
The user wants modern firmware as the eventual requirement, not a growing
multi-firmware support matrix. Historical experiments remain evidence after the move.
Reject unsupported version/region/base before writes; do not auto-port offsets.
Additional regions, hardware generations and legacy release support are deferred.

## Working style: hackathon

**“Elaborate is failure.”** Prefer a working, understandable experiment over
elaborate preparation. Build the smallest complete path from a useful question
to a patch, an actual bench result and undo.

Reverse engineering and code analysis are core work. Understand how the CMU makes
decisions, manages resources and moves through its lifecycle so patches change
the right behavior. Deep investigation is worthwhile when it resolves a concrete
design question. Coordination churn, repeated audits and speculative tooling are
not substitutes for progress.

Pursue the best correct fix. Do not choose a cosmetic workaround merely because
it is easier or less invasive. The dedicated bench exists for experimentation,
including native changes; it is separate from the user's real car. Backups and
recovery enable experiments, rather than becoming an endless prerequisite project.
Bench success does not automatically establish end-user release safety.

Keep scope small enough to pivot. Infrastructure must unblock the current
experiment or remove demonstrated repetition. Get exact-base checks, preserved
originals, repeatable execution and independent undo right now. Reuse those pieces.
Defer generalized plugin/configuration systems, broad compatibility and speculative
workflows until a real second use requires them. Prefer a small replaceable helper
over committing the project to an architecture early.

## Ownership and execution

- One primary agent owns the complete outcome directly. No standing specialist
  team or delegation of the main work. Any explicitly requested helper is
  ephemeral, answers one specific question, and exits.
- Decide routine implementation details and continue authorized work without
  repeated permission gates. Surface a concrete new risk or missing dependency
  when it changes the experiment; do not invent hypothetical approval chains.
- Keep one bench operator and clean up owned resources. Know what is on disk,
  what is actually loaded, and what state the device is in.
- Reuse working tools. Add tooling only to solve a demonstrated obstacle or remove
  repeated work. Avoid a new framework for each experiment.
- Test concrete failure modes and real entry points. Passing isolated mocks is
  not proof that the integrated runner works. After relevant checks pass, move
  to the useful bench experiment.
- Preserve original bytes and failure evidence, provide independent undo, and
  verify the resulting state. Do not relabel partial or reconciled results as
  an uninterrupted automated pass.
- Answer the user promptly. A status question does not pause the project.
  Report outcome, blocker and next action in plain language; do not flood the
  conversation with duplicated handoffs or leave questions unanswered.

## Current feature direction

Choose the simplest correct disclaimer bypass that preserves OEM initialization,
cleanup, focus, last-app/audio/display-off behavior and the normal frontend lifecycle.
Use native changes when they are the right intervention; do not require them when
an existing OEM mechanism provides a simpler correct result.

The independent native bypass and paired renderer cleanup worked on firmware55,
including undo and restored-stock startup. The subsequent upstream JS comparison
and Snap experiment still showed a handoff. Their noncommercial code remains local;
the first AGPL release needs an independently distributable implementation.
A clean bypass is the outcome; visual masking or timer reduction alone is not it.
Do not indefinitely tune an unmeasured frame at the expense of a usable product.

[PLAN.md](PLAN.md) orders the work and defines milestone exits. Firmware upgrade
scoping is active now, alongside the next small bench helper. Native install/undo
must account for loaded-module lifetime: restoring disk bytes does not unload it.
Reuse the working hardlink-hold recovery instead of rebuilding tooling.

## Extension architecture direction

Design around one complete selected boot configuration covering service policy,
configuration and optional code. A native/JS loader is an adapter, not the whole
architecture. Global disable must account for earlier service/configuration
effects too; a late MMUI flag cannot undo them. Prefer boot-scoped changes over
persistent edits that need repair before stock startup can resume.

The revised [architecture proposal](docs/extension-architecture.md) recommends a
small pre-consumer selector, immutable composed configurations and per-feature
adapters. The early boundary has one-shot warm-boot and controlled native/JS fault evidence.
Power cuts after completed record flushes passed; interrupted writes and persistent
feature policy remain unqualified.
Keep requested disable, verified baseline startup, automatic failed-start detection
and full uninstall distinct. No hot-unload or universal crash-recovery promise.

User priority: prevent an endless watchdog boot loop first; avoid unnecessary
safe-mode fallback after battery loss or an unrelated Mazda fault second.
Recovery should preserve installed features and the user's selection, not
uninstall or blame a tweak from one reset. New configurations get stricter trial
handling than previously confirmed ones. Any automatic retry policy must have a
persistent finite limit; a startup-ready signal must not erase later-fault
protection. Retry counts and reset classification remain proposed until qualified.

The user-preferred layout remains tooling/ for host code, cmu/ for bootstrap,
adapters and features. Move complete components with their tests; avoid empty
scaffolding or another history folder. Current paths remain until that migration.

## Development home and license

The public repository is https://github.com/aeharding/open-connect.
Original project code uses AGPL-3.0-or-later; incompatible comparison adaptations
and proprietary OEM captures stay out of the public repository. See THIRD_PARTY.md.
Use issues for concrete work and pull requests for coherent changes. Every PR
requires independent adversarial review before merge, including small fixes and
documentation. Review the actual final diff for correctness, clarity and unnecessary
complexity; resolve blockers and record the reviewed commit. Keep the review
focused and proportional. The primary still owns implementation and bench results.
See CONTRIBUTING.md for development workflow and issue #1 for bench-profile work.

## Knowledge, progress and maintenance

Keep concise, source-backed findings alongside code: applicable firmware,
what we learned, relevant evidence and remaining uncertainty. Preserve independent
implementation provenance; keep full OEM binaries and private captures out of
published source.

Document after useful results and batch updates. GitHub issues and pull requests are the progress record. Do not maintain a
parallel dashboard or duplicate current-state indexes.

Keep changing device state and the next concrete task in
[the current handoff](docs/bench-state.txt), and operational instructions
in [AGENTS.md](AGENTS.md). Product intent belongs in this agreement; open implementation questions belong
in GitHub issues. Git preserves superseded plans.

Maintain this document when goals or working agreements change, not after every
command. Keep it short enough to read at the start of a session.

Current repository layout (before the planned tooling/cmu split): src/open_connect is host code; tests covers it; experiments
contains prototype mods; docs contains setup, usage and findings. Retired records belong in Git history. Keep one starting README and one current lab-state file.
