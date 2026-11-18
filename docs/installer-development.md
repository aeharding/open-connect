# Build and test the installer

The owner instructions are in [Quick start](usb-installer.md),
[Settings](settings.md) and [Uninstall](uninstall.md). This page covers the
release build, backend behavior and qualification evidence.

## Build the USB release

Build with Clang, LLD, llvm-objcopy, OpenSSL and zip:

```sh
make release OUT=runs/my-release
```

The output is `open-connect-<version>-usb.zip` plus `SHA256SUMS`. CI uploads the
same files as `fw55-usb-installer`. A `v<version>` development tag matching
`cmu/installer/VERSION` on reviewed main history prepares a draft prerelease after
host checks. Publish it after qualifying that CI artifact on the bench.

Build scripts copy authored files and compile native assets; OEM files are read
and composed privately on the CMU. The installer and its backend run on the CMU;
`oc` remains host bench instrumentation. See [CMU code](https://github.com/aeharding/open-connect/blob/main/cmu/README.md)
for the implementation and command contract.

## Startup recovery

A durable attempt budget limits repeated boots of the disclaimer bypass. A
sustained ACC-off transition followed by a different kernel boot can renew it.
Reaching Home, quick ACC resume and repeated software resets do not renew it.

When attempts run out, startup uses Mazda's original native/JavaScript path and
restores the saved touchscreen setting. The display service reads that setting
before our hook, so its restored value takes effect on the next boot. Recovery
does not force an additional restart or erase the feature preferences.

This is a finite retry policy, not a diagnosis of which component caused a reset.
A battery interruption or unrelated firmware fault can consume an attempt.

## Uninstall and interruption handling

Uninstall restores the saved pre-install startup file, including its mode and
owner, and the previous touchscreen NVRAM value. A restart unloads the selected
RAM native/JavaScript files. Restoration covers these affected targets, not a
factory reset or removal of unrelated modifications.

If relevant files changed, the installer asks before saving that state and
restoring the originals. The single Undo checkpoint retains startup bytes and
metadata, feature preferences, the actual NVRAM value, and hashes of retained
package/composed files and known firmware dependencies. Those retained files stay
intact. Undo checks the post-uninstall state and dependencies again. Later changes
make it stop without overwriting or merging them.

The backend records before/after snapshots durably before changing targets.
After interruption, reinserting a compatible USB lets it reconcile each target
against those states. An unknown third state is preserved. An unconfirmed response
does not cause the UI to repeat a write automatically.

The record, originals and checkpoint remain on the CMU; the original USB stick is
not required. This applies to the supported firmware and compatible installer
format. Arbitrary old-USB compatibility and recovery of unrelated files are not
promised.

## Qualification

The development prerelease supports exactly **55.00.750B NA / cmu150_NA**.
Bench qualification covered the actual CI bundle and these behaviors:

- Fresh install, reinstall with preferences retained, restart, completion and
  native Settings; uninstall from the installed backend after USB removal.
- Full ignition shutdown/startup, quick resume, software resets and an exhausted
  attempt budget followed by a fault after Home.
- Recovery after one controlled power cut with a prepared preference transaction.
- Conflicted uninstall, exact Undo and refusal after a later edit; original
  startup, NVRAM and native mappings verified after removal, with root read-only.

See the [firmware-scoped evidence](reverse-engineering.md#standalone-installer-backend).
These are bounded bench checks, not long-term vehicle reliability qualification.
The outgoing CMU has unreliable touch hardware. Physical touch/motion behavior,
broader last-app/display-off cases and the modern-firmware port remain before a
normal owner release. Power loss at arbitrary storage-write points is also
unqualified; the host suite covers additional injected failures.
