# Mazda Open Connect

<p class="oc-intro">Make your Mazda infotainment screen faster, more capable, and customizable.</p>

Plug-and-play USB install.

[Quick start](usb-installer.md){ .md-button .md-button--primary }
[Browse settings →](settings.md)
{ .oc-actions }

<p class="oc-availability">Still in testing. No public download yet, and no real-car installations have been validated. Currently for North American version <strong>74.00.324</strong> only. Startup gains vary by configuration; faster startup than stock is not established.</p>

<figure class="oc-screen oc-screen--lead">
  <div class="oc-screen-frame"><img src="assets/guide/settings-entry.png" alt="Mazda Settings System tab with Open Connect above About." width="800" height="480"></div>
  <figcaption><span class="oc-nav-path" data-walkthrough="open-connect">Settings → System → Open Connect</span> — scroll down to Open Connect.</figcaption>
</figure>

## Features

- **[Touchscreen While Driving](touchscreen.md)**: keep touch available for a passenger.
- **[Startup disclaimer](disclaimer.md)**: continue to your usual screen.
- **[Startup optimizations](services.md#base-optimizations)**: reduce background logging and unused services.
- **CarPlay & Android Auto**: [wireless connections](wireless-carplay.md), [Show CarPlay on connection](carplay-on-connection.md) and [Android Auto](services.md#android-auto).
- **[Audio sources](services.md#audio-sources)**: choose DVD, Pandora and SiriusXM.
- **[Developer options](developer-options.md)**: UART, SSH and Import public key for your own access.
- **[Uninstall](uninstall.md)**: restore the configuration saved before installation.
- **[About](about.md)**: check the installed version.

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

Some Canadian/Mexican trims and sister models (Mazda2, Toyota Yaris iA / Scion iA) were also offered with first-generation Mazda Connect.

Model year and trim alone aren’t enough. Check **<span class="oc-nav-path" data-walkthrough="version-info">Settings → System → About → Version Information</span>** (see [Quick start](usb-installer.md#1-check-your-firmware-version)). **OS Version** must read **74.00.324 NA N**; other versions and regions are unsupported.

<span id="building-open-connect"></span>

## Open source

Open Connect is built by contributors and licensed under AGPL-3.0-or-later. Code, issues and discussions live on [GitHub](https://github.com/aeharding/open-connect). Start with [Development](development.md) to contribute.
