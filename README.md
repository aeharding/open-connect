<h1>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/wordmark-dark.svg">
  <img alt="Mazda Open Connect" src="docs/assets/brand/wordmark-light.svg" width="560">
</picture>
</h1>

Make your Mazda Connect infotainment screen faster, more capable, and customizable. Plug-and-play USB install.

Supports North American Mazda Connect **74.00.324 NA N** (**[0.3.0-dev.26](https://github.com/aeharding/open-connect/releases/tag/v0.3.0-dev.26)** development prerelease; real-car qualification pending).

[Owner guide](https://aeharding.github.io/open-connect/) · [Quick start](https://aeharding.github.io/open-connect/usb-installer/) · [Settings](https://aeharding.github.io/open-connect/settings/) · [How it works](https://aeharding.github.io/open-connect/how-it-works/) · [Releases](https://github.com/aeharding/open-connect/releases)

## Developing

Build the USB bundle and run host tests offline (with the development environment installed):

```sh
make release OUT=runs/my-release
.venv/bin/python tests/run_offline.py
```

| Path | Purpose |
| --- | --- |
| [cmu/](cmu/) | Target code and Mazda UI integration |
| [tooling/open_connect/](tooling/open_connect/) | Host bench CLI and capture tools |
| [tests/](tests/) | Offline host checks |
| [Makefile](Makefile) | Native build and USB packaging |
| [docs/](docs/index.md) | Owner guide and research |

[Development guide](docs/development.md) · [Bench setup](docs/bench-setup.md) · [CMU research](docs/cmu/index.md) · [Contributing](CONTRIBUTING.md) · [Roadmap](PLAN.md) · [Issues](https://github.com/aeharding/open-connect/issues)

## License

Original work: **AGPL-3.0-or-later** ([LICENSE](LICENSE)); third-party boundaries: [THIRD_PARTY.md](THIRD_PARTY.md).
OEM firmware, credentials and raw captures are never published here.
