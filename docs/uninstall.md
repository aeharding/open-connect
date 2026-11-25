# Uninstall

Remove Open Connect from Mazda Settings. You don’t need a USB drive or computer.

**<span class="oc-nav-path" data-walkthrough="uninstall">Mazda Settings → System → Open Connect → Uninstall</span>**

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-uninstall.png" alt="Uninstall highlighted in the Open Connect menu, between Developer options and About." width="800" height="480"></div>
  <figcaption>Uninstall highlighted (dev.19).</figcaption>
</figure>

- **Default**: No preference; removal requires confirmation.
- **Startup & RAM impact**: **Neutral** — restores the saved pre-install configuration; no isolated startup or RAM improvement is measured.
- **Trade-offs & boot implications**: Removes Open Connect, its backups and saved choices. Install again using USB; radio presets, phone pairings and other normal Mazda preferences remain.
- **Applies**: Confirming **Uninstall** starts removal and an automatic Mazda Connect restart. Keep the car on until it finishes.
- **Evidence & limits**: Dev.19 Settings Uninstall has bench verification on **74.00.324A NA**; real-car removal remains unqualified. [Performance evidence](performance.md) does not measure an isolated uninstall benefit. No public download is available.

## Remove from Settings

1. Select **Uninstall** and confirm **Uninstall**.
2. Keep the car on while Mazda Connect restores the saved configuration and restarts.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/restarting.png" alt="Restarting Mazda Connect with a progress meter and Do not turn off the car." width="800" height="480"></div>
  <figcaption>Leave power on until the restart finishes (retained dev.17 capture).</figcaption>
</figure>

Uninstall restores the startup, touchscreen and access configuration saved before installation. It then removes Open Connect’s files and backups. Radio presets, phone pairings and other normal Mazda preferences are left alone.

If another modification changed files Open Connect needs to restore, removal stops rather than overwriting them. Keep the message for an [issue report](https://github.com/aeharding/open-connect/issues).

<span id="remove-it-using-usb"></span>

## Remove using USB

If Settings is unavailable, [prepare a USB drive](usb-installer.md) with a compatible bundle. Insert it on Mazda Connect’s main screen and choose **Uninstall**. Keep the drive connected and the car on until restart finishes.

A compatible replacement drive works. You don’t need the original stick.

<span id="install-it-again"></span>

## Install again

Use USB and choose **Install**. A new installation starts with default preferences.

[Back to Settings](settings.md)
