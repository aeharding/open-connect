# Agent instructions

Read [STEERING.md](STEERING.md) for user direction and [PLAN.md](PLAN.md) for priorities.
Use [docs/bench-state.txt](docs/bench-state.txt) only when operating the existing lab.
Historical plans, ready profiles and assignments are evidence, not current authority.

## Ownership and pace

One primary owns integration, complete validation, bench operation and recovery.
Delegate independent fixes in isolated branches when useful. During the current
architecture refinement, use multiple fresh adversarial peers in repeated rounds
to challenge code quality, Mazda patterns, ownership and unnecessary complexity.
Keep the findings and their dispositions in GitHub issues; refine that list as
fixes and new evidence arrive. Verify claimed bugs and have revised code reviewed
again. No standing specialists. Use GPT-6.2-Astra for adversarial, major-plan and
final PR reviews as described in CONTRIBUTING.md; peers are equals with room to
challenge the approach. Keep live bench ownership serialized.
Create fresh Herdr agents; do not reuse the owner's previously open sessions.
Use --no-parent --no-notify so inherited context cannot route updates into them.
Attach each new reviewer to a visible Herdr tab immediately.
Answer the user promptly; status questions do not cancel ongoing work.
Current work is bench hacking, with no real-car installations. Favor quick,
bounded experiments and usable increments. Keep working toward the release path;
experiments need not be release blockers. Batch edits and checks, reuse working
procedures, and repeat hardware checks only for affected behavior. Do not impose
production qualification on each experiment. Avoid duplicated audits, tooling and
logs. Apply STEERING.md: outcome first,
early prior art, one decision per experiment, and separate device/tooling failures.

Run commands and file operations directly, including Git, builds and tests.
Use Herdr hc only for agent communication. Give uploads and boot observers
explicit deadlines long enough to complete. Keep UART/camera ownership serialized
and close owned resources. Match process identity before termination.
The user supplies physical resources; agents handle software operation. Do not
ask the user to press buttons, dismiss dialogs or rewire things to complete agent work.

## Code and documentation

- tooling/open_connect/: host Python; nothing here is installed on the CMU.
- cmu/: target integration code, including firmware adapters and probes.
- tests/: maintained host tests, including the semantic CLI and bench profile.
- Superseded research probes live in Git history; do not keep a parallel prototype tree.
- docs/: Markdown sources for the GitHub Pages site: setup, usage and CMU findings.
  Navigation and site settings are in zensical.toml. Use Git for historical records.
- GitHub issues/PRs: work queue and review. No separate progress-dashboard requirement.

The installed oc command (or python -m open_connect) is only for bench
instrumentation: oc uart for low-level UART and oc bench for the profile.
Release builds use Make/shell and standard native compiler/linker tools directly.
Keep installer logic in static files; generate compiled assets and data manifests
only. Do not add Python packaging/code generation or custom ELF linking.
Use one simple UI/backend command contract and one authoritative durable
transaction record. See STEERING.md for the release implementation direction.
See docs/cli.md for bench operations.
Run tests/run_offline.py for host changes, then only relevant experiment checks.
Do not change historical manifests to claim old evidence used new code.

## Device work

Current source baseline is exactly 74.00.324A NA/cmu150_NA; release qualification is in progress.
Confirm actual identity before operations; remembered paths/PIDs/inodes are not authority.
UART is 115200/8N1, no flow control, RTS/DTR inactive. The adapter is presently
pinned to FT232R VID:PID 0403:6001, serial A9048JM0 by default. Other benches
explicitly set OC_UART_SERIAL before launching a process; that same identity binds
the lock and every re-enumeration. Re-enumerate before opening.
A shell can persist after port closure; establish its actual state before commands.

Use finite operations, exact-base checks, preserved originals and independent undo.
Uncertain transmission is not permission to resend. Preserve raw failures and
reconcile from fresh evidence. Long mutating programs must be staged as data,
verified, then executed through a short guarded entry.
The existing runner limits physical input lines to 600 bytes and paces TX.
BusyBox grep lacks -x; timeout uses -t SECONDS; use observed capabilities.

For native replacement, retain same-filesystem hardlink holds across loaded-module
lifetime. Restoring disk bytes does not unload modified code. Verify physical root
mount flags, actual mappings and restored-original startup when closing a trial.
Keep the stock frontend heartbeat and native initialization/cleanup intact.
CMU JavaScript must follow stock CMU loading, input, transition and lifecycle
patterns. Inspect the equivalent stock path first and preserve framework
ownership. Justify and document necessary deviations with source or runtime
evidence, as required by the owner rule in STEERING.md.

Treat Opera `Navigate`, including a `javascript:` URL, as browser navigation:
it cancels pending resource loads. Product code must not use it for routine
JavaScript execution or teardown already completed by the owning frontend.
Necessary USB launch/removal must check the current session and its close state
before crossing that boundary. Preserve native loading, heartbeat and watchdogs.

Installed Settings and the transient installer popup have independent ownership.
Settings loads only from the boot-selected installed package; USB must never
replace its code, row, callbacks or backend, or make entry wait for USB verification.
The popup sends maintenance choices to the backend and never installs a Settings
interface into the running browser. Updates take effect through normal restart.
Cleanup affects only the interface/session that created it. Preserve one durable
transaction record and protection against conflicting changes. See STEERING.md.

For changes to navigation, teardown or maintenance, cover partial module delivery,
late/failed replies, cancellation and real dialog lifecycle callbacks in behavior
tests. Native verification must witness dependency registration and framework
idle beyond the reproduced failure window. See the
[v74 diagnosis](docs/reverse-engineering.md#usb-browser-navigation-and-settings-ownership-on-v74).

## Publication

Use aeharding/open-connect, branches and PRs. Original work is AGPL-3.0-or-later.
Before merging any PR, obtain an independent adversarial review of the final
revision and resolve blockers. This includes docs-only changes and deletions.
Follow CONTRIBUTING.md; ephemeral review agents are explicitly authorized for this.
Never publish ignored OEM files, credentials, raw captures or incompatible comparison
adaptations. Reviewed direct UI screenshots for the owner guide are allowed;
see docs/documentation.md. Stage an explicit reviewed file set; see THIRD_PARTY.md.
Current state belongs only in docs/bench-state.txt; new knowledge belongs in
docs/reverse-engineering.md with a concise supporting record when needed.
