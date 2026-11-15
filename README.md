# Mazda Open Connect

Improve first-generation Mazda Connect while preserving Mazda's look and feel:
startup behavior, unused services, logging/performance, controls and connectivity.
The first feature is a disclaimer bypass; the
[architecture](docs/extension-architecture.md) covers the broader feature scope.

**Development project, not an end-user installer.**
The supported bench firmware is **55.00.750B North America**.

## Start here

**[Read the documentation](https://aeharding.github.io/open-connect/)** — bench
wiring, development guides and CMU reverse engineering.

- **Build a bench:** [power, display and UART wiring](docs/bench-setup.md).
- **Use a connected bench:** [CLI commands](docs/cli.md).
- **Follow the first feature:** [disclaimer bypass and availability](docs/disclaimer-preview.md).
- **Change the code:** install the host tools and run the offline tests below.
- **Understand the Mazda behavior:** [findings](docs/reverse-engineering.md).
- **Choose work:** [roadmap](PLAN.md) and [issues](https://github.com/aeharding/open-connect/issues).

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/oc --help
.venv/bin/python tests/run_offline.py
~~~

Installation and offline tests do not connect to or change the CMU.
The host tests include the CLI, bench profile, UART protocol and file transfers.
Prototype-specific checks are separate and may need private OEM inputs.

## Where things live

| Path | Purpose |
| --- | --- |
| [tooling/open_connect/](tooling/open_connect/) | Host CLI, firmware builders and device operations |
| [cmu/](cmu/) | Code and templates that run on the CMU |
| [tests/](tests/) | Maintained host, shell and build checks |
| [experiments/](experiments/README.md) | Unfinished research probes, outside the feature workflow |
| [docs/](docs/index.md) | User guides, development instructions and CMU research |

Installing the Python package installs host tools only. Building a feature uses
the checkout's target sources and your private OEM inputs; it does not install it.
Generated firmware files are never included in the package.

[Contributing](CONTRIBUTING.md) · [Roadmap](PLAN.md) · [Working agreement](STEERING.md)

## License

Original code is **AGPL-3.0-or-later** ([LICENSE](LICENSE)).
[Third-party boundaries](THIRD_PARTY.md) explain excluded comparison code.
OEM firmware, credentials and raw captures are private. Paths under ignored runs/
refer to local evidence, not files available in a fresh checkout.
