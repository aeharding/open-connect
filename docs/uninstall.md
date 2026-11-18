# Uninstall and Undo

Uninstall restores the saved pre-install startup file, including its mode and
owner, and the previous touchscreen NVRAM value. A restart unloads the selected
RAM native/JavaScript files. This restores the affected state; it is not a
factory reset or removal of every unrelated modification.

Choose **Uninstall** in Open Connect's Mazda Settings page or from a compatible
replacement USB. If relevant files changed, the installer asks before saving
that state and restoring the originals.

The single **Undo uninstall** checkpoint retains the startup bytes and metadata,
feature preferences, actual NVRAM value, and hashes of retained package/composed
files and known firmware dependencies. Those retained files are left intact.
Undo checks the post-uninstall state and retained dependencies again. If they
changed later, it stops without overwriting or merging them.

The backend records the before/after snapshots durably before changing targets.
After interruption it reconciles each target against those two states. An
unknown third state is preserved. The record, originals and checkpoint remain
on the CMU, so the original USB stick is not required.

This applies to the supported firmware and compatible installer format. It does
not promise arbitrary old-USB compatibility or recovery of unrelated files.
See the [USB guide](usb-installer.md) for current qualification limits.
