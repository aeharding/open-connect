# USB installer

The development prerelease supports **55.00.750B NA (cmu150_NA)** only. It installs
always-enabled touchscreen input and the startup disclaimer bypass, with
preferences in Mazda Settings. Other firmware, including v74, is unsupported.

## Install or update

1. Download the USB ZIP and `SHA256SUMS` from the matching
   [GitHub release](https://github.com/aeharding/open-connect/releases).
2. Extract the ZIP into the root of a FAT32 USB drive. Keep the two trigger files
   beside the `open-connect` folder. Preserve the unusually named `.up` file.
3. With Mazda Connect at Home, insert the drive and choose **Install** or
   **Install/update**. Leave power on while the operation finishes.
4. Mazda Connect restarts. Choose **Done** or **Open settings**. The USB drive can
   then be removed; the installed features persist across ignition cycles.

The head unit runs the complete installer locally. No computer, SSH, internet
connection, Python or `oc` command is involved. Running Install/update again uses
saved originals and retains your Open Connect preferences.

## Preferences and removal

Find **Open Connect** in the System tab of Mazda Settings. Each preference has a
separate radio-choice page. The choice updates immediately; its behavior takes
effect after restarting Mazda Connect.

Choose **Uninstall** there or from a compatible replacement USB. It restores the
saved startup file and pre-install touchscreen setting, then restarts. Saved
originals and one uninstall checkpoint remain for **Undo uninstall** from USB.
See [uninstall and conflicts](uninstall.md).

After an interruption, reinsert a compatible USB. The backend reconciles the
prepared operation with actual files and settings before continuing. An
unconfirmed response does not cause the UI to repeat a write automatically.

## Startup recovery

A durable attempt budget limits repeated boots of the disclaimer bypass. A
sustained ACC-off transition followed by a different kernel boot can renew it.
Reaching Home, quick ACC resume and repeated software resets do not renew it.

When attempts run out, startup uses Mazda's original native/JavaScript path and
restores the saved touchscreen setting. The display service reads that setting
before our hook, so its restored value takes effect on the **next boot**. Recovery
does not force an additional restart or erase your feature preferences.

This is a finite retry policy, not a diagnosis of which component caused a reset.
A battery interruption or unrelated firmware fault can consume an attempt.

## Development and qualification

Build with Clang, LLD, llvm-objcopy, OpenSSL and zip:

```sh
make release OUT=runs/my-release
```

The output is `open-connect-<version>-usb.zip` plus `SHA256SUMS`. CI uploads the
same files as `fw55-usb-installer`. A `v<version>` development tag matching
`cmu/installer/VERSION` on reviewed main history prepares a draft prerelease after
host checks. Publish it after qualifying that CI artifact on the bench.
Build scripts copy authored files and compile native assets; OEM
files are read and composed privately on the CMU.

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
