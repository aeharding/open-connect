# Mazda Open Connect

Make first-generation Mazda Connect feel factory-original, work more reliably,
and be easy to maintain. First feature: a clean startup disclaimer bypass.

**Development project, not an end-user installer.**
The supported bench firmware is **55.00.750B North America**.

## Start here

- **Build a bench:** [power, display and UART wiring](docs/bench-setup.md).
- **Use a connected bench:** [CLI commands](docs/cli.md).
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

| Path | Purpose | Runs where? |
| --- | --- | --- |
| [src/open_connect/](src/open_connect/) | Python CLI, UART transport, file transfer and runtime bench profile | Your computer |
| [cmu/adapters/](cmu/adapters/) | Firmware-specific target integration; currently a host-built native loader probe | CMU when explicitly installed; no automatic deployment |
| [tests/](tests/) | Offline tests for that host package | Your computer; fake transport or local PTYs |
| [experiments/](experiments/) | Prototype mods, builders and bench trials; see its index before running anything | Builders run on the host; generated payloads may change the CMU |
| [docs/](docs/README.md) | Setup, usage and Mazda findings | Documentation |

There is no automatic deployment step. Installing the Python package installs
**only host tools**. Product patches are still experiments, not bundled into the CLI.
The Python import name uses an underscore (open_connect); the project/command
names are Open Connect and oc.

[Contributing](CONTRIBUTING.md) · [Roadmap](PLAN.md) · [Working agreement](STEERING.md)

## License

Original code is **AGPL-3.0-or-later** ([LICENSE](LICENSE)).
[Third-party boundaries](THIRD_PARTY.md) explain excluded comparison code.
OEM firmware, credentials and raw captures are private. Paths under ignored runs/
refer to local evidence, not files available in a fresh checkout.
