# Developing Open Connect

GitHub is the development home:
https://github.com/aeharding/open-connect

Read [STEERING.md](STEERING.md) and [PLAN.md](PLAN.md). Bench operation also
requires [AGENTS.md](AGENTS.md). Keep experiments small and complete.

1. Use an issue for a concrete feature, bug or investigation. State the outcome,
   current Mazda evidence, simplest plausible approach and how to test/undo it.
   A routine fix can go directly into an existing issue's branch.
2. For a substantive design, write a short plan and use one focused reviewer to
   challenge it against actual Mazda code and simpler existing mechanisms.
   The reviewer answers a specific question and exits. The primary owns the work;
   repeated reviews are not a gate for each command.
3. Implement on a short-lived branch. Test the real entry point and relevant
   failure cases, then run the authorized bench experiment. Record firmware,
   enabled bench profile, loaded versus disk state, result and undo.
4. Open a pull request linked to the issue. Explain the resulting behavior, tests,
   actual bench evidence and remaining limits. Review the diff as well as the plan.
   Do not claim host mocks prove a live device result.
5. Merge a coherent completed change and update the issue/plan. Keep historical
   failures intact; use a new result to document reconciliation.

## Evidence and licensing

Use AGPL-3.0-or-later for original contributions and preserve existing attribution.
See [THIRD_PARTY.md](THIRD_PARTY.md). Do not upload OEM files, firmware packages,
credentials, raw UART logs or private captures. Publish concise findings, synthetic
fixtures, hashes and sanitized results. Evidence references under ignored `runs/`
refer to local/offloaded material; they are not available in a fresh checkout.

Development-only helpers belong in `bench/`; experimental work remains in
`experiments/`. End-user releases must exclude bench overrides. Test reports
must distinguish stock, feature-only and bench-profile-enabled runs.

## Host checks

Use the focused check command documented beside the affected experiment. Existing
checks may require exact private OEM inputs; report that dependency rather than
fabricating a passing result. The general offline runner is `tests/run_offline.py`.
No hardware access is implied by opening a PR or running a host check.

## Triage and support

Use one priority label: `priority: now`, `priority: next` or `priority: later`,
plus the relevant area and outcome milestone. `now` is priority, not a claim that
multiple implementations are running. Put the dependency and next concrete action
in the issue. A blocker applies only to the dependent step; keep useful preparation
moving. Triage after useful results rather than running recurring meetings.

Support one exact firmware baseline at a time: currently 55.00.750B NA.
Changing the baseline requires qualified stock/access evidence and feature
requalification. Reject unsupported builds; do not add legacy compatibility
without an explicit change to project direction.

Before adding infrastructure, name the current experiment it unblocks or the
repeated task it removes. Implement that smallest useful piece, using existing
tools. Preserve exact-base checks and undo; defer generalized configuration,
plugin systems and multi-version abstractions until concrete use requires them.
The first preview exposes Install/update and Uninstall only; reinstall and
interruption recovery reuse those paths.
