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

## Review major plans without adding ceremony

Get one independent adversarial review before substantial implementation of a
major change to architecture, feature scope, delivery sequence or state/recovery
design. A short approach and the relevant code or evidence are enough; no formal
plan document or new approval process is required. Routine experiments and local
implementation choices do not need separate plan reviews.

Tell the reviewer the development stage: we are hacking on the bench, with no
real-car installations yet. Ask whether the plan reaches a useful result quickly,
which assumptions need an experiment, and what complexity or verification can be
removed. Challenge execution overhead as well as correctness. Do not manufacture
production requirements, speculative risks or findings to fill a checklist.
Continue independent work while the review runs; resolve consequential findings
before committing to the major implementation. The final PR still gets its normal
review, focused on the actual delta rather than repeating the entire plan audit.

## Release implementation

Keep development moving toward the maintained USB install/restart/Settings/
uninstall path. Use bounded experiments to learn; they need not be release blockers.
An experiment is not a claim that the complete owner flow is qualified.
The installer prerelease includes persistent features after USB removal and
ordinary restarts, with repeated-start and bounded-recovery checks.
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

For UI iteration, run `make check-ui` with Node.js. It exercises the maintained
dialog, Settings, runtime and loader fixtures without a CMU, release build or
private inputs. Batch small UI edits and use targeted native layout checks where
needed. Select hardware checks from the behavior changed. Complete lifecycle
qualification belongs to changes in installer/state/recovery behavior and actual
release claims; reuse existing evidence for unchanged mechanisms and name its
revision. UI text, layout and read-only status changes need focused checks, not
another complete install/update/uninstall cycle. The offline suite remains the
final local check for host/code batches; docs-only edits use the strict docs build.
Required CI checks still run on the final PR revision.

Host code lives in tooling/open_connect/, with tests in tests/.
The offline runner includes the CLI and bench profile and opens no physical device.
The installed entry point is oc; python -m open_connect is equivalent.

CI runs those host checks on Linux with Python 3.13 for every PR and main push,
then checks the installed CLI from outside the checkout. Require the Host checks
job to pass alongside adversarial review before merging. To apply formatting
locally, run .venv/bin/ruff format tooling tests.

Ruff covers tooling/ and tests/. The offline suite includes the public CLI,
publication/undo with real local files and mappings, generated video,
and installer transactions with local sockets and shell processes. It uses no physical
device, credentials or OEM files. Install Clang for its host C checks; optional
Node.js and ffmpeg checks report skips if those tools are absent.

CI also builds the maintained ARM helpers and public USB bundle with standard tools.
Private exact-original checks use tests/check_firmware.py as described in the
[installer development guide](docs/installer-development.md#private-firmware-checks).
An absent private fixture is an explicit skip in the public suite. Host tests do not establish
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

Use the [maintained installer workflow](docs/installer-development.md) for bench
verification. Report missing private OEM inputs rather than claiming their checks passed.
Read [bench setup](docs/bench-setup.md), [CLI usage](docs/cli.md) and the current
[lab state](docs/bench-state.txt) before operating the project's bench.
One operator owns UART and cleanup.

Before implementing a substantive patch, state the user-visible outcome, the
question this experiment answers, and evidence that would count as success.
Check relevant existing implementations early and compare them with actual Mazda
behavior. Label partial improvements and unproved proposals explicitly.

Use the major-plan review above when it applies. For routine experiments, choose
the smallest useful next check and run it directly. Reuse working instrumentation,
check actual entry points, and verify undo for effects introduced by the trial.
Batch related checks and documentation; do not create a new script, audit or
publication step for every command. Keep release qualification separate from
exploration so experiments stay quick.
Record firmware, bench profile, installed versus loaded code, and whether a
failure occurred in the CMU or our tooling. Unknown outcomes stay unknown until
reconciled. Tests and infrastructure must support the concrete question; avoid
repeated review gates and success claims based only on command completion.

## Keep it small

Keep host bench code in the package, maintained target code in cmu and human
documentation in docs. Delete superseded probes and documents; Git preserves them.
Do not create another top-level notes, research,
examples or dashboard system. Prefer consolidating already-shared code over
inventing a general framework. Git history preserves retired implementations.

Only original AGPL-compatible code and sanitized findings belong in commits.
Never add OEM binaries/sources, credentials, private captures or the noncommercial
comparison adaptations. See [THIRD_PARTY.md](THIRD_PARTY.md).
Support one exact firmware baseline: currently 74.00.324A NA.

Use [PLAN.md](PLAN.md) for priorities and [STEERING.md](STEERING.md) for product
direction. Update useful findings after results, not a journal after every command.
