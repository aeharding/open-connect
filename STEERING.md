# Open Connect — living steering agreement

Last updated: 2026-11-23. User direction and implementation choices are
identified separately.

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

Ship always-enabled touchscreen input and the startup disclaimer bypass together
in the first production release. The owner plans the first real-car installation
after bench validation on matching firmware. The agreed order is first v74
release, a small developer menu, performance baselines, a dedicated Services menu
with measured changes, then cold-start CarPlay reliability last. The owner has
deferred first-car validation and additional manual bench checks for now. Continue
Developer options development without waiting for those checks; retain the
remaining qualification limits and do not claim a qualified release.
Keep the two user-facing actions **Install/update** and **Uninstall**. Running Install again reinstalls it using verified originals;
interrupted-operation recovery is internal behavior, not a separate Repair option.
Keep the USB install prompt short. The update prompt shows the installed and
target versions, including same-version reinstalls. During installation and its automatic restart,
tell users not to remove the USB drive or turn off the car. Show completion after
restart, say the USB drive can now be removed, and offer Done and Open settings.
Use Mazda’s own Settings list and a separate radio-choice page for each feature
preference. The developer controls described below use their agreed UI.
Uninstall restores the pre-install startup and touchscreen behavior, then removes
Open Connect's installed files, backups and transaction state. There is no Undo
uninstall option; installing it again uses USB. Preserve backups until restoration
is durably verified, and let a compatible USB finish interrupted cleanup. If other
modifications conflict, stop without overwriting them. See docs/uninstall.md.
Maintenance uses a compatible replacement USB stick; the original stick is not
required. Validate independence from old contents using freshly prepared media.
The SD bench path may qualify installer maintenance; keep its manual launch distinct
from the separately verified USB-insertion path. Do not require a spare USB
stick or Mac-attached storage for this check.
Arbitrary old-package compatibility is not promised.
Original-backup restoration is as-found restoration, not a factory reset.

USB maintenance should feel OEM: use Mazda's normal UI for concise progress,
completion and any necessary decisions, never debug alerts. USB insertion is
the intended entry point, with automatic detection/application where supported;
users should not need to browse the drive in the media center. The insertion
and launch mechanism must be proven on the supported firmware before promising
that experience. Keep the flow simple.

The product scope is comparable to Miatafy/ScreenTune's non-customization
improvements: startup/disclaimer behavior, unused services, logging and performance,
OEM menu/input conveniences, and phone/audio reliability. Preserve Mazda's look
and feel; do not turn this into themes, replacement dashboards or a launcher.
The disclaimer is the first experiment, not the architecture's scope.

The motivating problem is the user's native wireless CarPlay mod: it lags after
a long parked, cold start but is stable once running. Performance work should
target that experience. The owner will uninstall the existing wireless mod
before the first Open Connect installation. Do not maintain installer allowances
for its modified startup, board-detection or service files; require the supported
OEM originals. The owner rejects vehicle-fingerprint spoofing and wants an Open
Connect option to enable native wireless CarPlay while preserving actual vehicle
and hardware identity. The development candidate now has installed native
enablement and repeated-start reconnection checks; cold-start lag remains
unexplained and unmeasured for this candidate. Wireless baseline measurements
precede broader Services research; deep long-parked reliability work remains last.
Establish stock wired CarPlay early on the v74 bench for release compatibility
checks and timing/RAM baselines. Keep this fixture separate from changes to
native wireless enablement and cold-start behavior, which remain last in the
agreed sequence. Wired results do not reproduce wireless-specific timings.

Prefer native wireless CarPlay for everyday use, with explicit switching to an
internet connection through a phone/home hotspot when needed. Wired CarPlay plus
hotspot is an alternative, not the preferred experience. Investigate Mazda's
existing Wi-Fi modes and returning to CarPlay before adding network machinery.
Concurrent modes are not a requirement; online updates must not silently take
over the connection. An in-car version/settings page remains a proposal.

