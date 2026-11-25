# Uninstall

Remove Open Connect from Mazda Settings. You don’t need a USB drive or computer.

**Impact:** Neutral — restores the configuration saved before installation; no startup or RAM improvement is promised.<br>
**Trade-off:** Removes Open Connect and its saved choices. Use USB to install it again.<br>
**Evidence:** Earlier builds have removal and restoration bench checks. [Performance evidence](performance.md) does not measure an isolated uninstall speed or RAM benefit.

## Remove from Settings

1. Open **<span class="oc-nav-path" data-walkthrough="uninstall">Mazda Settings → System → Open Connect</span>**.
2. Scroll to **Uninstall**, select it and confirm **Uninstall**.
3. Keep the car on while Mazda Connect restores the saved configuration and restarts.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/uninstall.png" alt="Uninstall Open Connect? Open Connect will be removed. Mazda Connect will restart. Cancel and Uninstall buttons." width="800" height="480"></div>
  <figcaption>Confirm Uninstall to remove Open Connect.</figcaption>
</figure>

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/restarting.png" alt="Restarting Mazda Connect with a progress meter and Do not turn off the car." width="800" height="480"></div>
  <figcaption>Leave power on until the restart finishes.</figcaption>
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

These steps describe the **0.3.0-dev.19** preview for North American version **74.00.324**. Removal has bench checks; real-car qualification remains. No public download is available yet.
