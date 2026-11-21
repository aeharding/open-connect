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

## Iterate on the UI

Run `make check-ui` for the dialog, Settings, runtime and USB-loader behavior
fixtures. It needs Node.js and opens no physical device. Use this during small
UI edits; the full host suite and CI remain the pre-merge checks.

Batch visual changes and use targeted native rendering checks. A final supported
CI artifact still needs install/update/startup/Settings/uninstall qualification.
Changes to durable state, publication, native lifetime or recovery require checks
for those affected cases. Do not repeat the whole lifecycle for each label edit,
or relabel an old artifact's evidence as testing a new one.

The [dev.8 wireless result](cmu/wireless-carplay.md#installed-development-candidate)
records native connection and maintenance checks. The [dev.7 installed Base result](base-comparison.md)
retains the measured CI candidate and its complete maintenance checks. The earlier
[dev.5 verification result](startup-verification.md) retains its grouped-directory
optimization and original artifact identity. Deferred physical-input/audio and
matching-car checks still prevent a qualified v74 release.

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
these firmware checks.

## Existing modifications

Fresh installations require the exact supported OEM startup, board-detection,
service and native files on **74.00.324A NA**. Remove the existing wireless
CarPlay mod before installing Open Connect; the installer does not recognize or
adopt its modified files. Remaining conflicting edits cause refusal.

Reinstall checks the current targets and dependencies before accepting inputs.
Later edits are preserved and refused. The development candidate's Open Connect
wireless-enable option retains actual vehicle/hardware identity. A separate
[wireless ACC baseline](wireless-comparison.md) retains timings, RAM and failures;
usable early input/audio and long-parked reliability remain unqualified. See
[wireless research](cmu/wireless-carplay.md).

The removed compatibility allowance remains in Git history. Its captures retain
their actual source identity; they are not tests of this OEM-only revision.

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

Arbitrary old-package compatibility, including cross-firmware maintenance, is
not supported. Unknown edits are preserved even if restoration has partly completed.

## Qualification

The **0.3.0-dev.8** bundle from
[CI 44942234519](https://github.com/aeharding/open-connect/actions/runs/44942234519),
source `c25d5202ddebfed15b2f3eab8cccedb54a244dad`, passed fresh installation,
dev.7 update and same-version reinstall retaining choices and an imported key,
wireless controls/restarts/reconnection, and uninstall from wireless enabled.
The [wireless qualification record](cmu/wireless-carplay.md#installed-development-candidate)
identifies the artifact, restoration checks and remaining limits. These checks
do not qualify audio, physical input or a real-car release.

The **0.3.0-dev.7** bundle from
[CI 44917434811](https://github.com/aeharding/open-connect/actions/runs/44917434811),
source `2bbc8ade53ea455bd923c0fd4ae487ee9e93e285`, has separate
[installed-preset measurements and maintenance qualification](base-comparison.md).
Its public manifest is
`e403bdd466a0e8d15bbcc787fa02268aaae3972fb704f88cb45d7efc6bfa8fed`.
Fresh defaults, native confirmations/cancellation, automatic restart, completion,
Open settings, same-version dev.7 reinstall, legacy dev.6 → dev.7 migration and
normal Settings uninstall were checked through the maintained flow. Base on
selected Warn after startup; disabling required a full restart to return to Info.
Other preferences and the original uninstall baseline were preserved. Earlier
physical-insertion and interruption records below retain their actual sources;
this new maintenance path used manual SD staging with the existing USB loader.

The [Services development qualification](pandora-comparison.md#maintenance-and-restoration-qualification)
records its exact measured and later maintenance artifacts. The final CI bundle
preserved Pandora off and existing preferences through normal update/restart/
completion/Open settings, then passed normal Settings Uninstall and independent
original-startup checks. The original physical service files were never changed.
Physical-input/audio and matching-car checks remain separate.

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
