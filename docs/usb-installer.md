# Quick start

Install Open Connect from a USB drive. It adds two choices to Mazda Settings:
touchscreen access while moving and whether to show the startup disclaimer.

> **V74 development target · qualification in progress**
>
> Current source targets exactly **74.00.324A North America / cmu150_NA**.
> A qualified v74 download is not published yet. See
> [development and qualification](installer-development.md) for current limits.

Earlier v55 development downloads remain in the
[release archive](https://github.com/aeharding/open-connect/releases).
The screenshots show the **0.3.0-dev.1 v74 development build**. Release
qualification remains in progress.

<ol class="oc-install-flow" aria-label="Installation overview">
  <li>
    <img src="assets/guide/prepare-usb.svg" alt="" width="160" height="112">
    <strong><span>1</span> Prepare the USB</strong>
    <p>Extract every file onto a FAT32 drive.</p>
  </li>
  <li>
    <img src="assets/guide/insert-usb.svg" alt="" width="160" height="112">
    <strong><span>2</span> Insert the USB</strong>
    <p>Wait for Mazda Connect’s main screen, then insert the drive.</p>
  </li>
  <li>
    <img src="assets/guide/install-restart.svg" alt="" width="160" height="112">
    <strong><span>3</span> Install and restart</strong>
    <p>Choose Install. Keep the USB connected and the car on until installation is complete.</p>
  </li>
</ol>

## 1. Prepare the USB drive

Use a drive formatted as **FAT32**. Extract the downloaded ZIP and copy **all of
its contents** directly onto the drive, outside any extra folder.

The drive should contain the `open-connect` folder and **two small files beside
it**. Keep their original names, including the unusually named `.up` file.
Copy the extracted files, not the ZIP itself. Safely eject the drive.

## 2. Choose Install

Wait for **Mazda Connect's main screen**, then insert the USB drive.
Choose **Install** when the prompt appears.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/install.png" alt="Install Open Connect 0.3.0-dev.1? Cancel and Install buttons on the Mazda Connect main screen." width="800" height="480"></div>
  <figcaption>Choose Install. Keep the USB connected and the car on.</figcaption>
</figure>

**Do not remove the USB drive or turn off the car** during installation or the
automatic restart. Wait for the **Installation complete** message.

## 3. Finish

After the restart, wait for **Installation complete**, then choose **Done** or
**Open settings**. You can now remove the USB drive. Open Connect stays installed
for future starts.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/complete.png" alt="Open Connect 0.3.0-dev.1 installed. Installation complete, with Done and Open settings buttons." width="800" height="480" loading="lazy"></div>
  <figcaption>You can now remove the USB drive. Choose Open settings to change your preferences.</figcaption>
</figure>

[Change your settings →](settings.md) · [Uninstall →](uninstall.md)

## Updating an existing installation

Prepare a USB drive from the new release in the same way. Insert it while
Mazda Connect shows its main screen and choose **Install/update**.
Your Open Connect preferences are kept.

## Existing modifications

Other mods can change files this release needs. Installation refuses conflicting
files rather than overwriting them. If it stops, include your existing mods when
[reporting the problem](https://github.com/aeharding/open-connect/issues).

## No prompt?

Check that Mazda Connect shows its main screen, the drive is FAT32, and the
extracted folder and two files are directly on the drive. Check the firmware
limit above, then reinsert the drive. If it still does not open,
[report the problem](https://github.com/aeharding/open-connect/issues) with your
firmware version and what appeared on screen.
