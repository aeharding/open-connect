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

## Host code

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python tests/run_offline.py
~~~

Host code lives in src/open_connect/, with tests in tests/.
The offline runner includes the CLI and bench profile and opens no physical device.
The installed entry point is oc; python -m open_connect is equivalent.

## Mods and device work

Choose a prototype from [experiments/](experiments/README.md). Its own checks may
need private OEM inputs; report missing inputs rather than claiming success.
Read [bench setup](docs/bench-setup.md), [CLI usage](docs/cli.md) and the current
[lab state](docs/bench-state.txt) before operating the project's bench.
One operator owns UART and cleanup.

For a substantive patch, write a short approach and use one focused review against
actual Mazda behavior. Implement, test the relevant failure modes, run the useful
bench experiment and undo. Record firmware, enabled bench profile and the distinction
between installed files and loaded code. Avoid repeated review gates.

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
