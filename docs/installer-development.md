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

If relevant files or settings changed, uninstall stops without overwriting them.
There is no conflict-confirmation override or Undo uninstall operation. Installing
again from USB starts a fresh installation with default Open Connect preferences.

The backend records before/after snapshots durably before changing targets.
After interruption, reinserting a compatible USB lets it reconcile each target
against those states. An unknown third state is preserved. An unconfirmed response
does not cause the UI to repeat a write automatically.

Startup publication uses one staging path named by the pending record revision.
Recovery accepts a partial copy only when its bytes match the planned prefix;
handled failures remove the owned stage and restore root read-only. Unknown
staging files from older releases are preserved and block complete removal.

After restoration is verified and flushed, the record enters `purge`. The backend
runs from RAM and removes the persistent packages, composed files, originals and
snapshots. It deletes the record last, then the empty state directory, flushing
the directory changes. Loaded RAM files remain intact until restart.

A compatible USB resumes an interrupted purge without requiring already-deleted
snapshots. It also handles a cut between deleting the record and removing the
empty directory. No Open Connect files or backups remain on persistent storage
after successful uninstall. The original USB is not required.

The new USB can finish removal of v0.2.0-dev.1's retained state by choosing
Uninstall. It accepts that release's record layout and keeps an always-false
legacy `undo` response field during service handoff; no Undo command is accepted.
An old pending conflicted uninstall is refused because it promised to preserve
the conflicting edits. Fresh and pending removal also check that the saved
startup and touchscreen state belong to Open Connect; a legacy Undo could have
adopted someone else's edits into its current snapshot. Recovery preserves those
edits even if some targets have already been restored. Arbitrary old-package
compatibility remains unqualified.

## Qualification

The development prerelease supports exactly **55.00.750B NA / cmu150_NA**.
The v0.2.0-dev.1 bench qualification covered its actual CI bundle and these behaviors:

- Fresh install, reinstall with preferences retained, restart, completion and
  native Settings; uninstall from the installed backend after USB removal.
- Full ignition shutdown/startup, quick resume, software resets and an exhausted
  attempt budget followed by a fault after Home.
- Recovery after one controlled power cut with a prepared preference transaction.
- Conflicted uninstall, exact Undo and refusal after a later edit; original
  startup, NVRAM and native mappings verified after removal, with root read-only.

Those Undo/conflict results describe the earlier prerelease. For v0.2.0-dev.2,
the [CI bundle from source 2f30ead](https://github.com/aeharding/open-connect/actions/runs/44350948917)
installed from empty product state, restarted into both selected features, and
opened completion and native Settings. After removing the USB files and detaching
the drive, Settings Uninstall restored the saved startup/metadata and NVRAM,
deleted the product directory, and restarted into original native/JavaScript
paths with root read-only. No startup staging or product runtime remained.

Legacy retained-state cleanup also passed on an earlier candidate. Host tests
cover interrupted deletion, conflicting edits adopted by legacy Undo, and
publication failures under BusyBox ash. The final CI suite passed 172 tests with
seven private-input skips. The [BusyBox findings](reverse-engineering.md#complete-uninstall-and-busybox-publication)
record the failed first candidate, independent restoration and corrected trial.

See the [firmware-scoped evidence](reverse-engineering.md#standalone-installer-backend).
These are bounded bench checks, not long-term vehicle reliability qualification.
The outgoing CMU has unreliable touch hardware. Physical touch/motion behavior,
broader last-app/display-off cases and the modern-firmware port remain before a
normal owner release. Power loss at arbitrary storage-write points is also
unqualified; the host suite covers additional injected failures.
