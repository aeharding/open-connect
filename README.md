<p align="center">
  <a href="https://aeharding.github.io/open-connect/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/wordmark-dark.svg">
      <source media="(prefers-color-scheme: light)" srcset="docs/assets/brand/wordmark-light.svg">
      <img alt="Mazda Open Connect — Factory-feel improvements for first-generation Mazda Connect" src="docs/assets/brand/wordmark-light.svg" width="560">
    </picture>
  </a>
</p>

<p align="center">
  <strong>Make Mazda Connect feel factory-original, start faster, and stay easy to maintain — with optional improvements you can install from USB and undo anytime.</strong>
</p>

<p align="center">
  <a href="https://aeharding.github.io/open-connect/">Documentation</a> ·
  <a href="https://aeharding.github.io/open-connect/usb-installer/">Quick start</a> ·
  <a href="https://aeharding.github.io/open-connect/settings/">Settings</a> ·
  <a href="https://aeharding.github.io/open-connect/features/">Features</a> ·
  <a href="https://aeharding.github.io/open-connect/performance/">Benchmarks</a>
</p>

---

> **Current target: `74.00.324A` North America (`cmu150_NA`) · Pre-release qualification in progress.**
> A qualified v74 download is not published yet — real-car and physical-input checks are still ahead. See [Quick start](docs/usb-installer.md) and [installer development](docs/installer-development.md) for current status and limits.

## What Open Connect does

Every control lives natively inside **Mazda Settings → System → Open Connect**. No custom launcher, no replacement dashboard, and no computer needed once installed.

| Feature | What it solves | Default |
| --- | --- | --- |
| [**Touchscreen While Driving**](docs/touchscreen.md) | Removes Mazda's ~5 mph speed lock so passengers can still use touch controls | Allow |
| [**Startup disclaimer**](docs/disclaimer.md) | Skips the repetitive legal warning on every start while keeping normal startup behavior | Skip |
| [**Wireless CarPlay**](docs/wireless-carplay.md) | Enables Mazda's own native wireless CarPlay menus without spoofing vehicle identity | Off |
| [**Services & Base optimizations**](docs/services.md) | Cuts verbose logging and dead/unused services (DAB, TV, Stitcher, Aha, DVD, Pandora, Android Auto, SiriusXM) to reduce boot load and free RAM | Base Off · DVD Off · others On |
| [**Developer options**](docs/developer-options.md) | Optional passwordless UART root shell and key-based SSH over USB-Ethernet for contributors | Both Off |
| [**Clean Uninstall**](docs/uninstall.md) | Restores your saved pre-install files and settings from Settings or any compatible USB, then deletes Open Connect | Built in |

---

## Developing & contributing

Build the standalone USB installer directly with Clang, LLD, `llvm-objcopy`, OpenSSL, and `zip` — no Python or OEM files required:

```sh
make release OUT=runs/my-release
```

Set up the optional Python environment for host tests and bench tooling:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python tests/run_offline.py
```

Offline tests never connect to or modify a CMU. Exact-firmware checks use private OEM inputs and report explicit skips without them.

| Path | Purpose |
| --- | --- |
| [cmu/](cmu/) | Target code, native adapters, and Mazda UI integration |
| [tooling/open_connect/](tooling/open_connect/) | Host bench CLI (`oc`), capture, and validation helpers |
| [tests/](tests/) | Host unit, Node/ES5 UI, shell, and build checks |
| [Makefile](Makefile) | Native ARM build and USB bundle packaging |
| [docs/](docs/index.md) | Owner guide, performance evidence, bench setup, and CMU research |

- **Start contributing:** [Development guide](docs/development.md) · [Wire a bench](docs/bench-setup.md) · [CLI reference](docs/cli.md)
- **Understand the CMU:** [CMU research](docs/cmu/index.md) · [Reverse-engineering findings](docs/reverse-engineering.md)
- **Project direction:** [Roadmap](PLAN.md) · [Working agreement](STEERING.md) · [Contributing](CONTRIBUTING.md) · [Issues](https://github.com/aeharding/open-connect/issues)

## License

Original code is **AGPL-3.0-or-later** ([LICENSE](LICENSE)). See [THIRD_PARTY.md](THIRD_PARTY.md) for third-party boundaries. OEM firmware, credentials, and raw captures are never published in this repository.
