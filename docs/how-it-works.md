<span id="how-open-connect-works"></span>

# How it works

Open Connect adds preferences to Mazda’s own Settings. Your normal menus and controls stay in place.

<span id="original-files-selected-copies"></span>
<span id="shared-files-need-shared-rules"></span>

## Installation

The USB installer checks your firmware version and saves your original configuration before making changes. It stops if another modification has changed files it needs.

Your choices stay saved after removing the USB drive and across normal restarts.

<span id="a-bounded-startup-fallback"></span>
<span id="prepare-ahead-of-startup"></span>

## Startup

Open Connect verifies your saved choices and applies them as Mazda Connect starts. Changed app and service files run from temporary copies in memory; your original files stay intact on storage.

If repeated unexpected restarts exhaust its three-attempt allowance, Open Connect falls back to Mazda’s normal startup while keeping your saved choices. A normal start after a sustained ignition-off shutdown renews that allowance.

Startup and memory measurements live in [Performance evidence](performance.md); gains vary by configuration and faster startup than stock is not guaranteed across all settings.

## Removal

[Uninstall](uninstall.md) restores the configuration saved before installation and removes Open Connect’s files and backups. It leaves normal Mazda preferences, radio presets and phone pairings alone.

This restores the state found before installation. It is not a factory reset.

**0.3.0-dev.24** is a development prerelease for North American version **74.00.324**. Real-car qualification remains pending.
