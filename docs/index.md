# Mazda Open Connect

<p class="oc-intro">Make your Mazda infotainment screen faster, more capable, and customizable.</p>

Plug-and-play USB install.

[Quick start](usb-installer.md){ .md-button .md-button--primary }
[Browse settings →](settings.md)
{ .oc-actions }

<p class="oc-availability"><strong>0.3.0-dev.26</strong> is a development prerelease for North American Mazda Connect <strong>74.00.324</strong> only. Real-car qualification remains pending, and startup speed varies by setting.</p>

<figure class="oc-screen oc-screen--lead">
  <div class="oc-screen-frame"><img src="assets/guide/setting-touchscreen.png" alt="Open Connect settings showing Touchscreen set to Always enabled, Startup disclaimer, Startup optimizations, CarPlay and Android Auto, and Audio sources." width="800" height="480"></div>
  <figcaption><span class="oc-nav-path" data-walkthrough="open-connect">Settings → System → Open Connect</span></figcaption>
</figure>

## Features

- **[Touchscreen](touchscreen.md)**: keep touch enabled while moving, use Mazda’s default lockout, or choose **Always disabled** (see [Touchscreen](touchscreen.md) for current bench coverage and limits).
- **[Startup disclaimer](disclaimer.md)**: skip Mazda’s startup warning and go straight to your usual screen.
- **[Startup optimizations](startup-optimizations.md)**: reduce background logging and stop unused services, including DVD on North American units.
- **CarPlay & Android Auto**: [Wireless CarPlay](wireless-carplay.md), [Show CarPlay on connection](carplay-on-connection.md) and [Android Auto](android-auto.md).
- **Audio sources**: toggle built-in [Pandora](pandora.md) and [SiriusXM](siriusxm.md).
- **[Developer options](developer-options.md)**: UART, SSH and public-key import for direct access.
- **[Apply changes](apply-changes.md)**: restart Mazda Connect to activate saved choices.
- **[Uninstall](uninstall.md)**: restore your saved pre-install configuration.
- **[About](about.md)**: check the installed Open Connect version.

## Supported cars

Open Connect is for first-generation **Mazda Connect / MZD Connect** (commander knob). First-generation Mazda Connect was available on equipped trims in these North American model years; second-generation Mazda Connect is not supported.

| Model | Model years |
| --- | --- |
| Mazda3 | 2014–2018 |
| Mazda6 | 2016–2021 |
| MX-5 Miata | 2016–2023 (ND1/ND2; 2024+ uses second-generation Mazda Connect) |
| CX-3 | 2016–2021 (later in Canada/Mexico) |
| CX-5 | 2016–2020 (2021+ US uses 10.25-inch second-generation Mazda Connect) |
| CX-9 | 2016–2020 (2021+ US uses 10.25-inch second-generation Mazda Connect) |

Some Canadian/Mexican trims and sister models (Mazda2, Toyota Yaris iA / Scion iA) also shipped with first-generation Mazda Connect.

Model year and trim alone aren’t enough. Check **<span class="oc-nav-path" data-walkthrough="version-info">Settings → System → About → Version Information</span>** (see [Quick start](usb-installer.md#1-check-your-firmware-version)). **OS Version** must read **74.00.324 NA N**; other versions and regions are unsupported.

<span id="building-open-connect"></span>

## Open source

Open Connect is built by contributors and licensed under AGPL-3.0-or-later. Code, issues and discussions live on [GitHub](https://github.com/aeharding/open-connect). Start with [Development](development.md) to contribute.