Unused Aha/Pandora/Stitcher, TV and other service choices, logging levels and
performance settings are first-class feature candidates. Their dependencies,
benefits and hardware applicability need evidence; reducing process counts or
idle memory alone is not proof of a useful improvement. Similar feature scope is
not a requirement to copy another product's implementation or defaults.
The owner also wants service and optimization research beyond Miatafy's documented
changes. Inspect this firmware's dependencies and measured startup/background work
to choose candidates. Implementation plan: after native wireless enablement and
its baseline, expand Services and measured optimizations before deep long-parked
lag work. Research may overlap collection; changes need a fixed comparison baseline.
The owner wants performance testing before service changes and a dedicated
Services page in Open Connect Settings before CarPlay work. Include Miatafy's
published timings in the baseline comparison, matching measurement definitions
and conditions before claiming reproduction. See PLAN.md and issues #9 and #86.
Maintain a dedicated [Performance evidence](docs/performance.md) section in the
docs for timings and RAM, with comparable per-run results, methods, failures and
regressions. RAM measurements during startup and matched workloads are required.
The development candidate now groups the measured native Warn filter and four
qualified DAB/TV/Stitcher leaves behind a single Base optimizations on/off setting, with an implementation default of off.
Qualify the complete installed bundle with individual service selections held fixed; further contents and
default changes need their own timing and RAM evidence.

