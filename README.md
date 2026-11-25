# Mazda Open Connect

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/wordmark-dark.svg">
  <img alt="Mazda Open Connect screen mark and wordmark" src="docs/assets/brand/wordmark-light.svg" width="560">
</picture>

Make your Mazda infotainment screen faster, more capable, and customizable.

Plug-and-play USB install.

**0.3.0-dev.19 is a development prerelease.** Real-car qualification remains pending. Startup gains vary by configuration; faster startup than stock is not established.

[Owner guide](https://aeharding.github.io/open-connect/) · [Quick start](docs/usb-installer.md) · [Settings](docs/settings.md) · [Uninstall](docs/uninstall.md)

## Compatibility

For the original **Mazda Connect / MZD Connect** with the **7-inch screen and commander knob**. Depending on year and trim, this includes Mazda3, Mazda6, CX-3, CX-5, CX-9 and MX-5 Miata.

Only North American version **74.00.324** is supported by the current preview. Check **Settings → System → About → Version Information**: **OS Version** must read **74.00.324 NA N**. Don’t rely on model year alone.

## Features

| Feature | Choice | Fresh-install default |
| --- | --- | --- |
| [Touchscreen While Driving](docs/touchscreen.md) | Keep touch available while moving. | Allow |
| [Startup disclaimer](docs/disclaimer.md) | Skip the startup warning. | Skip |
| [Startup optimizations](docs/services.md#base-optimizations) | Reduce background logging and unused services. | Off |
| CarPlay & Android Auto | [Wireless CarPlay](docs/wireless-carplay.md), [Show CarPlay on connection](docs/carplay-on-connection.md) and [Android Auto](docs/services.md#android-auto). | Wireless off unless factory enabled; Show CarPlay on connection set to Factory; Android Auto on |
| [Audio sources](docs/services.md#audio-sources) | Choose DVD, Pandora and SiriusXM. | DVD off; Pandora and SiriusXM on |
| [Developer options](docs/developer-options.md) | UART, SSH and Import public key for your own access. | UART and SSH off |
| [Uninstall](docs/uninstall.md) | Restore your saved pre-install configuration. | — |
| [About](docs/about.md) | See the installed version. | — |

Use **Mazda Settings → System → Open Connect**. Changes apply on the next full startup. Uninstall restores your saved pre-install configuration.

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
