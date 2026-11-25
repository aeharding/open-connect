# Mazda Open Connect

<p class="oc-intro">Make your Mazda infotainment screen faster, more capable, and customizable.</p>

Plug-and-play USB install.

[Start here](usb-installer.md){ .md-button .md-button--primary }
[Browse settings →](settings.md)
{ .oc-actions }

<p class="oc-availability">Still in testing. No public download yet, and no real-car installations have been validated. Currently for North American version <strong>74.00.324</strong> only. Startup gains vary by configuration; faster startup than stock is not established.</p>

<figure class="oc-screen oc-screen--lead">
  <div class="oc-screen-frame"><img src="assets/guide/settings.png" alt="Open Connect settings showing Touchscreen While Driving, Startup disclaimer, Wireless CarPlay, Services and Developer options." width="800" height="480"></div>
  <figcaption><span class="oc-nav-path" data-walkthrough="open-connect">Settings → System → Open Connect</span> (0.3.0-dev.17).</figcaption>
</figure>

## Features

- **[Touchscreen while moving](touchscreen.md)**: keep touch available for a passenger.
- **[Skip the startup warning](disclaimer.md)**: continue to your usual screen.
- **[Wireless CarPlay](wireless-carplay.md)**: connect your iPhone without a USB cable on compatible hardware.
- **[Startup and services](services.md)**: reduce background startup work and turn off unused integrations.
- **[Built-in uninstall](uninstall.md)**: restore the configuration saved before installation.

## Supported cars

Open Connect is for the original **Mazda Connect / MZD Connect** with the **7-inch screen and commander knob**. These North American model years use that system; second-generation Mazda Connect with an 8.8-inch or 10.25-inch screen is excluded.

| Model | Model years |
| --- | --- |
| Mazda3 | 2014–2018 |
| Mazda6 | 2016–2021 |
| MX-5 Miata | 2016–2023 (ND1/ND2; 2024+ uses second-generation Mazda Connect) |
| CX-3 | 2016–2021 (later in Canada/Mexico) |
| CX-5 | 2016–2020 (2021+ US uses 10.25-inch second-generation Mazda Connect) |
| CX-9 | 2016–2020 (2021+ US uses 10.25-inch second-generation Mazda Connect) |

Some Canadian/Mexican trims and sister models (Mazda2, Toyota Yaris iA / Scion iA) also use this system — always check your screen for exact **OS Version 74.00.324 NA N** in [Quick start](usb-installer.md#1-check-your-firmware-version).

The model name alone isn’t enough. Check **<span class="oc-nav-path" data-walkthrough="version-info">Settings → System → About → Version Information</span>**. **OS Version** must read **74.00.324 NA N**. Other versions and regions are unsupported.

<span id="building-open-connect"></span>

## Open source

Open Connect is built by contributors and licensed under AGPL-3.0-or-later. Code, issues and discussions live on [GitHub](https://github.com/aeharding/open-connect). Start with [Development](development.md) to contribute.