For a future touchscreen follow-up, extend the preference to Factory behavior,
Always enabled and Disabled (ghost touch). Complete disable must cover startup
and normal use, including projection, while retaining commander navigation and
independent recovery. The exact firmware mechanism and delivery slot remain
unqualified; this does not expand the initial two-feature release. See
[#87](https://github.com/aeharding/open-connect/issues/87).

**Hard owner rule: Open Connect must not add overhead that slows boot or general
use. It must not increase RAM usage without the owner's explicit approval.**
This applies with Base optimizations off or on and to every optimization
configuration; meeting the bar in one preset does not qualify another. The
startup target is no measurable added delay compared with stock (approximately
zero seconds). No RAM increase has been approved by this rule.

Specific owner acceptance (2026-11-22): integrate dev.13's wireless-startup change
with its measured +1.15 percentage-point CPU increase in the later 60–170 s window
(+1.16 points across 20–170 s), in exchange for 2.21 s earlier visible Maps,
unresolved Home change, unchanged measured own-RAM components and the Settings
port fix. This decision applies to [PR #127](https://github.com/aeharding/open-connect/pull/127)'s
reviewed candidate; it is not a general waiver. Keep #9 open and continue removing
overhead. The [matched evidence](docs/wireless-startup-speed.md) records the limits.

Specific owner acceptance (2026-11-23): merge [PR #128](https://github.com/aeharding/open-connect/pull/128)'s
reviewed dev.14 candidate with its +12 KiB allocated tmpfs (436→448 KiB), including
+4 KiB with Base off. Listener/ignition private memory and PSS were unchanged in
the matched snapshots. This is candidate-specific acceptance, not a general RAM
waiver; keep #9 open. The [matched evidence](docs/base-startup-tuning.md) retains
the timing, CPU, memory and workload limits.

Specific owner acceptance (2026-11-23): proceed with [PR #129](https://github.com/aeharding/open-connect/pull/129)'s
reviewed dev.15 Services candidate despite the +1.407 s median visible-Maps tail
in the blocked three-start cohorts. Run ranges overlap and several native CMU
connection milestones were earlier; neither phone-only causation nor stock
parity is established. Home's midpoint was +0.200 s, with frame-endpoint
differences −0.001..+0.401 s. Own allocated tmpfs fell 4 KiB and helper private
pages were unchanged. Ignition PSS medians were 153 KiB in both cohorts, with
one 155 KiB candidate sample. The [recorded owner disposition](https://github.com/aeharding/open-connect/pull/129#issuecomment-7108804856)
applies to this candidate, not a general overhead/RAM waiver. Keep #9 open and
retain the [complete evidence and reload limit](docs/services-expansion.md).

Recover Open Connect's own startup and runtime overhead before expanding
Services further. Measure and remove redundant verification, staging and
background work while preserving integrity, locking, bounded recovery and
factory restoration. Compare timing, CPU and named RAM metrics under matched
conditions. Quantify any remaining RAM cost for an explicit owner decision;
do not infer approval from a performance improvement or from implementation
necessity. A partial reduction does not establish stock parity.

Development authorization (2026-11-23): implement dev.16 sparse MMUI/VUI loading
and an independent bounded Navigation delay with Base and Wireless on. The owner
pre-authorized the expected approximately +100/+144 KiB allocated tmpfs (depending
on disclaimer bypass), contingent on measuring the proposed MMUI/VUI PSS benefit.
This is permission for live qualification after source review, not final merge
acceptance or a Base-off RAM waiver. Confirm actual per-configuration costs and
the final owner disposition before merge.

Specific owner authorization (2026-11-23T23:48): dev.16 may merge overnight
only after independent Astra approval, green CI and no performance or functional
regressions, with allocated own-tmpfs growth **at most +152 KiB with Base on**
and **at most 0 B with Base off**. The owner explicitly authorized the measured
**+104/+108/+152 KiB Base-on** configurations and **−4 KiB Base-off** result
under that guardrail. This supersedes the earlier approximate +100/+144 KiB
qualification forecasts for [PR #131](https://github.com/aeharding/open-connect/pull/131),
not the general no-overhead rule. Keep unmatched projection/CPU/net-RAM limits
explicit and #9 open; this is not a broader performance or RAM waiver.

Discontinued or non-NA services such as DAB, TV, Stitcher and Aha may join Base
optimizations if their measured benefit and dependencies qualify. Active optional
services such as Pandora, Android Auto, SiriusXM and DVD remain individual
Services choices. The owner explicitly chose SiriusXM default on and DVD default
off for the next Services expansion; both remain configurable. The owner uses
SiriusXM in their car. CarPlay has priority when testing delayed voice startup;
explicitly name and measure delayed voice/phone/message readiness. Do that
pilot after the startup-overhead work and Android Auto pilot.

Every performance or optimization change needs comparable baseline and modified
timing trials. Define the timed operation and conditions before the change, run
repeated trials, and retain failures as well as successes. Report the spread and
any regressions; do not call a change faster without measured evidence.
Pair timings with relevant CPU, RAM and I/O measurements under the same workload
and startup phase. For CarPlay, measure time to usable projection and early-session
responsiveness, alongside connection/service readiness; Home appearing is not
CarPlay readiness. Separate cold, warm and resume conditions. Name the memory metric; lower RSS alone is not proof of a
useful improvement. Keep the baseline, feature set and measurement method explicit.

Published measurements must be reproducible by other contributors. Include the
collector and analysis revisions, exact commands, configuration, milestone
definitions, sampling intervals and individual results. Extend `oc` when it
materially simplifies repeatable timing/resource collection; this is a useful
option, not a required framework. Temporary service-disable and tuning experiments
may be checked into clearly labeled playground branches when that makes them
reproducible. Keep unfinished experiments out of main and retain the existing
publication exclusions for OEM code, credentials and private captures.

The autonomous bench and published reverse-engineering knowledge enable the
product and help contributors. Build them when they unblock a concrete experiment
or remove repeated effort. A 24/7 autonomous bench is an aspiration, not a
prerequisite for the first usable release or an active background schedule.
The user supplies physical resources; the primary owns software execution.
The bench supply may be power-cycled autonomously for experiments, without advance
notice. Its voltage setting must remain unchanged.

The `oc` CLI is only for bench instrumentation. Release packaging belongs in
repository build scripts, invoked directly by CI and local developers, not in `oc`.
Bench helpers are managed as one development profile: setup, status and teardown.
No per-helper manual activation, new CMU menu or graphical UI is needed. A thin
semantic CLI reuses working tools; Python on the host and POSIX sh on the CMU are
the initial implementation. Extend it only for concrete tasks. See docs/cli.md. Command-only ephemeral agents can test usability, while the primary
retains ownership of live state and the complete outcome.

The small **Developer options** page in Open Connect Settings is the agreed step
before performance-baseline and Services work. Deferred manual bench and
first-car validation do not block further development. The agreed
controls are labeled **UART** and **SSH**, with an **Import public key** option.
Keep the normal Developer options title and three controls. Explain that changes
apply after restart in the enable popups; omit the always-visible startup-state
header and disabled notice rows. Link the UART pin/cable guide
and explain SSH through a supported USB-to-network adapter in the owner docs.
The owner chose a password-free root shell over the physical UART connection, with a brief, matter-of-fact confirmation when enabling
it: passwordless root access over UART. Default
both owner-access options off; preserve Mazda's original login/key behavior when
off and restore the pre-install configuration on uninstall.
Keep diagnostic logging separate from interactive login. The private key stays
on the owner's computer. Use a fixed public-key file on maintenance USB for the
small initial import flow; qualify the firmware controls and complete UI flow.
Show actual state and any restart requirement, preserve the pre-install access
configuration for uninstall, and retain USB access/recovery when the UI is
unavailable. This product feature is separate from the bench helper profile.
See [#85](https://github.com/aeharding/open-connect/issues/85).

The owner suggested contextual documentation help, potentially an OEM-style Help
dialog with a QR code and short link to the relevant docs section. This remains
a proposal; placement and presentation are undecided. It does not expand the
current access-controls implementation.

The owner wants faster, automated development checks that reduce repeated
installation cycles. Use the existing fast host UI fixtures during iteration. A temporary RAM-only
native UI preview with simulated settings is the proposed next step, separate
from real installer qualification and persistent writes. Batch
UI edits before the final CI-built hardware cycle. Automate repeatable bench
steps where useful and measure installer bottlenecks before optimizing them;
retain durable transactions, original preservation and unknown-state refusal.

## Release implementation

Deliver one CI-built bundle that an owner extracts onto USB and installs on the
supported stock CMU. The small generic loader launches the installer payload.
The UI and install/uninstall backend run on the CMU without a host computer,
SSH, network access or `oc`. Preserve the runtime pieces needed for Settings and
uninstall on the CMU; a compatible replacement USB must also support maintenance.

Keep loader, UI and backend logic in checked-in static files. Runtime tokens,
ports and paths are data. Build output should be compiled native code and
checksum/version manifests, not generated shell or JavaScript application logic.
Use Make/shell and standard compiler/linker tools directly. Do not write a Python
packager or custom ELF linker. Python in the release build is allowed only if a
specific native compilation need cannot reasonably use standard tools; this does
not restrict existing Python bench instrumentation or host tests.

Use one small, explicit UI/backend command contract, chosen against actual CMU
capabilities. Do not carry image-request, short-lived receiver and D-Bus callback
chains into the product merely because a preview used them. Keep the transport
and allowed commands understandable; do not build another orchestration framework.

The backend owns install, reinstall, uninstall and interruption recovery. Use
one authoritative transaction record with explicit states and durable updates,
plus verified original backups and before/after snapshots. Avoid
scattered flags or receipts that independently claim operation state. Preserve
unknown later edits and reconcile uncertain outcomes before further writes.

The first standalone installer development prerelease includes persistent startup:
install once, remove the USB, and retain the features across ordinary ignition
cycles and reboots. Verify repeated starts, bounded failure recovery and the
renewal policy as part of that same delivery. Do not ship the bench's limited
trial-boot policy as the installer outcome. Label remaining qualification limits
plainly without making persistence a separate later milestone.

## One required firmware baseline

User decision: support **one exact firmware baseline at a time**. Current required
source baseline: **74.00.324A, North America (cmu150_NA)**, with exact source/API
guards. Other builds are unsupported. Keep maintained documentation on this
baseline; Git history preserves retired firmware guidance and experiments.

The Mazda-hosted **74.00.324A NA** package is hash-verified, and owner-key
development access has been demonstrated on that exact baseline. The maintained
port and reviewed CI bundle have install/update/startup/Settings/uninstall
evidence, including removable USB launch. Physical-input, broader recovery and
matching-car qualification remain. A general documented
upgrade route is unresolved; this is not an upgrade instruction. The owner has
confirmed the real car matches **74.00.324A NA**, the bench baseline. Carry that
confirmation forward; retain exact firmware/source guards before any writes. See the
[v74 access evidence](docs/reverse-engineering.md#owner-key-access-after-the-replacements-v74-upgrade).
The user wants modern firmware as the eventual requirement, not a growing
multi-firmware support matrix. Historical experiments remain evidence after the move.
Reject unsupported version/region/base before writes; do not auto-port offsets.
Additional regions, hardware generations and legacy release support are deferred.

## Working style: deliver the product

**“Elaborate is failure.”** We are hacking on the bench; Open Connect is not
installed in any real cars yet. Optimize for learning and useful working changes.
Short, reversible experiments are normal work, including experiments that explore
an opportunity rather than resolve a release blocker. Keep the complete owner
flow as the destination, integrate useful results, and retire superseded probes.
An experiment does not need production qualification before it can teach us something.

Use fast host checks while iterating, batch related edits, and check the affected
native behavior. Reserve complete install/update/restart/uninstall cycles for
changes to those mechanisms or evidence needed for an actual release claim.
Reuse existing lifecycle evidence when the relevant code is unchanged; identify
its actual revision and limits. Run required suites once the batch is ready, and
repeat them when a new change or failure warrants it. Do not spend more effort
on receipts, bespoke scripts or coordination than the question needs.

Major plans receive one brief independent adversarial review before substantial
implementation; see CONTRIBUTING.md. The reviewer should challenge scope,
assumptions, complexity and execution cost, with our current bench stage explicit.
The purpose is a better next decision and faster useful experiments. Routine
experiments and implementation choices do not each need another review or owner
approval. Keep independent work moving while a plan is reviewed.

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

Infrastructure must serve the current release or remove demonstrated repetition.
Keep exact-base checks, preserved originals, repeatable execution and independent
undo. Defer generalized plugin/configuration systems, broad compatibility and
speculative workflows. Judge progress by the complete user flow, not another
loader, harness or preview increment.

Before choosing an implementation, define the user-visible outcome and the
evidence that would establish it. A partial improvement may be a useful experiment;
label it explicitly rather than treating it as delivery of the requested feature.
Check relevant prior art early, then compare it against Mazda's actual behavior.

Each experiment must answer one concrete question that changes the next decision.
Explore and experiment aggressively within the agreed scope: prefer short,
bounded tests and batches of related release checks, then consolidate findings.
Do not let repeated evidence handling or per-step publication dominate the work.
Infrastructure, checks and documentation earn their scope by supporting that
question. Reuse tested orchestration and check the real entry point before live
work; do not attribute avoidable runner failures to missing hardware.
SSH improves throughput; ACC gates specific lifecycle tests, not all development.

Keep proposals provisional and overviews short: current direction, evidence,
open questions. Surface consequential choices with a concrete recommendation.
Distinguish device behavior from observer/tool failure immediately; an incomplete
capture cannot establish that the CMU failed, and a successful command cannot
establish that the feature worked. Report results clearly without requiring the
user to repeatedly redirect the work.

## Ownership and execution

Before substantial implementation based on an inferred need, clarify the
assumption and scope with the owner. This includes compatibility allowances,
new architecture or extra features that were not requested. The roadmap does
not authorize speculative extensions. Keep routine work within the agreed scope
moving without repeated confirmation.

- One primary owns the complete outcome. Use ephemeral Herdr peers for focused
  reviews of major plans and final PRs, without a standing specialist team.
  Teammates are equals: trust their judgment. Keep bench ownership serialized.
  Create fresh agents for this work; do not reuse or notify the owner's
  previously open sessions. Disable inherited Herdr parent notifications.
  Put each new reviewer in a visible Herdr tab immediately.
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

The independent native bypass and paired renderer cleanup now have v74 CI-bundle
startup and restored-stock evidence. Keep the implementation independently
distributable under AGPL. Noncommercial comparison adaptations stay private.
A clean bypass is the outcome; visual masking or timer reduction alone is not it.
Do not indefinitely tune an unmeasured frame at the expense of a usable product.

[PLAN.md](PLAN.md) orders delivery: the v74 installer with persistent startup,
then the developer menu and measured performance work. Native
install/undo must account for loaded-module lifetime: restoring disk bytes does
not unload it. Reuse the working hardlink-hold recovery where native replacement
requires it.

## Extension architecture direction

Design around one complete selected boot configuration covering service policy,
configuration and optional code. A native/JS loader is an adapter, not the whole
architecture. Global disable must account for earlier service/configuration
effects too; a late MMUI flag cannot undo them. Prefer boot-scoped changes over
persistent edits that need repair before stock startup can resume.

The owner requested a retrospective and deep plugin-architecture research,
especially layering, conflicting changes, restoration in either removal order
and dogfooding our own features. The [research proposal](docs/extension-architecture.md)
recommends core-owned hooks, typed resource providers and the existing transaction.
These are recommendations, not an approved framework implementation or new roadmap
phase. A marketplace is a possible destination, not the current deliverable.
Call features built-in plugins when they use the same package, conflict and
removal contract as independent plugins; a label change alone is insufficient.
Preserve unknown external edits and distinguish activation compatibility from the
evidence required to release our own changes. Keep requested disable, baseline
startup, failed-start fallback and complete uninstall distinct.

User priority: prevent an endless watchdog boot loop first; avoid unnecessary
safe-mode fallback after battery loss or an unrelated Mazda fault second.
Recovery should preserve installed features and the user's selection, not
uninstall or blame a tweak from one reset. New configurations get stricter trial
handling than previously confirmed ones. Any automatic retry policy must have a
persistent finite limit; a startup-ready signal must not erase later-fault
protection. Retry counts and reset classification remain proposed until qualified.

Keep recovery proportional to the delivered feature. Freeze expansion of the
Home-only supervisor prototype. Include persistent startup and its renewal policy
in the standalone installer prerelease; avoid a universal health-detection
project. Intentional button resets must
not silently replenish attempts or be blamed on a mod. Automatic everyday renewal
requires qualified ACC evidence.

Recovery disables the disclaimer bypass for the fallback boot and restores the
pre-install touchscreen setting. Mazda reads that setting before our hook, so
the restored value takes effect on the next boot. Do not add a forced recovery
restart solely to apply it; this is the user's accepted prerelease behavior.

Use tooling/ for host code, cmu/ for bootstrap, adapters and features, and tests/
for maintained checks. Remove superseded research probes and their separate CI
targets; Git preserves them. Keep useful components with their maintained callers
and tests. Do not keep a parallel prototype tree or another history folder.

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
