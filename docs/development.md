# Develop Open Connect

Start with an offline checkout. You can work on the host tools and documentation
without a CMU or private firmware files.

## Install and test

Use Python 3.13, matching Linux CI:

~~~sh
git clone https://github.com/aeharding/open-connect.git
cd open-connect
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/oc --help
.venv/bin/oc bench setup
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/python tests/run_offline.py
~~~

The setup command above is a dry run. The offline tests use fake transports,
local PTYs and temporary files; they do not open the physical bench.

## Find the right code

| Location | Purpose |
| --- | --- |
| [src/open_connect/](https://github.com/aeharding/open-connect/tree/main/src/open_connect) | Host CLI, UART transport, file transfer and bench profile |
| [tests/](https://github.com/aeharding/open-connect/tree/main/tests) | Maintained offline tests for the host tools |
| [cmu/](https://github.com/aeharding/open-connect/tree/main/cmu) | Target integration code; currently a host-built loader probe |
| [experiments/](https://github.com/aeharding/open-connect/tree/main/experiments) | Prototype patches and bench trials, each with its own instructions |
| [docs/](https://github.com/aeharding/open-connect/tree/main/docs) | This website's Markdown sources |

Some prototype checks require privately obtained, exact firmware files. Their
absence is not a test pass. Follow the selected experiment's README and keep
generated OEM-derived payloads out of commits.

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
