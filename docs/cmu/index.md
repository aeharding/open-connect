# Understand the Mazda CMU

The CMU is the infotainment computer behind first-generation Mazda Connect.
Our maintained findings cover **74.00.324A North America / cmu150_NA**. They
trace startup policy through native services to the screen, so a change reaches
the component that owns the behavior. They are engineering findings, not a
complete firmware specification.

## Software layers

| Layer | Role in the paths we have traced | Evidence |
| --- | --- | --- |
| Linux and vendor startup | Mount filesystems, select the board's service configuration and launch services | [Exact firmware integration](firmware74.md#startup-selection) |
| Native MMUI and system UIA | Choose application contexts, focus and startup continuation | [Native call sites and renderer cleanup](../reverse-engineering.md#v74-installer-port-and-native-code-placement) |
| Opera and the GUI framework | Render Mazda templates and run transition callbacks | [Renderer lifecycle](firmware74.md#renderer-settings-and-touch) |
| LVDS service and CarPlay | Apply distinct physical-touch and projection restrictions | [Touch and CarPlay findings](../reverse-engineering.md#touch-input-and-carplay-on-v74) |
| Login scripts and SSH server | Authenticate console and network sessions | [Developer access and file lifetime](../reverse-engineering.md#developer-access-and-login-script-lifetime-on-v74) |

## Questions the research answers

- [Which exact source bytes and integration points does Open Connect require?](firmware74.md)
- [Why does restoring a file require keeping its original inode alive?](../reverse-engineering.md#why-the-original-login-needs-a-hardlink)
- [How do USB launch, SD bench storage and wired CarPlay coexist?](../reverse-engineering.md#v74-usb-launch-and-sd-bench-storage)
- [How does Mazda select wireless CarPlay and Wi-Fi modes?](wireless-carplay.md)
- [What does Mazda Factory Reset delete?](factory-reset.md)

The [architecture discussion](../extension-architecture.md) distinguishes the
current installer from proposed plugin composition. A proposed guarantee is
not observed Mazda behavior.

## Limits

The [qualification record](../installer-development.md#qualification) identifies
the CI artifacts used for install, startup, recovery, Settings and uninstall.
These bounded single-unit bench checks do not establish long-term vehicle
reliability, every power-loss boundary or support for another firmware.
Physical-input and first-car checks remain deferred.

The silent bench fixture has no tuner/amplifier unit (TAU). It can exercise some
Entertainment screens without establishing working audio playback.

## Contribute a finding

Record the firmware and component, the question, the observed behavior or exact
source basis, and what remains untested. Summarize relevant source rather than
uploading full OEM files. [Documentation guidance](../documentation.md) explains
where to put the result and how to preview it.
