# Develop Open Connect

Start with an offline checkout. You can work on the host tools and documentation
without a CMU or private firmware files.

## Install and test

Use Python 3.13, matching Linux CI, and Clang for the host C checks:

~~~sh
git clone https://github.com/aeharding/open-connect.git
cd open-connect
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/oc --help
.venv/bin/oc bench setup
.venv/bin/ruff check tooling tests
.venv/bin/ruff format --check tooling tests
.venv/bin/python tests/run_offline.py
~~~

The setup command above is a dry run. The offline tests use fake transports,
local PTYs and temporary files; they do not open the physical bench.

## Find the right code

| Location | Purpose |
| --- | --- |
| [tooling/open_connect/](https://github.com/aeharding/open-connect/tree/main/tooling/open_connect) | Host CLI, firmware builders, device operations and bench profile |
| [tests/](https://github.com/aeharding/open-connect/tree/main/tests) | Maintained offline tests for the host tools |
| [cmu/](https://github.com/aeharding/open-connect/tree/main/cmu) | Target startup code, firmware adapters and feature sources |
| [experiments/](https://github.com/aeharding/open-connect/tree/main/experiments) | Unfinished research probes; not dependencies of the feature CLI |
| [docs/](https://github.com/aeharding/open-connect/tree/main/docs) | This website's Markdown sources |

The public suite reports explicit skips for tests needing private OEM inputs.
[The developer feature guide](disclaimer-development.md) covers the real build
and its private checks. Keep generated firmware files out of commits.

## Make one complete change

Choose a concrete [issue](https://github.com/aeharding/open-connect/issues), use a
short-lived branch, and open a PR with the problem, resulting behavior and relevant
validation. Every PR needs an independent adversarial review of its final
revision before merge, including documentation changes.

The [contribution guide](https://github.com/aeharding/open-connect/blob/main/CONTRIBUTING.md)
is the source for required checks and review policy. The
[roadmap](https://github.com/aeharding/open-connect/blob/main/PLAN.md) sets priorities.

For device work, read [bench setup](bench-setup.md) and [CLI usage](cli.md).
One operator owns the UART. Preserve originals, provide independent undo and
verify what is on disk and what is loaded. Current state of the project's
particular bench stays in the
[repository handoff](https://github.com/aeharding/open-connect/blob/main/docs/bench-state.txt),
not in a generic setup recipe.

## Measure optimizations

Every performance or optimization change needs a measured baseline and modified
trials—not just fewer processes or a lower memory number.

- Define the timed operation, workload and startup phase before changing code.
  Keep firmware, hardware and other enabled features comparable.
- Repeat timings and relevant CPU, RAM and I/O samples. Name the memory metric
  and account for measurement overhead.
- Retain failures, report the spread and check regressions. Claim only the
  improvement the measurements demonstrate.
