# Disclaimer bypass

Skip the startup warning and go straight to Mazda's normal home screen.
The screen may still briefly fade or go black during startup.

The [USB development prerelease](usb-installer.md) installs the bypass on exactly
**55.00.750B North America**. It persists after USB removal and includes a
preference in Mazda Settings, uninstall and bounded startup recovery. Other
firmware, including v74, is unsupported.

The separate bench workflow verifies the feature for one startup, then returns
to the previous setup. `oc` provides that development instrumentation; it is not
needed to use the USB installer.

- **Following the project?** See [GitHub Releases](https://github.com/aeharding/open-connect/releases) for updates.
- **Have a development bench?** Follow the [bench testing guide](disclaimer-development.md).

See the USB guide for installation instructions and the remaining qualification
limits before a normal owner release.
