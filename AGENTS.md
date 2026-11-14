# Agent instructions

Read [STEERING.md](STEERING.md) for user direction and [PLAN.md](PLAN.md) for priorities.
Use [docs/bench-state.txt](docs/bench-state.txt) only when operating the existing lab.
Historical plans, ready profiles and assignments are evidence, not current authority.

## Ownership and pace

One primary owns implementation, tests, bench operation, recovery and integration.
No standing specialist agents. Use ephemeral reviewers only when explicitly
requested or required by the contribution workflow, for one concrete question.
Answer the user promptly; status questions do not cancel ongoing work.
Build the smallest complete experiment. Avoid duplicated audits, tooling and logs.

Run program/file operations through Herdr hc. Keep UART/camera ownership serialized
and close owned resources. Match process identity before termination.
The user supplies physical resources; agents handle software operation. Do not
ask the user to press buttons, dismiss dialogs or rewire things to complete agent work.

## Code and documentation

- src/open_connect/: host Python; nothing here is installed on the CMU.
- cmu/: target integration code, including firmware adapters and probes.
- tests/: maintained host tests, including the semantic CLI and bench profile.
- experiments/: prototype mods and trial tooling; generated payloads may affect the CMU.
- docs/: Markdown sources for the GitHub Pages site: setup, usage and CMU findings.
  Navigation and site settings are in zensical.toml. Use Git for historical records.
- GitHub issues/PRs: work queue and review. No separate progress-dashboard requirement.

Use the installed oc command or python -m open_connect. Low-level UART operations
are oc uart; profile operations are oc bench. See docs/cli.md.
Run tests/run_offline.py for host changes, then only relevant experiment checks.
Do not change historical manifests to claim old evidence used new code.

## Device work

Current supported firmware is exactly 55.00.750B NA/cmu150_NA.
Confirm actual identity before operations; remembered paths/PIDs/inodes are not authority.
UART is 115200/8N1, no flow control, RTS/DTR inactive. The adapter is presently
pinned to FT232R VID:PID 0403:6001, serial A9048JM0. Re-enumerate before opening.
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

## Publication

Use aeharding/open-connect, branches and PRs. Original work is AGPL-3.0-or-later.
Before merging any PR, obtain an independent adversarial review of the final
revision and resolve blockers. This includes docs-only changes and deletions.
Follow CONTRIBUTING.md; ephemeral review agents are explicitly authorized for this.
Never publish ignored OEM files, credentials, raw captures or incompatible comparison
adaptations. Stage an explicit reviewed file set; see THIRD_PARTY.md.
Current state belongs only in docs/bench-state.txt; new knowledge belongs in
docs/reverse-engineering.md with a concise supporting record when needed.
