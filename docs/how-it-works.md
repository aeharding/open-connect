<span id="how-open-connect-works"></span>

# How it works

Open Connect adds preferences to Mazda’s own Settings. Your normal menus and controls stay in place.

<span id="original-files-selected-copies"></span>
<span id="shared-files-need-shared-rules"></span>

## Installation

The USB installer checks the supported version and saves the original configuration before making changes. It stops if another modification has changed files it needs.

Your choices stay saved after removing the USB drive and across normal restarts.

<span id="a-bounded-startup-fallback"></span>
<span id="prepare-ahead-of-startup"></span>

## Startup

Open Connect checks your saved choices, then applies them as Mazda Connect starts. Most changed app and service files are temporary copies in memory; the originals stay on storage.

If repeated unexpected restarts exhaust its three-attempt allowance, Open Connect falls back to Mazda’s normal startup. Your choices are kept. A normal start after a sustained ignition-off shutdown renews that allowance.

Startup and memory overhead remain under development. Bench improvements do not establish a faster start than stock. Measurements are in [Performance evidence](performance.md).

## Removal

[Uninstall](uninstall.md) restores the configuration saved before installation and removes Open Connect’s files and backups. It leaves normal Mazda preferences and phone pairings alone.

This restores the state found before installation. It is not a factory reset.

The **0.3.0-dev.23 development prerelease** is for North American version **74.00.324**. Real-car qualification remains pending.
