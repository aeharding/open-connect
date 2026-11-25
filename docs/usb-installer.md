# Quick start

Install Open Connect directly from a FAT32 USB drive — no laptop, serial cable, or network connection required. Once installed, every setting and Uninstall live inside **Mazda Settings**.

<div class="oc-status-strip">
  <span class="oc-status-pill">Pre-release · 74.00.324A NA</span>
  <span>Targets exact firmware <strong>74.00.324A North America (cmu150_NA)</strong>. A qualified release download is not published yet; screenshots show <code>0.3.0-dev.17</code> on the bench. <a href="installer-development/">Current limits →</a></span>
</div>

<ol class="oc-install-flow" aria-label="Installation overview">
  <li>
    <img src="assets/guide/prepare-usb.svg" alt="" width="160" height="112">
    <strong><span>1</span> Prepare the USB</strong>
    <p>Extract every file directly onto a FAT32 drive.</p>
  </li>
  <li>
    <img src="assets/guide/insert-usb.svg" alt="" width="160" height="112">
    <strong><span>2</span> Insert the USB</strong>
    <p>Wait for Mazda Connect’s main screen, then plug in the drive.</p>
  </li>
  <li>
    <img src="assets/guide/install-restart.svg" alt="" width="160" height="112">
    <strong><span>3</span> Install &amp; restart</strong>
    <p>Choose Install and leave power and USB connected until completion appears.</p>
  </li>
</ol>

## 1. Prepare the USB drive

Format a USB drive as **FAT32**. Extract the release ZIP and copy **all of its contents** directly to the top level of the drive (not inside an extra folder).

You should see the `open-connect` folder alongside **two small files** — keep their exact names, including the `.up` file. Copy the extracted files rather than the ZIP itself, then safely eject the drive.

## 2. Choose Install

Wait until **Mazda Connect’s main screen** is visible, then plug in the USB drive. Choose **Install** when the prompt appears.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/install.png" alt="Install Open Connect? Version 0.3.0-dev.17, with Cancel and Install buttons." width="800" height="480"></div>
  <figcaption>Confirm Install while Mazda Connect’s main screen is showing.</figcaption>
</figure>

**Keep the USB drive plugged in and the car turned on** while Open Connect applies the installation and automatically restarts Mazda Connect.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/installing.png" alt="Installing Open Connect, with Mazda’s animated meter and a warning to keep the USB drive connected and car on." width="800" height="480" loading="lazy"></div>
  <figcaption>Mazda’s native progress screen stays up while changes are applied and the system restarts.</figcaption>
</figure>

## 3. Finish

After the restart, wait for **Open Connect installed**, then choose **Done** or **Open settings**. You can now safely remove the USB drive — Open Connect remains installed for future starts.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/complete.png" alt="Open Connect installed. Version 0.3.0-dev.17, with Done and Open settings buttons." width="800" height="480" loading="lazy"></div>
  <figcaption>Installation is complete — remove the USB drive and open Settings to customize features.</figcaption>
</figure>

[Explore Settings →](settings.md) · [Uninstall →](uninstall.md)

## Updating or reinstalling

Prepare a FAT32 USB drive with the release you want and insert it on Mazda Connect’s main screen. The prompt shows **From** (installed version) and **To** (USB version). Choose **Update**, or **Reinstall** if both versions match. All of your Open Connect preferences are preserved automatically.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/update.png" alt="Update Open Connect? From 0.3.0-dev.16 to 0.3.0-dev.17, with Cancel, Update and Uninstall buttons." width="800" height="480" loading="lazy"></div>
  <figcaption>Verify the installed and target versions before choosing Update or Reinstall.</figcaption>
</figure>

## Existing modifications

Open Connect requires the exact supported OEM files on `74.00.324A NA`. If another mod changed files Open Connect relies on, installation stops safely instead of overwriting them. Remove existing mods (such as legacy wireless CarPlay mods) first, or include your installed mods when [reporting an issue](https://github.com/aeharding/open-connect/issues).

## No prompt?

Double-check that:

- Mazda Connect is showing its main screen,
- The USB drive is formatted as **FAT32**,
- The `open-connect` folder and both companion files are directly in the root of the drive, and
- Your firmware is exact **`74.00.324A` North America**.

Reinsert the drive. If the prompt still doesn’t appear, [open an issue](https://github.com/aeharding/open-connect/issues) with your firmware version and what appeared on screen.
