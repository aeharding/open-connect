# Mazda Open Connect

Improve first-generation Mazda Connect while preserving Mazda's look and feel:
startup behavior, unused services, logging/performance, controls and connectivity.
The first USB installer keeps the touchscreen enabled and skips the startup
disclaimer, with preferences and uninstall in Mazda Settings.

**V74 release qualification is in progress.**
Current source targets exactly **74.00.324A North America / cmu150_NA**.
See [Quick start](docs/usb-installer.md) for installation and availability, or
[Build and test the installer](docs/installer-development.md) for development.

## Start here

**[Read the documentation](https://aeharding.github.io/open-connect/)** — bench
wiring, development guides and CMU reverse engineering.

- **Build a bench:** [power, display and UART wiring](docs/bench-setup.md).
- **Use a connected bench:** [CLI commands](docs/cli.md).
- **Build the USB installer:** `make release`; no Python or `oc` is required.
- **Choose your preferences:** [Open Connect settings](docs/settings.md).
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
Exact firmware checks use private OEM inputs and report explicit skips without them.

## Where things live

| Path | Purpose |
| --- | --- |
| [tooling/open_connect/](tooling/open_connect/) | Host bench CLI, capture and file validation |
| [cmu/](cmu/) | Code and templates that run on the CMU |
| [tests/](tests/) | Maintained host, shell and build checks |
| [Makefile](Makefile) | Standard native build and USB packaging, without Python or OEM inputs |
| [docs/](docs/index.md) | User guides, development instructions and CMU research |

Installing the Python package installs host tools only. The USB release builds
without OEM inputs; optional private checks validate its composition against
originals. OEM-containing outputs stay under ignored runs/.

[Contributing](CONTRIBUTING.md) · [Roadmap](PLAN.md) · [Working agreement](STEERING.md)

## License

Original code is **AGPL-3.0-or-later** ([LICENSE](LICENSE)).
[Third-party boundaries](THIRD_PARTY.md) explain excluded comparison code.
OEM firmware, credentials and raw captures are private. Paths under ignored runs/
refer to local evidence, not files available in a fresh checkout.
