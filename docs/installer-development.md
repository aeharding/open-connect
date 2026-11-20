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
same files as `usb-installer`. A `v<version>` development tag matching
`cmu/installer/VERSION` on reviewed main history prepares a draft prerelease after
host checks. Publish it after qualifying that CI artifact on the bench.

Build scripts copy authored files and compile native assets; OEM files are read
and composed privately on the CMU. The installer and its backend run on the CMU;
`oc` remains host bench instrumentation. See [CMU code](https://github.com/aeharding/open-connect/blob/main/cmu/README.md)
for the implementation and command contract.

## Private firmware checks

The optional checker builds the same public bundle, composes it with exact
originals using the maintained shell, and validates the result on the host:

~~~sh
.venv/bin/python tests/check_firmware.py --firmware /private/firmware74 \
  --output runs/my-v74-check
~~~

The input is a private filesystem-shaped tree containing the original paths
listed by firmware_dependencies in cmu/installer/firmware.sh, plus GuiFramework.js
and lvds_service. No credentials are needed. Unknown hashes and public output
paths are refused before building; OEM-containing outputs stay under ignored runs/.
Use a fresh output directory for each run so failures and source snapshots remain.

Clang, LLD, llvm-objcopy, llvm-objdump, Node.js, OpenSSL, zip and GNU-compatible
stat/readlink are needed. Explicit tool paths can be supplied with --host-cc,
--objdump and --node; Make handles the target toolchain.

Checks preserve every original section and symbol address, validate segment
alignment and PIC relocations, and require the interception point to lie in the
ordinary event callback. They cover both MMUI XML consumers, both stock board
configurations, the real v74 BaseApp/frame-completion lifecycle and the native C wrapper with all
13 actual continuation rules. Source/input hashes and outputs are retained.
The host composition stubs durability flushes and the C contract uses fakes:
these checks do not execute ARM code, access a CMU or prove recovery.

Without explicit private inputs, the public offline suite reports a skip for
these firmware checks. The superseded v55 one-shot builder is in Git history.

## Existing modifications

Fresh installations require the exact supported OEM startup, board-detection,
service and native files on **74.00.324A NA**. Remove the existing wireless
CarPlay mod before installing Open Connect; the installer does not recognize or
adopt its modified files. Remaining conflicting edits cause refusal.

Reinstall checks the current targets and dependencies before accepting inputs.
Later edits are preserved and refused. The future Open Connect wireless-enable
option must retain actual vehicle/hardware identity and remains in the final
roadmap phase. See [wireless research](cmu/wireless-carplay.md).

The earlier compatibility allowance and its stock-bench CI trial are
[historical evidence](reverse-engineering.md#preserving-recognized-wireless-mod-inputs).
Those captures retain their actual source identity; they are not tests of this
OEM-only revision.

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

The historical v55 maintenance bundle could finish removal of v0.2.0-dev.1's
retained state by choosing Uninstall. That implementation accepted the old
record layout and kept an always-false
legacy `undo` response field during service handoff; no Undo command is accepted.
An old pending conflicted uninstall is refused because it promised to preserve
the conflicting edits. Fresh and pending removal also check that the saved
startup and touchscreen state belong to Open Connect; a legacy Undo could have
adopted someone else's edits into its current snapshot. Recovery preserves those
edits even if some targets have already been restored. Arbitrary old-package
compatibility, including cross-firmware maintenance, remains unqualified.

## Qualification

Current source targets exactly **74.00.324A NA / cmu150_NA**. The reviewed
OEM-only bundle from [CI 44798623680](https://github.com/aeharding/open-connect/actions/runs/44798623680),
source `14919e1`, passed SD-staged install, automatic restart, completion,
Open settings and normal Settings Uninstall. Both feature preferences were
selected; all 32 public entries matched the installed package and runtime.
Uninstall restored all 19 intake files/metadata, absent touch NVRAM and original
loaded native/frontend code, with root read-only and product state removed.
This was a manual bench-source launch, not a distinct replacement-USB test.
See the [OEM-only regression record](reverse-engineering.md#oem-only-bundle-regression).

The earlier reviewed
incoming-frame correction's [CI bundle](https://github.com/aeharding/open-connect/actions/runs/44716935060)
passed host-staged fresh install, reinstall with preferences retained, automatic
restart, completion, Open settings and both preference pages. Its installed
payload matched all 32 public manifest entries, plus a private installation ID.
Normal Settings Uninstall restored all 19 intake hashes/metadata, original
native/frontend paths and saved touch NVRAM, with physical root read-only and
all product files, backups and runtime state removed.

The same artifact also passed the removable-USB install/restart/completion/Open
settings flow after software reauthorization through Mazda's normal detector.
A separate owner-performed physical insertion opened the correct prompt, which
was cancelled without reinstalling. Normal Settings Uninstall worked after the
original USB was physically removed. A temporary SD mount alias also supported
the unchanged loader for bench tests while SD reads, live CarPlay and Ethernet
worked together. See [USB and SD findings](reverse-engineering.md#v74-usb-launch-and-sd-bench-storage)
for source identity, exact launch methods and limits; this is not owner SD-install
support.

The same bundle passed a prepared-preference supply interruption, three selected
software starts, quick ACC resume without budget renewal, controlled frontend-loss
fallback and sustained-ACC renewal. A deliberate external NVRAM edit made Settings
Uninstall refuse without changing that value, startup or the record. A compatible
host-staged payload also finished cleanup after a controlled stop following stock
restoration and reboot. Wired CarPlay projection, a virtual focus input and return
to Mazda passed with both features selected. These are bounded correctness checks,
not timing, RAM, physical-input, audio, charging or long-term reliability results.

The earlier CI payload recovered its transaction but left the startup logo over
an already-ready CarPlay dialog. That failure is preserved separately from the
reviewed fix and its new-artifact results. See the
[v74 findings](reverse-engineering.md#v74-installer-port-and-native-code-placement)
for source/artifact identities, failed candidates and qualification limits.

Matched checks of both **Turn Display Off** and **Turn Display Off and Show Clock**
also passed on stock and this CI bundle. Sustained ACC shutdown retained the blank
or clock screen respectively, normal OEM software wake returned to unobscured
Home, and normal UI/ACC operations restored the original saved display state.
Physical wake controls remain untested.
The earlier inference of phone disconnection from missing host USB entries was
incorrect: stock wired CarPlay and input worked while those entries were absent
and the CMU's USB device-controller interface was UP. See the
[display and USB-role findings](reverse-engineering.md#display-off-startup-and-usb-role-on-v74).

A freshly extracted copy of the current OEM-only CI bundle also passed manual
SD maintenance: Install/update, automatic restart, completion and Open settings.
It retained Factory/Show and the original backup base. All 32 public entries in
the installed package/runtime matched CI; private INSTANCE was the sole addition.
This qualifies maintenance from fresh payload contents through the existing SD
bench path. The earlier physical USB insertion evidence retains its own source
identity; this is not another physical insertion test. No spare USB is required
for the bench maintenance check. Supporting record:
runs/v74-release-20261120T064850Z/release-batch/maintenance-qualification.json.

Show also produced a camera-visible warning after both normal ACC startup and
Mazda's controlled `GenericReboot(0)`. The earlier `/sbin/reboot` case selected
Mazda's unexpected-shutdown logo branch, which covered the warning until it ended.
Its logo-to-Home outcome remains recorded under those original conditions.

Normal Settings Uninstall after that fresh-SD reinstall also passed, removing
both owned packages/state and restoring all 19 intake hashes and mode/UID/GID,
saved absent touch NVRAM, original loaded native/frontend and read-only root.
A subsequent stock ACC start displayed the warning with live factory touch
configuration; normal long-Home returned the actual wired CarPlay grid.

The current bundle also resumed Fuel Economy Monitor after matched normal ACC
starts with Allow/Skip and Factory/Show. Both saved DriverInfo category 3 and
returned to the visible app using their respective selected/original native
routes. This adds a distinct startup continuation; audio playback is outside it.

Physical touch under a declared motion restriction, physical commander response,
remaining applicable startup/audio routes and matching-car installation remain
release gates.
No qualified v74 download or vehicle-ready claim is made.

### Historical v55 releases

The following evidence belongs to the earlier **55.00.750B NA / cmu150_NA**
development releases; it does not qualify v74.
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

The unreleased v0.2.0-dev.3 candidate rendered its updated installation warnings
and post-restart USB-removal message. After Open settings, Mazda's Display tab
timed out waiting for its slider control. Opera exited and the watchdog rebooted
the CMU. Why the control missed registration remains unresolved. Later cleanup through the
backend restored original startup/NVRAM, removed the product files and passed a
stock boot check; this does not qualify the failed UI transition. Keep the
candidate unreleased until that failure is understood and the full flow passes.
See the [failure and cleanup record](reverse-engineering.md#installer-message-trial-and-old-cmu-cleanup).

See the [firmware-scoped evidence](reverse-engineering.md#standalone-installer-backend).
These are bounded bench checks, not long-term vehicle reliability qualification.
The outgoing CMU has unreliable touch hardware. Physical touch/motion behavior,
broader last-app/display-off cases and the modern-firmware port remain before a
normal owner release. Power loss at arbitrary storage-write points is also
unqualified; the host suite covers additional injected failures.
