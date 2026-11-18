# Contributing

Start with [README.md](README.md). Work is tracked in
[GitHub issues](https://github.com/aeharding/open-connect/issues); use short-lived
branches and reviewable pull requests.

## Review before every merge

Every PR requires an independent adversarial review before merging, including
documentation, moves, deletions and small fixes. A separate ephemeral reviewer
or another contributor must inspect the actual diff and affected entry points,
not just the author's summary. The author remains responsible for the result.

Challenge whether a newcomer can understand the result, what became broken or
misleading, what is unnecessary, and whether the evidence supports the claims.
Report concrete findings with severity and file references; do not manufacture
objections to fill a checklist.

Record the reviewed commit, findings and their disposition in the PR. Resolve
blocking findings before merge. After changes, have the reviewer check the
affected delta; a review of an earlier revision is not approval of new code.
Keep this proportional: one focused review, not a standing review team.

## Release implementation

Complete the maintained USB install/restart/Settings/uninstall path. Targeted
experiments resolve concrete blockers; another standalone preview is not delivery.
Keep loader, UI and backend logic in static files. Make/shell invokes standard
native compiler/linker tools and packages the bundle; build-generated content is
compiled code and data manifests. `oc` is bench instrumentation, not a release
build or product dependency. Python remains appropriate for existing host bench
tools and tests; any release-build exception must meet STEERING.md's narrow
native-compilation rule.

Use one explicit UI/backend command contract and one authoritative durable
transaction record with verified backups. Review interruption recovery and actual
state reconciliation, not just the successful install path. Validate the actual
CI bundle on the supported CMU. Installation and maintenance must work without
SSH or a host computer. See [the steering agreement](STEERING.md#release-implementation).

## Host code

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/ruff check tooling tests
.venv/bin/ruff format --check tooling tests
.venv/bin/python tests/run_offline.py
~~~

Host code lives in tooling/open_connect/, with tests in tests/.
The offline runner includes the CLI and bench profile and opens no physical device.
The installed entry point is oc; python -m open_connect is equivalent.

CI runs those host checks on Linux with Python 3.13 for every PR and main push,
then checks the installed CLI from outside the checkout. Require the Host checks
job to pass alongside adversarial review before merging. To apply formatting
locally, run .venv/bin/ruff format tooling tests.

Ruff covers tooling/ and tests/. The offline suite includes the public CLI,
publication/undo with real local files and mappings, simulated boot observation,
and startup selection with local sockets and shell processes. It uses no physical
device, credentials or OEM files. Install Clang for its host C checks; optional
Node.js and ffmpeg checks report skips if those tools are absent.

CI also builds the small ARM helpers and checks the remaining research probes.
Private native/JS input checks run through oc feature build; an absent private
fixture is an explicit skip in the public suite. Host tests do not establish
firmware behavior or successful recovery on a CMU.

Actions are pinned to commit hashes, validation jobs have read-only permissions, and
Dependabot proposes monthly grouped updates. Dependency PRs require the same
tests and adversarial review; there is no automatic merge. Reviewed documentation
on main is deployed automatically to GitHub Pages.

## Documentation

Edit Markdown in docs/ and navigation in zensical.toml. With Python 3.13:

~~~sh
.venv/bin/python -m pip install -e ".[docs]"
.venv/bin/zensical serve
# Before opening a PR:
.venv/bin/zensical build --clean --strict
~~~

The Documentation build job validates internal links and anchors on every PR.
Main builds deploy to [GitHub Pages](https://aeharding.github.io/open-connect/).
See [documentation guidance](docs/documentation.md) for content and publication rules.

## Mods and device work

Use the [developer feature workflow](docs/disclaimer-development.md) for the maintained
feature. Unfinished probes stay in [experiments/](experiments/README.md). Report
missing private OEM inputs rather than claiming their checks passed.
Read [bench setup](docs/bench-setup.md), [CLI usage](docs/cli.md) and the current
[lab state](docs/bench-state.txt) before operating the project's bench.
One operator owns UART and cleanup.

Before implementing a substantive patch, state the user-visible outcome, the
question this experiment answers, and evidence that would count as success.
Check relevant existing implementations early and compare them with actual Mazda
behavior. Label partial improvements and unproved proposals explicitly.

Write a short approach and use one focused review. Reuse working instrumentation,
check the real release entry point, then qualify the complete flow and undo. Use
a separate experiment only when a specific unknown blocks that qualification.
Record firmware, bench profile, installed versus loaded code, and whether a
failure occurred in the CMU or our tooling. Unknown outcomes stay unknown until
reconciled. Tests and infrastructure must support the concrete question; avoid
repeated review gates and success claims based only on command completion.

## Keep it small

Keep host code in the package, target-specific prototypes in experiments and
human documentation in docs. Delete superseded documents; Git preserves them. Do not create another top-level notes, research,
examples or dashboard system. Prefer consolidating already-shared code over
inventing a general framework. Git history preserves retired implementations.

Only original AGPL-compatible code and sanitized findings belong in commits.
Never add OEM binaries/sources, credentials, private captures or the noncommercial
comparison adaptations. See [THIRD_PARTY.md](THIRD_PARTY.md).
Support one exact firmware baseline: currently 55.00.750B NA.

Use [PLAN.md](PLAN.md) for priorities and [STEERING.md](STEERING.md) for product
direction. Update useful findings after results, not a journal after every command.
