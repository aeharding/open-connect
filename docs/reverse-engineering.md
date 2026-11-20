# Mazda Connect findings

Findings apply to **55.00.750B North America** unless another version is named. Detailed original records
remain in [Git history](https://github.com/aeharding/open-connect/tree/1e8efdfea264e4b31704d9e378da1f1b3be0ced6/docs/history).

## UART access on the replacement v59 unit

The replacement's stock boot reported **59.00.441A / cmu150_NA** and registered
an LVDS touchscreen plus `Virtual Keyboard` as input1. That registration alone
does not establish working physical touch or remote navigation. One normal UART
login using Mazda's public default `root` / `jci` credentials returned
`Login incorrect`; no retry or shell command followed. The same login was
previously verified on the outgoing 55.00.750B NA unit. This single-unit result
does not establish a firmware-wide credential change. Private evidence:
`runs/replacement-resume-20261119/login-console/`.

Later UART access using the public `user` / `jci` login succeeded with UID 1000.
This unit's UID 0 account is named `cmu`; a single `cmu` / `jci` attempt was also
rejected. Its stock SSH configuration uses port 36000 and key authentication.
An interrupted access trial left a startup hook and temporary SSH listener;
the attempted connection timed out without establishing authenticated root access.
Cleanup verified and backed up the hook before removing it, then verified a
fresh stock boot with the hook, its staging file, runtime directory and temporary
listener absent. Mazda's startup checksums were unchanged and the physical root
remained read-only. Private evidence: `runs/replacement-v74-20261119/` and
`runs/replacement-cleanup-20261119/`. This did not qualify the installer on v59.

The later read-only intake found that this unit's firewall source sets INPUT to
DROP and permits SSH on port 36000, with no allowance for the temporary listener's
36001. The normal 36000 listener was reachable and its host key matched the key
read over UART. That makes the missing firewall allowance the leading explanation
for the earlier timeout; it was not an authentication rejection. Private evidence:
`runs/replacement-access-research-20261119/`.

The installed OpenSSH 5.9 binary names `/etc/ssh/sshd_config` as its default;
the separate `/etc/sshd_config` is a different inode. A one-line candidate adds
an owner key file to `AuthorizedKeysFile` alongside Mazda's file. OpenSSH 5.9
[supports multiple key files and username expansion](https://github.com/openssh/openssh-portable/blob/V_5_9_P1/sshd_config.5).
The owner-authorized repair passed the CMU's `sshd -t` before publication,
preserved a verified original and an independent guarded restore script, and
returned the physical root to RO. After a full supply cycle, the normal server
accepted the owner's key as `cmu`, UID 0. SFTP retrieved the protected original
configuration byte-for-byte. Effective configuration retained password
authentication off, the original Mazda key path and port 36000; live firewall
inspection confirmed the normal rules. Original startup files, passwords and
Mazda keys were unchanged. The one-use entry and staging were removed, and access
persisted without a custom startup hook or additional SSH daemon. The restore
script's input checks passed; restoration itself was not exercised. This is
single-unit bench access evidence, not installer qualification or a promise of
access surviving an upgrade. Private evidence: `runs/replacement-root-ssh-20261119/`.

## Owner-key access after the replacement's v74 upgrade

After the owner completed the update, authenticated root inspection identified
**74.00.324A / cmu150_NA**. The previous owner SSH key was initially rejected.
UART continued to show logs and a login prompt, but one previously working
`user` / `jci` attempt returned `Login incorrect`. This does not establish that
v74 disables UART, or identify why that login failed.

The maintained USB trigger launched a one-use access-recovery payload on insertion.
Before writes, it checked the exact firmware and the packaged SSH configuration's
SHA-256. It preserved the original configuration and an independent guarded
restore script, then added the owner's key path alongside Mazda's path in
`/etc/ssh/sshd_config`. The normal server reloaded successfully on port 36000;
password authentication remained off. Root SSH and SFTP then worked with the
same pinned host identity. Downloaded original and installed configurations
matched the expected hashes. The USB trigger was consumed and the physical root
returned to read-only.

A subsequent 30.012-second ACC-off interval produced a new kernel boot. The same
owner key authenticated as `cmu`, UID 0; the restore preflight passed again,
the physical root remained read-only and camera footage showed Mazda Home.
The startup script and frontend index matched the verified v74 package, and
Opera used the stock index. The USB remained connected with its trigger absent;
access persisted without rerunning the payload, a custom startup hook or an extra
SSH server. No supply commands were sent during this check.

This is single-unit development-access evidence. UART login was not restored,
the restore operation itself was not exercised, and full supply-loss persistence
was not tested on v74. It does not qualify Open Connect features or a general
upgrade route. At that checkpoint the published installer required 55.00.750B NA;
the later maintained v74 port is recorded below. Private evidence:
`runs/post-upgrade-20261120T052126Z/` and `runs/access-resume-20261120T053952Z/`.

## V74 installer port and native code placement

Fresh intake on **74.00.324A / cmu150_NA** matched the extracted originals.
Both board GPIOs read 0 and the running Service Manager selected `sm.conf`.
The port preserves Mazda's board decision and composes both `sm.conf` and
`sm_WCP.conf`, rather than forcing one profile.

The native library has no file padding after its RX segment at `0x6f79c`.
The port inserts one `0x8000` alignment interval there, moves the original file
tail, and updates the affected file-offset metadata with static linker-emitted
words. Original virtual addresses and symbol values stay fixed. Original section
bytes stay fixed except for the verified call-site word; the authored payload
extends RX into the available virtual-address gap below
`0x70000`. Standard Clang/LLD/objcopy produce the code and replacement words;
the maintained shell composes them with this unit's hash-verified original.
Independent host comparison checked every original section, symbol and program
header. On the first installed boot, the loader mapped the composed UIA and MMUI
libraries at their expected offsets with the physical root read-only.

That first boot still displayed the disclaimer: the initial adapter intercepted
the helper call at `0x83d4` in `UIA_SYSTEM_FocusChangeCallback`. Ordinary events,
including ShowDisclaimer, instead reach `UIAHLP_ProcessContextEvent` from
`UIA_SYSTEM_EventCallback` at **`0xbfb4`**. Its machine/context arguments resolve
to `0x83dac` and `0x77d48`, and its nested event ABI matches the wrapper.
The corrected adapter uses this ordinary-event call. On its next boot, the native
trace went directly from Intro 1023 to Home 1015 and logged successful logo-service
cleanup. A successful load alone had not established a working bypass.

That correction exposed a separate visible failure: the new looping-logo surface
still covered Home and the completion dialog. The paired renderer had sent
`DisposeIntroVideo` after its transition, and the native logo state read 0, but
v74's separate `NEWLOOPLOGO_SURFACE` was still running. Mazda's Disclaimer outgoing
callback also sends `NotifyDisclaimerEnd`; its native handler stops the process
named by `/var/run/newlooplogo.pid`. After checking that PID's actual splashplayer
identity, sending that OEM event once exposed the completion screen. This was a
manual mechanism check, not a clean startup pass. The maintained Intro completion
callback now emits both events, in order, after the replacement screen completes.
Its next update/restart reached visible completion without intervention: native
logs recorded the bypass, the renderer emitted both events, and camera footage
showed the completion dialog without the looping logo. Both preferences were
retained. This is one startup result; repeated-start and recovery qualification
remain separate checks.

The first composition attempt exceeded the API response deadline while copying
the native file one byte at a time. Its orphaned composition finished, but no
transaction record or target changes followed. Reconciliation verified stock
startup/metadata, absent touch NVRAM and the same boot. Buffered prefix/tail
copies removed that bottleneck. The next attempt stopped before writes because
the dependency-name validator rejected `sm_WCP.conf`'s underscore. The corrected
lookup keeps the exact known-root-path mapping and rejects unknown names.

Installation, automatic restart, completion, Open settings and the touchscreen
radio page then ran on v74. The earlier v55 SliderCtrl reset did not recur in
this check; its original cause remains unresolved. These are local-build,
host-staged payload trials, not physical USB-insertion or CI-artifact qualification.
Normal Settings Uninstall on the paired-renderer candidate restored startup and
touch NVRAM, deleted the product state, and restarted into stock native mappings
and frontend. All 19 initial file hashes and metadata matched the final intake;
the physical root was read-only and no product runtime or startup stage remained.
Private originals, host checks, compiled ARM assets, failed attempts, camera/UART observations and
restore preflights remain in `runs/v74-release-20261120T064850Z/`.

### First v74 CI bundle

[CI run 44703590719](https://github.com/aeharding/open-connect/actions/runs/44703590719)
built version 0.3.0-dev.1 from source 1850c73. The reviewed port merged in
[PR #90](https://github.com/aeharding/open-connect/pull/90). The public payload
manifest hashes to
f8b88d7de32759498b98498f8f6862abe6b06c35370ce0ea063a73af2c6951de.
Its compiler outputs differ from the local build, so local results were not
carried over as CI qualification.

Host staging launched this bundle's normal session from empty product state.
Install, automatic restart, native bypass, both OEM cleanup events, visible
completion and Open settings passed. All installed payload hashes matched CI;
the backend adds a per-installation INSTANCE, so the durable package ID differs
from the public manifest. The selected native mappings used the composed RAM
files, dependencies and originals verified, and physical root stayed read-only.
The initial boot budget was 2. Factory Default and Allow in the touchscreen radio
page committed absent and disable NVRAM respectively. Back returned to the list;
Show on the disclaimer page committed warning preference 0. A software restart
preserved the choice and loaded the original native mappings. Its trace entered
Disclaimer, while the camera showed the looping logo through to Home; this does
not qualify a visible warning. Normal Settings Uninstall then restored all 19 input hashes/metadata, absent
touch NVRAM, original mappings and root read-only; product/runtime state was gone.
That fully uninstalled stock boot also traversed Disclaimer while the camera
showed the logo through to Home. No introduced display difference was established;
a visible warning remains unqualified under other startup conditions. Physical touch and commander
operation are separate unqualified checks.

A second fresh installation of the same CI payload reached completion with both
features. Done returned to Home. The next software restart kept the same selected
snapshot and preferences, loaded the composed native files, cleared both startup
video layers and reached unobscured Home. The durable budget fell from 2 to 1, then to 0 on the next selected start;
reaching Home did not renew it. After unobscured Home on that last attempt, a
single guarded TERM to the verified Opera PID/start triggered Mazda's configured
watchdog reset. The following kernel loaded original native/frontend paths,
restored the saved absent touchscreen key and kept budget 0 with both choices
preserved. No selected marker remained and physical root was read-only. The
camera showed stock Home. This is a controlled frontend-failure case, not a
spontaneous product failure or proof of every startup failure. A subsequent 30.020-second ACC-off interval and new kernel renewed the exhausted
budget and selected both saved choices, leaving budget 2 and NVRAM disable with
physical root read-only. No supply commands were sent. The camera reached Mazda
Home and the ordinary Enable Apple CarPlay dialog. Selecting Agree through the
virtual keyboard established a wired session and visible CarPlay dashboard with
both Open Connect features selected. A deliberate Right input changed visible
focus; the normal long-Home event returned to Mazda. This is one projection/input
smoke test, not physical controls, audio, charging, timings or long-term reliability
qualification. Relay, UART and camera closed cleanly. Transaction-interruption
tests remain separate checks.

One controlled supply-output interruption then tested a durably prepared touch
preference transaction before target changes. The new kernel reconciled it to
active with touch 0, warning 1, absent NVRAM and root read-only. Voltage/current
setpoint bits were unchanged. Record recovery passed, but startup did not: the
logo covered the display through the observation, and neither renderer cleanup
event appeared despite the native Home transition.

A read-only snapshot found the correct hook loaded, with the framework idle on
CarPlay's enable dialog beneath the logo. Thus file presence and native Home
were insufficient. The outgoing-Intro notification had not delivered cleanup.
The new candidate observes the OEM completed incoming-template callback instead,
delegates it unchanged, waits through startup templates, leaves Disclaimer's
cleanup to stock code and restores the prior callback after handoff. The private
regression executes the actual BaseApp/frame-completion code without an outgoing
Intro template and with CarPlay focus; it rejects the old implementation.

After preserving the failure, one manual pair of OEM cleanup events uncovered
the enable dialog. Agree and long-Home returned the unit to normal use so the
maintained update could be tested. This recovery is not a clean startup pass.
The local incoming-frame candidate then updated with preferences retained and
reached unassisted completion. Repeating the prepared touch 1-to-0 supply-output
interruption recovered the record and reached the visible CarPlay enable dialog,
with both cleanup events and no intervention after power-on. Touch 0, warning 1,
absent NVRAM, budget 2, selected code and root read-only were verified. This is a
local-build result under frame-local/; reviewed CI qualification and broader
release checks remain in progress.

The incoming-frame correction was independently reviewed at `ba941122` and
merged in PR #91. Its actual [CI bundle](https://github.com/aeharding/open-connect/actions/runs/44716935060)
has public payload-manifest SHA-256
`dc2c88ac78dba5ca9a11f8c453331bb3bfcfd554a1d5667aa5280e52f08cb019`.
A fresh host-staged installation reached completion and Open settings remained
stable for the 45-second observation. All 32 public payload digests matched;
only the private installation INSTANCE was added. Both touchscreen choices
committed the expected NVRAM values. This is new-artifact evidence, separate
from the earlier CI bundle and local candidate.

On the local candidate, an intentional external touch-NVRAM edit made normal
Settings Uninstall refuse with “Nothing was overwritten.” The external value,
record and startup bytes were unchanged. After independently undoing that owned
test edit, the maintained transaction primitives restored startup and touch state
and deliberately stopped before cleanup. A stock reboot verified all 19 original
hashes/metadata and original mappings while the removed-state record remained.
The new CI payload, staged independently in RAM, recognized that retained state.
Choosing Uninstall finished cleanup and restarted; all product files, backups
and the record were absent, all 19 originals still matched, and physical root
was read-only. This qualifies that controlled stop and compatible payload handoff,
not arbitrary interruption points or physical replacement-USB insertion.

The same CI installation then passed the prepared touch 1-to-0 supply-output
interruption: active record, no pending operation, touch 0/warning 1, absent
NVRAM, budget 2, selected native files and physical root read-only. Both cleanup
events appeared and the camera reached the ordinary CarPlay agreement dialog
without intervention after power-on. Supply voltage/current setpoint bits were
unchanged. The phone and CarPlay hub appeared in the host USB inventory after
this full power cycle. Their absence from an earlier host inventory was initially
misclassified as disconnection; the role comparison below supersedes that
interpretation. Neither inventory qualifies charging or USB reliability.
New-artifact evidence is under runs/v74-release-20261120T064850Z/ci-ba941122/.
Agree then opened the wired CarPlay dashboard, a virtual Right input changed
visible focus, and the normal long-Home event returned to Mazda. These results
use touch 0/warning 1 after recovery; they do not establish physical controls,
audio, charging, timings or long-term projection reliability.

Reinstalling that same CI bundle preserved touch 0/warning 1 and reached
completion. Show saved through the normal radio page and the following boot
loaded the original native files; the camera again showed logo through to Home,
as in the stock comparison. Returning to Allow/Skip through the menus selected
both features across three software starts, with attempt counts 2, 1 and 0.
A 2.014-second ACC off/on interval at count 1 kept the same kernel and a
byte-identical record. After the last selected start reached the ordinary
CarPlay agreement dialog, one TERM to the verified Opera process triggered
Mazda's watchdog reset. The next kernel used original native/frontend paths,
restored absent touch NVRAM and retained both preferences with count 0.
A subsequent 30.014-second ACC-off interval and new kernel renewed the budget
and selected those preferences, leaving count 2 and NVRAM disable. Neither ACC
trial sent supply commands. These are controlled recovery cases, not universal
fault detection or physical touchscreen qualification.

With both choices selected after renewal, wired projection, a virtual focus
change and return to Mazda passed. A deliberate external change from NVRAM
disable to enable then made normal Settings Uninstall refuse. Readback verified
that the external value, startup and record were unchanged. After independently
undoing that owned edit, normal UI Uninstall restored all 19 intake hashes and
metadata, saved absent NVRAM, original native/frontend paths and root read-only;
all product files, backups and runtime state were gone after restart. These are
results from the reviewed CI payload, separately preserved under its conflict/
and uninstall/ evidence directories.

### Display-off startup and USB role on v74

A matched stock/selected comparison used Settings → Display → Turn Display Off,
then one sustained ACC-off interval and a new kernel. Stock used 30.018 seconds;
the same reviewed CI bundle with Allow/Skip used 30.017 seconds. Both retained
the blank screen after the startup logo. Read-only observations of the exact
native display-mode globals agreed: current/last mode changed from 1/3 before
the cycle to 1/1 afterward. The normal OEM `DisplayOffGUIActivity` event woke both
to unobscured Mazda Home, with mode 3/1. The selected boot retained OEM GUI
initialization and emitted both `DisposeIntroVideo` and `NotifyDisclaimerEnd`.
No process memory was written and no post-start cleanup intervention was used.

A further normal ACC cycle from the awake state restored the original
saved mode 3 in both configurations, confirmed as current/last 0/3 in a new
kernel. Normal Settings Uninstall after the CI trial again restored all 19 intake
hashes/metadata, absent touch NVRAM and original native/frontend paths, with no
product state/runtime and physical root read-only. This qualifies the
blank display-off option and software wake under these conditions, not physical
controls, audio or every last-app route. Private evidence is
under runs/v74-release-20261120T064850Z/startup-routes/, including
stock-display-off.json and ci-display-off.json. These are correctness captures,
not timing measurements.

A separate matched case tested **Turn Display Off and Show Clock**, using
30.014-second stock and 30.016-second selected ACC-off intervals. Both retained
the otherwise dark screen with time in the upper right, without a leftover
startup logo: native current/last mode changed from 2/3 to 2/2 across the new
kernel. Normal OEM software wake returned each to unobscured Home at 4/2.
The original `UIA_SYSTEM_UpdateDisplayModeOnDisplayOffExit` at VA `0x19e54`
explicitly maps blank-off 1 to 3 and clock-off 2 to 4; the different wake values
are expected stock behavior. The selected clock boot preserved GUI initialization
and emitted both video cleanup events. In both configurations, normal blank-off
and wake followed by another normal ACC cycle restored the original saved mode 3
(current/last 0/3). Private clock-startup/stock-clock.json and ci-clock.json link
the raw mode, ACC, camera and UART evidence under the same release evidence root.
Normal Settings Uninstall after the clock trial again verified all 19 original
hashes/metadata, saved absent touch NVRAM, original native/frontend paths and
root read-only, with product state/runtime absent and saved display mode 3 intact.
This adds the clock option under these conditions; physical wake controls,
audio, timing and broader last-app coverage remain unqualified.

A matched foreground wired-CarPlay case also restored the dashboard automatically
on stock and the same reviewed CI bundle with both features enabled. Stock used
30.021 seconds of ACC off and the selected case used 30.014 seconds; each started
a new kernel without post-start input or a consent action. Both retained cached
last-app type 6 and native display current/last 0/3. Hardware-camera observations
showed projection, with carrier 1 and fresh receive traffic; the selected boot
also emitted both video cleanup events. This establishes the startup destination
under these conditions. The planned usable-input comparison remains incomplete:
the raw/filtered arrow and filtered-wheel probes did not establish a visible
focus response on stock. It does not qualify physical controls, audio, charging,
timing/RAM or native wireless CarPlay. Private last-app/plan.json and
stock-acc/result.json / ci-acc/result.json retain the original criterion and limits.

Fixture setup needed recovery before each matched case: one stock supply-output
reset recovered its inactive projection link, and a separate normal ACC cycle
after the CI installation completed recovered unreachable bench Ethernet/SSH.
Voltage/current settings were unchanged; Install was not repeated. The latter
boot showed the Ethernet adapter, DHCP client and listening SSH server, but no
lease result was captured before recovery. Its cause remains unresolved. These
setup interventions are separate from the subsequent unassisted startup results.
Normal Settings Uninstall afterward restored all 19 intake hashes/metadata,
absent touch NVRAM, original loaded native/frontend and display 0/3 in a fresh
stock kernel, with no product state/runtime and physical root read-only.
Private last-app/uninstall/qualification.json records closure; all 19 observers
completed with closed handles and all 173 sealed artifacts matched their manifests.

The earlier missing-phone interpretation was premature. Fully stock live wired
CarPlay accepted a virtual Right input while the phone and bridge were absent
from the host USB tree. At that checkpoint `usb0` was UP, associated with
`fsl-usb2-udc/gadget`, and had received about 50.8 MB. Together with the live
projection/input result, this shows that host enumeration alone cannot establish
phone disconnection. Interface presence or cumulative counters alone would not
prove a current working connection either. The original inventories remain
preserved; startup-routes/usb-role-reconciliation.json records the correction.
This is separate from the earlier demonstrated logo-cleanup defect.

A bounded OEM Settings check temporarily disabled Apple CarPlay and used a quick
ACC cycle to expose the phone/bridge in host mode. The original enabled checkbox
was then restored and visually verified before the CI display-off installation.
Even in that verified host-mode view, the intended SanDisk drive and a removable
storage volume were absent at that checkpoint. The later [USB and SD
qualification](#v74-usb-launch-and-sd-bench-storage) used the owner-reinserted stick. The stock
cold/warm inventory comparison and buffered supply samples remain evidence of
those conditions only; they do not qualify charging or continuous reliability.
The normal long-Home event also returned stock CarPlay to its last Mazda app
(Communication in this check), so it must not be treated as an unconditional
request for the main Home screen.

The earlier CI trial's private evidence remains under
runs/v74-release-20261120T064850Z/ci-1850c73/, including source/run identity,
checksums, guarded actions, camera/UART observations and readback. This is not
physical USB-insertion qualification or a published release. A first read-only
intake helper omitted its D variable and failed before any write; a corrected
helper completed the checks. Startup SSH probes before network initialization
failed; the pinned connection returned after DHCP. Neither failure is counted
as a product failure or an uninterrupted observer pass.

### Preserving recognized wireless-mod inputs

**Retired approach.** The current installer requires supported OEM inputs. The
owner will uninstall the legacy wireless mod before Open Connect and wants a
future native wireless-enable option that preserves actual vehicle/hardware
identity. Compatibility with the old mod is outside the initial release.

PR #98 briefly recognized four component hashes from the inspected
[reference revisions](cmu/wireless-carplay.md#what-the-existing-mods-change).
Its private host comparisons covered stock, Kenatia, luxubuok and luxubuok after
Kenatia's startup edit. That allowance, its additional backup checks and its
mod-specific test have been removed; Git preserves the implementation. The
independent safeguard refusing later edits during reinstall remains maintained.
Private historical records: runs/v74-car-mod-compat-20261120/derived-source-hashes.json,
composition-results-final.json and stock-check-final/result.json. No existing
wireless mod was installed on the CMU during that work.

Actual CI 44785660779 / source `c0cc169` then passed the maintained stock-bench
install/restart/completion flow, UI reinstall conflict refusal, independent
owned-edit restoration, fresh UI reinstall preserving preferences/base snapshot,
Open settings and normal Settings Uninstall. Both installed packages/runtimes
matched all 32 public entries plus INSTANCE. Uninstall verified all 19 intake
hashes/metadata, saved touch NVRAM, original native/frontend and root read-only in
a new kernel, with no product state/runtime.

The second manual SD-loader call did not establish a fresh maintenance UI. The
USB entry holds a nonblocking fd8 lock inherited by its session; another call
returns success before creating a second payload/runtime. An actual CMU probe
under that lock confirmed this behavior and left stock state unchanged. In the
trial, the subsequent key sequence dismissed the prior refusal dialog, with
unchanged kernel/record/package. The earlier interpretation that a product dialog
had reappeared was not established: the manual call was insufficient to reopen it,
and the direct screenshot did not establish the current hardware input target.
An isolated cleanup-JavaScript replay also omitted the entry lock and does not
prove a reachable session-ownership defect. A later explicit maintained reopen
reported no conflict; hardware-camera confirmation preceded the actual reinstall.
An initial host read helper also lacked its
AUTOSTART variable; correcting that read did not repeat Install. One SSH read
during the actual reinstall restart timed out before a later read completed.
These failures remain separate from the successful cases. The final restored-stock
warm restart left projection carrier/RX/TX zero, matching the previously recorded
stock fixture issue; a separate bounded supply-output recovery followed without
changing voltage/current settings. No cause or reliability improvement is claimed.
The live trial used OEM inputs, not a wireless-mod installation. Supporting
records in the same private root: ci-identity.json, installed-qualification.json,
conflict-qualification.json, first-reinstall-input-reconciliation.json,
reinstalled-qualification.json, uninstall-qualification.json and
sd-reentry-reconciliation.json. Earlier capture/interpretation records are retained;
the reconciliation does not relabel the wrong-dialog input as a reinstall.

## Native installer and Settings on v55

Open Connect uses Mazda’s `Dialog3Ctrl` for install and completion. **Open settings**
takes the same route as the Home gear. **Settings → System → Open Connect** returns
to the same list. Both the summary and the single-choice pages use `List2Tmplt`.
Mazda’s time-zone picker supplies the radio-row pattern. Keep About last on the
System tab because v55 addresses it by position when updating speed restrictions.
Mazda can rebuild that list while it is open. Preserve the extra row on refresh
and repaint the list. Mazda’s time-zone handler caches the chosen index and sends SetTimeZone from
the radio list. Open Connect follows that interaction. The dot moves on selection and the bench
owner saves in the background. Back remains available.

On 55.00.750B NA, commander-path input selected Install, opened Settings, and
changed Touchscreen back to Mazda default. Independent NVRAM readback confirmed
the change. Selecting **Show** for the disclaimer restored stock startup. The
bench harness missed that save acknowledgement in the GUI. A fresh boot
confirmed stock startup and the warning appeared. The bench Mac handled the
writes over SSH. At that stage, autonomous USB installation and physical touch
input were untested; the standalone installer evidence below supersedes the USB limit.

## Earlier installer and touch trials

Mazda’s `Dialog3Ctrl` rendered an Open Connect dialog over Home. Virtual
keyboard events sent through Mazda’s commander input path selected Install
and Cancel. We captured the actual 800 × 480 Wayland display with Mazda’s
`screenshot` utility and copied the PNG over SSH. Switching the active Opera
browser to a second document had produced a black screen and a reset.
The successful trial used the original startup page and its optional GUI script.

On the same startup, the native disclaimer bypass went directly from Intro to
Home and the display service reported its touch restriction disabled. The trial
changed only the display-specific NVRAM key. Undo removed the key because it
was originally absent. After reboot the display service reported its default
restriction enabled and the stock disclaimer returned.

In a second trial the Install choice triggered the paired bench change.
After the selected boot, choosing Uninstall triggered undo. An authenticated Mac
bench runner carried out both operations over SSH. The restored boot reached Home.
A standalone USB transaction without that Mac and finger input on a working
display still need end-to-end testing. [Installer](https://github.com/aeharding/open-connect/issues/7) · [Touch](https://github.com/aeharding/open-connect/issues/60)

## Touch input and CarPlay on v74

The [v74 porting record](cmu/firmware74.md) pins the analyzed files and maps the
startup, disclaimer and renderer changes needed for the single-baseline move.
It also provides the replacement's read-only intake and qualification sequence.
The v55 native payload cannot be reused: v74 changes the state machine and has
no file padding between its executable and writable system-UI segments.

The 74.00.324A NA firmware has two places to test. Mazda’s LVDS display service
checks a restriction before forwarding physical touch events. It has a
display-specific setting in nonvolatile memory. CarPlay also receives a
restriction signal and sets the phone’s limited-UI mode. The firmware alone
doesn’t tell us what a user will see when only the display setting changes.

On the stationary replacement bench, first verify that stock touch works in
Mazda’s menus and CarPlay. Then establish a controlled condition that reproduces
the stock restriction. Compare both screens under that same condition before
the change, with the display-specific change active and after undo. Record
the original setting, including whether it was unset. [Touch investigation](https://github.com/aeharding/open-connect/issues/60)

## USB bootstrap preview

On **55.00.750B NA**, an Open Connect USB package now opens Mazda's native
`Dialog3Ctrl` over the existing Home screen. The preview offers only Cancel;
it performs no feature installation. Cancel through the commander input path,
immediate reinsertion, duplicate-launch suppression, USB removal and the
one-minute dialog deadline passed.
The same kernel and Opera instance continued running, with the physical root
read-only and no developer startup script installed. Insertion/removal used
software reauthorization of the identified thumb drive; physical touch was not
tested. SSH prepared the drive and observed the result, but did not launch the UI.

Kenatia's `jci-autoupdate` marker and shell-expression `.up` filename must be
placed **at the USB root**. Keeping them in the upstream source directory
`run_triggers` did not launch anything. The adapted filename selects only
`open-connect/run.sh`. Mazda's package parser evaluates it; the empty `.up`
then fails ordinary firmware validation. This is a script entry point, not a
firmware update. The launcher returns immediately after handing off its verified
RAM copy, avoiding the updater's request timeout during a dialog session.

Opera's D-Bus `Navigate` method accepts a void `javascript:` URL in its existing
document. A short **deferred** call to `utility.loadScript` loads the payload
without replacing the document or disrupting its heartbeat. The working loader
uses a relative path preserving the `file://localhost` origin. A whole-script
URL and synchronous file-loading probes did not execute the payload; their
failures remain in the private evidence. The bootstrap supplies a session token
and a bounded loopback reply receiver; the payload owns the dialog. Firmware,
frontend and staged-payload checks precede execution. There are no root remounts,
watchdog changes, NVRAM writes or startup hooks in this preview.

The static-file refactor also passed launch, Cancel, reinsertion, removal and
deadline cleanup. The separately loaded dialog and UI need no generated JavaScript.
The [CI-built Make/shell bundle](https://github.com/aeharding/open-connect/actions/runs/44243108343)
passed automatic USB launch and Cancel cleanup on the same stock v55 baseline.
Refactor evidence is in `runs/usb-installer-20261118/`. That Cancel-only payload
has since been replaced by the standalone installer.

Earlier private evidence: `runs/usb-bootstrap-20261118/`, including the `build-v6` file
manifest, insertion/cancellation/removal receipts and screen captures. This
establishes the bootstrap at Home only. Cold insertion, v74, the autonomous
install/uninstall transaction and release qualification remain separate work.
[Build the current installer](installer-development.md) ·
[Installer work](https://github.com/aeharding/open-connect/issues/7)

## Standalone installer backend

Stock v55 BusyBox includes `tcpsvd` and `flock`. Its `httpd` has no CGI support
and rejects POST with 501. Opera successfully sent a plain-text POST to a
loopback `tcpsvd` worker and read its JSON response with the CORS response header.
The maintained installer uses one small compiled request parser and static shell
backend, replacing the preview's image acknowledgement and short-lived receiver.

The bundle from [CI run 44267661925](https://github.com/aeharding/open-connect/actions/runs/44267661925)
(`8370d73`) installed from empty installer state through the native USB dialog,
restarted into privately composed RAM native/JS files, reached Home and opened
native Settings. With USB removed, Settings uninstall restored original startup,
NVRAM and mappings. Earlier qualification revisions exercised reinstall with
preferences retained and the lifecycle/fault cases below; the final bundle change
only corrected failed-composition error output.

The startup file's original metadata is `775:1018:3015`;
retaining only its bytes or assuming root ownership is insufficient. Original
native/JS files on root stay unchanged; the selected RAM files live until reboot.

The installed policy starts with three attempts. A full ACC-off shutdown reached
0.002 A standby; the next kernel boot renewed the allowance and consumed one.
A 1.426-second ACC interruption resumed the same kernel without changing the
record. Two software resets consumed the remaining attempts. An Opera fault
after Home then caused watchdog recovery, rather than earning fresh attempts.

The first exhausted-budget trial restored the stock native configuration but
hit the hook's 25-second deadline before restoring touchscreen NVRAM. Repeated
OpenSSL startup dominated verification. Batching the same package/dependency
checks reduced three paired measurements from 4.90–5.03 s to 2.39–2.45 s and CPU
time from 1.96–1.97 s to 0.43–0.45 s. Reported maximum resident set was 5,552 KiB
before and 5,600 KiB after; filesystem input/output counters were zero in both.
These repeated post-boot checks reused cached files and measure verification,
not total boot time or cold-storage performance.
With that fix, a separately prepared exhausted budget and late Opera fault
produced one watchdog reboot, stock mappings, restored NVRAM and read-only root.
There was no forced second restart. The display service reads its restriction
before our hook, so the restored touchscreen value applies on the next boot.

A controlled B+ interruption tested one real pending preference transaction.
After its prepared record was flushed and NVRAM changed, the owned backend was
paused and supply output cycled without changing voltage. The next boot completed
the recorded transaction, selected the requested configuration and left root
read-only. This tests that interruption point, not every possible storage failure.
Host tests separately inject failed writes and ambiguous target states.

Uninstall with a deliberately changed startup file saved its exact bytes,
metadata and preferences, restored the pre-install startup/NVRAM and restarted
with original native mappings. A later edit made Undo refuse without changing
that file or the transaction record. After removing only that test edit, Undo
restored the saved modified startup, metadata, preferences and actual NVRAM;
its restart selected that exact snapshot. Qualification limits are in the
[USB guide](usb-installer.md). Private evidence, including the deadline failure,
observer failures and independent restore, is under `runs/installer-20261118/`.

### Complete uninstall and BusyBox publication

The complete-removal change retires Undo and keeps the restoration record until
persistent packages, originals and snapshots have been deleted. Recovery checks
saved ownership as well as current targets, because the older Undo implementation
could adopt an unrelated modification into its current snapshot. Those conflicts
must not become permission to overwrite and discard the saved edit.

The first candidate exposed two differences in Mazda's BusyBox 1.19.2. Its ash
unwinds function locals before a subshell EXIT trap runs, and its `cp` replaces
an existing destination inode. The candidate installed its targets but failed
cleanup with `work: parameter not set`, left root writable, and refused restart.
Fresh record/target verification preceded independent read-only and stock
restoration; this was a candidate failure, not a successful install cycle.

The publisher now keeps trap inputs in subshell scope and writes through the
exclusively created staging inode. An isolated RAM fixture on the actual CMU
reproduced the old failure and verified successful and publication-failure cleanup with
the fix. CI also runs the publisher under BusyBox ash, and host tests simulate
the target's inode-replacing copy behavior. Private failure, restoration and
fixture evidence is under `runs/owner-guide-polish/bench/`.

The corrected [CI bundle 44350948917](https://github.com/aeharding/open-connect/actions/runs/44350948917)
(source `2f30ead`, version 0.2.0-dev.2) then completed a fresh USB installation,
restart, completion and native Settings. The installed package manifest matched
the CI payload, both preferences were selected, native mappings used the private
RAM files, and root was read-only. Six direct Wayland captures document this UI.

With release files removed and USB detached, Settings Uninstall deleted the
persistent product directory and restarted. Fresh readback verified original
startup bytes and `775:1018:3015` metadata, absent touchscreen NVRAM, original
native mappings and Opera's stock index, physical root read-only, and no startup
staging, product runtime or listener. Evidence: `verify-install.out`,
`remove-installed-usb-driver.out`, `uninstall-boot/`, `stock-intake/` and
`verify-stock.out` beneath that private evidence directory.

### Installer message trial and old CMU cleanup

The [v0.2.0-dev.3 candidate](https://github.com/aeharding/open-connect/actions/runs/44368399412)
(source `df7fd03`) displayed the new installation warnings and post-restart
completion message on 55.00.750B NA. The installed package, selected native
mapping and physical root read-only state matched expectations.

After **Open settings**, the native UI requested the Display tab at 1:39.168
into the boot. Eight seconds later, the GUI still reported Home and timed out
loading the list template's controls. Its only outstanding control was
`SliderCtrl`. Opera exited, and at 1:50.374 the service manager stopped feeding
the watchdog because Opera had exited. The post-click observation in
`open-settings.out` matches the timestamp, GUI process and Home context in saved
log archive 020. The timeout preceded that observation by 54 ms.

The stock v55 framework emits the missing-control warning when registration is
still pending at the deadline. The underlying reason for the missing registration
is unknown. The earlier successful Display tab capture provides a comparison.

At the later cleanup intake, the attempt budget was zero, selection was absent,
and the original frontend and baseline touchscreen NVRAM were observed. The
normal uninstall backend restored original startup metadata and removed the
product directory. A new boot verified the original native mappings, stock Opera
index, absent touch override and root read-only. Historical lab/rescue folders
were then removed after a host archive matched all source file checksums.
This was backend cleanup, not a repeated UI qualification.

The candidate remains unreleased. Private evidence: `runs/installer-messaging/bench/`
and `runs/old-cmu-cleanup-20261119/`. The latter includes the saved crash/log
archives, `backup-verification.json`, `uninstall-driver.out`, `verify-stock.out`
and `verify-final.out`. Resolve the slider-loading failure and verify the
complete installer/Settings flow before publishing it.

## USB detection at Home

Stock v55 mounted a SanDisk drive read-only through the retrofit hub within
2.2 seconds of software reattachment at Home. Mazda’s update and media
services both saw the device. The test used an ordinary drive and required
no media-menu interaction. The [bootstrap preview](#usb-bootstrap-preview)
extends that result to Open Connect's native prompt on v55.

Kenatia documents the user-visible precedent on 74.00.324. Inserting the drive
opens a dialog automatically. The user then chooses install or uninstall.
[Project instructions](https://github.com/Kenatia/mazda-cmu150-wcp-mod#installation--uninstallation)

### V74 USB launch and SD bench storage

The same reviewed CI 44716935060 / source `ba941122` bundle passed a removable-USB
install, automatic restart, completion and Open settings on exact 74.00.324A NA.
For that install, software reauthorization of the identified SanDisk caused Mazda's
normal update scanner to launch `open-connect/run.sh`; SSH did not start the
installer. A separate owner-performed physical insertion, after full uninstall,
also opened the correct Install prompt. Its observer sent no UART input and ran
only a read-only readiness check. The firmware log recorded the mass-storage
attachment, root auto-update marker and USB session source. The prompt was then
cancelled without a second installation. These are separate entry checks, not
USB insertion timing measurements.

After the installed boot with USB present, the active USB runtime held the 32
public manifest entries. The durable installed package held those same entries
plus its private INSTANCE; its manifest hash matched the package ID. Treating the
public USB runtime as that private package caused an initial host-verifier
assertion, not a payload mismatch. Another runner guard stopped after USB OFF
because the device hides its serial while unauthorized. Fresh evidence confirmed
OFF and no ON transmission; a separate guarded ON completed once. Both failures
are retained without repeating installation or rewriting their captures.

A spare 256 GB SD card initially used exFAT and did not mount. After the owner
formatted it as FAT32, read-only access passed, and a later boot mounted it at
`/tmp/mnt/sd_nav`. The current loader accepts USB-style paths and its root trigger
does not search that navigation path. For **bench testing**, a temporary bind
mount at `/tmp/mnt/sda1` and a guarded invocation of the unchanged loader opened
the maintained maintenance dialog from the SD copy. All 32 payload entries
matched the same CI artifact. No firmware/product changes, root launch markers
on SD or new automatic service were needed. The mount alias expires on reboot;
this does not establish native SD auto-launch or a supported owner SD installer.

The owner then replaced the original USB stick with the iPhone. With both
features still selected, the actual panel showed the CarPlay dashboard while
three SD manifest reads succeeded and Ethernet SSH remained connected. Fresh
projection traffic and Ethernet counters increased during those reads. This
establishes one live CarPlay/SD/Ethernet coexistence case, not physical input,
audio, charging, timing/RAM or continuous reliability.

Normal Settings Uninstall, with the original USB physically absent, restored
all 19 intake hashes/metadata, saved absent touch NVRAM and original loaded
native/frontend in a new kernel, with no product state/runtime and physical
root read-only. A later restored-stock software restart left the projection link
inactive; one bounded supply-output reset restored the link. This separate stock
fixture failure does not establish an Open Connect or SD cause. One normal
long-Home then showed the dashboard, with fresh projection traffic, successful SD
reads and Ethernet. Its initial readback used a nonexistent interface name; a
fresh read-only observer completed without resending input. Voltage/current
setpoints remained unchanged. Private evidence is under
runs/v74-release-20261120T064850Z/usb-resumed-20261120T162005Z/:
plan.json, installed-payload-validation.json, sd/viability.json,
physical-usb/qualification.json, uninstall/qualification.json and
stock-link-recovery/qualification.json link the cases.
Raw observations remain private; the SD bench path is separate from qualification
of a distinct replacement USB drive.

## Silent Entertainment without a TAU

Mazda's Audio Manager test-menu API provides enableStatus and enable(boolean).
The Lua handler owns audio enable state; SYSTEM startup policy can subsequently
turn it off when the TAU is absent. Service availability alone is therefore not
a sufficient startup activation boundary.

The [bench helper](https://github.com/aeharding/open-connect/blob/main/tooling/open_connect/bench.py) uses that API. Live setup,
repeat setup, teardown and setup passed; FM Now Playing and the source list opened
without a TAU. This proves UI access, not sound output or playback. Runtime state
and ownership expire on reboot/service replacement; no persistent hook is verified.

## Disclaimer and intro handoff

Native MMUI selects Disclaimer before the GUI renders it. On the observed Intro
path, ShowDisclaimer1470 in IntroAnimation1021 selects Disclaimer1010.
The loader XML priorities are not bypass flags. Replacing the event with Timeout
or Yes is wrong: those events are unhandled in IntroAnimation.

Disclaimer Timeout1481 has nine continuation rules covering focus, display-off,
navigation, last app and audio availability. Yes omits the display-off rule.
The native prototype reuses the ordered continuation rather than forcing Home.
Rule granted/denied actions are alternatives; actions precede the old context's
exit hook. Cleanup and pending-warning behavior must be preserved.

The [native prototype](https://github.com/aeharding/open-connect/tree/492fe06/experiments/disclaimer-native/) bypassed the observed
warm Intro route. Early intro-player disposal caused a black interval. The
[paired renderer hook](https://github.com/aeharding/open-connect/tree/492fe06/experiments/intro-handoff/) defers DisposeIntroVideo
until renderer completion; the sampled long gap disappeared, but a dim transition
remained. Independent undo and restored-original startup passed. This does not
establish cold ACC, every resume branch or a seamless sub-frame transition.

The separate upstream-derived comparison uses a transparent NoCtrl template and
native Yes; the local Snap variant still showed a handoff. It is excluded from
AGPL distribution under its noncommercial license; see [THIRD_PARTY.md](https://github.com/aeharding/open-connect/blob/main/THIRD_PARTY.md).

## Loaded libraries and read-only remount

Replacing a still-mapped native library caused an EBUSY read-only remount failure.
Keeping same-filesystem hardlink holds through apply, undo and loaded-module
lifetime resolved the observed case. Restoring the file on disk does not unload
modified code: verify a restored-original startup and mapping before releasing
its holds. See [mapped publication](https://github.com/aeharding/open-connect/blob/492fe06/experiments/mapped-publication/README.md).

## Spinner and frontend lifecycle

List2Ctrl and NowPlaying4Ctrl contain a circular loading indicator using
IcnStatBgFunctions_Refreshing_01.png with a two-second repeating rotation.
List2's loading overlay has a default 200 ms show delay. This is distinct from the
shimmering Mazda LoopLogo. We have not established which control causes the user's
post-shimmer spinner or whether it is limited to a particular boot mode.

Replacing the entire frontend document stopped the stock framework heartbeat
and caused Opera to exit. Preserve the document, normal transitions, callbacks
and native initialization rather than suppressing or spoofing the heartbeat.

## Optional extension loading

**One selected startup now controls service policy, logging and native/JS code
together.** A following baseline boot omitted the combination while the prepared
files remained unchanged.

| Part | Selected boot | Following baseline |
| --- | --- | --- |
| Stitcher | Did not auto-start | Process running again |
| Native logging | Inherited Warn; native filter rejected Info | Override absent; native Info messages returned |
| Native extension | Copied MMUI plugin loaded and invoked our marker module | Original plugin; marker module absent |
| GUI extension | Copied index ran our JS marker | Original index; no JS marker |

Both boots reached Communication Home. The original startup file was then restored
and its holds removed, with root read-only. The existing comparison JS stayed
installed, so this baseline is the bench configuration, not a factory-stock unit.

These are code-entry and fallback results, not a performance claim or a shipping
feature. Timing and CPU/RAM samples were retained; one pair cannot establish an
optimization. Private evidence: `runs/composed-generation/result.json`.
See the [architecture direction](extension-architecture.md) for what remains open.

<details>
<summary>Source references and earlier leads</summary>

Current source findings:

- index.html:33 loads ../../data/integration/developer_mode_GuiConfig.js before
  Utility/BaseApp/GuiFramework and framework.init(). It resolves to /data/integration,
  whose parent was mode 0777; the script was absent. Utility.js:66–94 handles script
  onload only, not onerror. This is a candidate bootstrap slot, not readiness proof.
- sm.conf:145–169 starts MMUI and Opera through separate dependency sets. Current
  /data resolves to /tmp/mnt/data on /dev/ffx01p4; data_persist is separate.
  Current availability does not establish availability at an earlier boot hook.
- svcjcimmui.so constructs UIA priority/context records before invoking loaders
  (0x2e08–0x2f50). It is not a neutral plugin registry. The
  [historical probe](https://github.com/aeharding/open-connect/blob/ab4752b/experiments/optional-loader/README.md) hooks its final return at
  0x31ac, before ServiceInit calls AppsLoadingFinish at 0x1914. This cannot select
  services that have already started.
- Websockets.js:507–551 constructs/sends events on an open MMUI socket.
  libjciguiifm.so:0x4d64–0x4d7c resolves the UIA name and passes the complete JSON
  object to ProcessEventJSON (0x4584). That walks UIA records and calls the event
  callback at offset 12. getGuiifmCallbackLLHead is at 0x40dc; Register at 0x40e8
  refuses an existing ID. No new callback or GUI message has been exercised.
- sm.conf:67–74 makes Wi-Fi and voice startup stages depend on blm_ira_aha;
  start_wifi:526–528 in turn depends on stage_wifi. Pandora, Stitcher and Aha
  declarations are at 414–437; TV at 519–523. A service-removal plan must resolve
  retained consumers and startup dependencies, not simply remove declarations.

Private exact sources, checksums, before/after identities and saved disassembly:
runs/runtime-boundary-research/*-result.json and guiifm-disassembly.txt.
The relevant source SHA256 values are:
sm.conf 52dac9b051ab02a07afdc7bdfac56402420f8230901b5a55a76a7e9c44fb2e08;
index.html b0e116b941f29078ced19b864a1b888cf76d8bc3e4974af081efca4693e5c420;
Utility.js eff9e63497fbd0f90d5dc9e2d9403c93fc6171cc71f70319462686a423fea791;
Websockets.js 090486339f83b40d9758faf867f3984e14e659df574fa702033a60d49406c973;
GuiConfig.js 165ef686e419dd562868ac1be206cb2a7bcd6d52ef976578c3246cbc982976e0;
libjciguiifm.so d438121db2d3fa5f75dc9b40f5eb6d54b607ac348cfd490f3ed750621572be09.
Plugin source pins and build reproduction are in the probe README.

</details>
Captures were read-only with known completion and closed ports; no OEM write or
reboot occurred. Source ordering is not proof of runtime fallback or cold startup.

## Startup selection and reset evidence

**Main learning:** a consumed trial can fall back without a working GUI or
optional runtime. Mazda's existing watchdog performs the reset; Open Connect
must choose what runs afterward.

The [one-shot selector](https://github.com/aeharding/open-connect/blob/79b5b562086acfb615c50807395c21adae5e1e7c/tooling/open_connect/firmware55/selection.py)
runs in /usr/bin/autostart before normal-mode setup, the Logger and Service
Manager (SM). It consumes and flushes a trial record before choosing a fixed
configuration. A spent record selects Mazda's original service configuration.

| Actual bench test | Observed result | Limit |
| --- | --- | --- |
| Two ordinary warm boots | Trial configuration once, OEM configuration next; running SM arguments verified | Selection proof, not a feature-health policy |
| SIGSEGV to one identity-checked MMUI process | SM stopped feeding the watchdog; automatic reset booted the baseline configuration | External process fault, not a bug in a modified library |
| Trial-only JS infinite loop | Native GUI Manager closed Opera after missing heartbeats; watchdog reset returned to the original entry page | Reconciled from the saved crash archive and fresh target checks; original serial observer stayed incomplete |
| Supply output off/on after a flushed consumed record | Record survived; fresh root access and read-only root returned | One completed write in normal runtime |
| Supply cut after early commit, before services | Spent record survived; next boot selected OEM SM configuration | Explicit three-second post-flush pause; not during rename/fsync |

These tests retained the existing comparison JS and original native library.
“Baseline” here means the pre-existing bench configuration, not an entirely stock
unit. Independent undo removed the startup hook and its hardlink holds after
each completed trial. The runtime power test ran with the hook already removed.

The runtime and early-startup power interruptions were **6.964 s** and **6.920 s**
between output requests. DPS150 voltage/current settings were unchanged; no
voltage-setting commands were sent. These test full supply loss, not ACC.

For the early test, the selector emitted a console marker after successful file
and directory flushes, then paused before returning to service startup. Output-off
was confirmed 0.390 s after that marker, within the three-second pause. The next
boot saw the record spent and started OEM SM configuration; fresh root access,
read-only root and Home returned. The original startup script was then restored.

The first early-test observer refused before cutting power: the logged Linux
banner arrives after this early console marker. Its replacement used the actual
ordered bootloader/kernel-handoff text. That failed attempt and subsequent
one-login reconciliation remain separate from the successful power-cut run.

### A real feature can be selected without replacing its installed files

One corrected trial loaded the independently implemented native disclaimer
bypass and its JS cleanup companion from a prepared configuration. Actual logs
showed `IntroAnimation → HomeScreen`, then intro disposal after Home's transition
completed. Native mappings, JS execution, fresh access and read-only root passed.

The following boot selected the original MMUI/Opera paths and native library,
with no companion marker. Both reached Home. The prepared files stayed in place;
the original installed native and local comparison JS files stayed unchanged.
This proves feature selection and omission, not a new timing/no-flash result
or qualification of every last-app/display-off route.

Private evidence: `runs/selected-feature-v2/result.json`.
The [reproduction guide](https://github.com/aeharding/open-connect/blob/79b5b562086acfb615c50807395c21adae5e1e7c/docs/disclaimer-development.md)
builds from explicitly supplied private originals; none are published.

### A live process is not proof of a working UI

The first selected-feature trial exposed an OEM loader limit: both MMUI XML
`libpath` and `lib` fields truncate at 49 bytes. The selected plugin loaded,
but the system UIA did not. MMUI remained alive, and no automatic reset was
observed before an explicit normal reboot returned to baseline. Installed
native/JS files were unchanged.

Check initialization and useful behavior, not only process existence. Selection
provides fallback **on the next boot**; it does not guarantee that every failure
will cause a reboot. Automatic recovery from this kind of partial startup still
needs a bounded health check outside the optional component.

The corrected adapter splits the parent and relative library path within both
limits. See the [feature builder](https://github.com/aeharding/open-connect/blob/79b5b562086acfb615c50807395c21adae5e1e7c/tooling/open_connect/firmware55/generation.py).
Private failed trial, diagnosis and recovery: `runs/selected-feature/result.json`.

### Normal does not mean the GUI initialized

**Mazda's SYSTEM state returned Normal during a startup stuck on the logo.**
A deliberate missing-system-UIA trial reproduced the earlier loader failure
without changing the installed native or GUI files.

| Observation | GetCurrentSystemState |
| --- | --- |
| Working Home | 2 — Normal |
| Working Compass screen | 2 — Normal |
| System UIA absent; MMUI and Opera alive; logo still visible | 2 — Normal |

The failed startup entered Normal at uptime 45.410 s; the read-only query still
returned Normal at 112.53 s. The copied loader reported the missing library,
and fresh process mappings confirmed its absence. No automatic reset occurred
before our explicit recovery request after uptime 132.85 s.

This rules out process existence **and SYSTEM Normal alone** as startup-health
checks. The [notification tests below](#ready-signals-are-not-equivalent) also reject
InitializeGuiComplete and native HMIReady as general readiness verdicts.
Neither should replenish the finite attempt budget.

The next normal reboot restored baseline mappings and Home. Independent undo
removed the trial hook and its holds; root was read-only and bench audio was
re-enabled. The earlier host upload interruption is preserved separately from
the successful fault/recovery pair.

<details>
<summary>Read-only API and evidence</summary>

On this firmware, resolve com.jci.blm.system on
unix:path=/tmp/dbus_service_socket, then query its unique owner at
/com/jci/blm/system with
com.jci.blmsystem.Interface.GetCurrentSystemState. Bind owner and boot before
and after the call. It returns a uint32 state and int32 status; the observed
status 100 is not a health score. Do not substitute the similarly named HMI-bus
service or invoke ReportGuiAvailable, which changes readiness state.

The exact SYSTEM constructor maps 1 to Init and 2 to Normal. BaseApp sends
InitializeGuiComplete after its first displayed template, even after catching
a displayed-callback exception. Native OnFinishIntroAnimation sends HMIReady
before setting the next context.

Private evidence: runs/startup-health-research/state-classification.json,
state-enum.json, and runs/startup-health-trial/ (query, mappings, closed video
and subsequent recovery). This tests one missing-UIA case, not every partial
startup, display-off/ACC route, or later GUI hang.

</details>

### Ready signals are not equivalent

**Neither promising OEM notification is a reliable GUI-health verdict on
55.00.750B.** We traced the exact code and tested both native and JS failures.

| Mechanism | What it actually establishes |
| --- | --- |
| SYSTEM Normal | Startup policy advanced; a timeout can produce it |
| InitializeGuiComplete | First-template callback ran; this firmware's native event parser does **not** recognize it |
| ReportGuiAvailable / HMIReady | Native FinishIntroAnimation action ran; it also appeared during the failed JS startup |
| JavaScript heartbeat | Event loop is servicing callbacks; not proof that an app loaded |

In the missing-system-UIA test, no ReportGuiAvailable call appeared and the logo
remained. The healthy comparison produced one call, bound to MMUI, and Home.
Read-only bus-ID canaries bracketed both captures and established coverage.
That distinction alone was insufficient: the following JS failure also produced
the notification before Opera exited.

The JS trial threw before defining systemApp. Mazda's saved error log records
the exception at **21.971 s**, a **loadingApp state timeout at 29.982 s**, and
forceExit at **31.020 s**. SM stopped watchdog feeding at 31.301 s; the automatic
reset selected baseline. Fresh mappings, root RO, Home and independent undo
passed. The original serial observer remains incomplete; it checked during
early fallback startup. This did not become the intended sustained, responsive
but stuck UI case—Mazda's own state timeout recovered first.

**Direction:** preserve Mazda's heartbeat and state-timeout recovery. A small
acknowledgment at a verified rendering boundary remains a candidate for cases
Mazda leaves stuck. Do not use the names above as proof, and never let readiness
refund attempts. No production health detector was installed.

<details>
<summary>Source and capture details</summary>

The exact native event-name parser lacks InitializeGuiComplete and returns its
unknown value 1486; the healthy log records that event being ignored immediately
after BaseApp sends it. FinishIntroAnimation is event 1404, routed through A23
to OnFinishIntroAnimation and ReportGuiAvailable. These are separate paths.

The passive monitor observed com.jci.blmsystem.Interface.ReportGuiAvailable at
/com/jci/blm/system on unix:path=/tmp/dbus_service_socket. Do not invoke the
method to query readiness: it changes state. An interrupted capture cannot
establish absence. The JS trial's capture contains the call but ends at reset;
its sender was not resolved before that process exited.

The Opera guimanager plugin initially arms 30 seconds, then each framework
heartbeat rearms 10 seconds. Its expiry closes Opera. The separate framework
state timer also closes Opera when loading or transition progress stalls.

Private evidence: runs/gui-ready-research/notification-contract.json,
runs/gui-ready-missing/result.json, and runs/gui-ready-js/result.json.
OEM sources, full logs and generated fault payloads remain private.

</details>

### A Home-specific acknowledgement

**A real browser acknowledgement and an independent deadline now work on the bench.**
The adapter preserves Mazda's transition callback, then requires the same Home
context and visible DOM on two consecutive samples. The loopback request carries
the generation and current boot ID; logs are diagnostic, not the transport.

| Bench startup | Observed outcome |
| --- | --- |
| Selected native/JS disclaimer bypass | Home signal at uptime 30.201 s; independent `ready|0` receipt and camera Home |
| Missing native system module | No Home signal; independent timeout requested a normal reboot; next boot selected baseline with original mappings and Home |

The attempt stays spent even after a healthy acknowledgement. The receiver and
supervisor exit after their decision; no permanent HTTP service is installed.
Recovery does not require optional native code or a functioning GUI. It preserves
Mazda's own watchdogs and cannot rescue a broken kernel, baseline or bootstrap.

An initial healthy trial missed readiness. The revised adapter allows the fade
to settle instead of requiring visibility immediately at transition completion.
Its successful follow-up does not fully explain the first miss or establish a
general health guarantee. DOM checks cannot prove compositor pixels; caught
callback errors, child controls, native overlays and last-app/display-off paths
remain unqualified. This is a scoped Home trial, not production retry policy.

Code: `cmu/adapters/fw55/home-ready.js`, `cmu/startup/ready-receiver.c` and
the boot-selection experiment's `readiness.py`. Private evidence:
`runs/independent-ready-feature-v2/result.json` and
`runs/independent-ready-missing/result.json`; the initial miss remains in
`runs/independent-ready-feature/result.json`. Earlier log-only observations are
preserved separately in `runs/render-ack-feature/` and `runs/render-ack-missing/`.

### The developer CLI completed the feature/recovery cycle

`oc feature` now builds the private payload, prepares independent undo, selects
one startup and returns to baseline through `disable`. In the measured FW55 run,
the native/JS feature reached Home and acknowledged at CMU log time **29.324 s**.
The one-shot record was spent; fresh checks confirmed selected mappings and rootRO.

The selected observer originally returned UNKNOWN: its 9.5 KB console check
never produced a complete begin/end frame during startup logging. Fresh read-only
reconciliation verified the feature; the failure was not relabeled an automated
pass. Startup checks now use short, separately framed commands. The subsequent
baseline boot passed automatically, followed by exact hook restoration/hold cleanup.

Both closed videos showed Home. CPU/RAM/I/O samples were captured, but different
boot ages and audio-profile conditions prevent a performance comparison.
[Historical developer workflow](https://github.com/aeharding/open-connect/blob/79b5b562086acfb615c50807395c21adae5e1e7c/docs/cli.md#developer-feature-trial).
A later clean-checkout preview run passed both selected startup and independent
Disable/baseline startup automatically, without reconciliation or reboot retry.
This confirms the short-command workflow on the bench; it does not broaden the
Home-only warm-start scope. [Try the preview](disclaimer.md).
Private evidence: `runs/feature-cli-trial/result.json` and
`runs/disclaimer-preview-reproduction/result.json`.

### What causes a reset?

~~~mermaid
flowchart TD
    JS["JavaScript event-loop hang"] --> Miss["Native monitor misses JS heartbeat"]
    Miss --> Close["Opera closes"]
    Init["App load / transition stalls"] --> Timer["Framework state timeout"]
    Timer --> Close
    Native["Critical native process exits"] --> SM["Service Manager stops watchdog feeding"]
    Close --> SM
    SM --> Reset["Watchdog resets CMU"]
    Reset --> Selector["Early selector sees spent trial"]
    Selector --> Baseline["Start baseline services and frontend"]
~~~

This is the chain observed in the controlled tests, not a claim that every JS
exception or native fault resets the unit.

A critical MMUI exit produced SM's reset_board=yes notice and watchdog-feeding
stop, followed by a new kernel boot. Opera also exited in that sequence.
This matches the compiled path through SMHEALTH_StopWatchdog (0x1bb28) and
SM_WD_Stop/stopFeeding (0x311cc). It does not disable or replace the watchdog.

JavaScript exceptions and a stuck event loop are different failure modes.
The framework catches several callback exceptions and continues. In the hang
trial, a copied entry document kept Mazda's framework but scheduled an infinite
loop. The saved log records the hang marker at uptime 48.942 s, then
OnHeartbeatMissed at 58.490 s: no JS heartbeat for ten seconds, so close Opera.
SM detected Opera's exit at 59.691 s and stopped watchdog feeding.

Serial logging was still draining messages from uptime 26 s when the reset
occurred. The observer therefore missed the hang marker and stopped as unknown.
The exact saved crash archive supplied that marker and heartbeat failure; a
separate fresh login verified baseline SM arguments, the OEM Opera entry path,
spent control and read-only root. This is a reconciled result, not an uninterrupted
automated pass. An earlier probe hit Mazda's .js-only log-stack parser before
scheduling the hang; that failed injection remains recorded.

### A reset label is not a cause classifier

**A normal software reboot and a deliberate MMUI crash reported the same
bootloader reset word.** It cannot decide whether to renew retry attempts.

| Known preceding action | Next boot's ibclog result |
| --- | --- |
| One normal /sbin/reboot | 0x00000001 — “Power-up sequence” |
| One identity-checked MMUI SIGSEGV, followed by Mazda's watchdog reset | 0x00000001 — “Power-up sequence” |

The second run reached Home with fresh root access, original native mappings,
baseline service configuration and read-only root. No new startup hook, software
reboot fallback or supply command was used. This compares one run of each path;
it does not classify battery loss or every possible reset.

The /usr/sbin/ibclog tool reads the bootloader buffer identified by ibcinfo= in the
kernel command line. The executable maps it read-only and decodes a private copy.
It also provides early boot timings. The separate boottime wrapper can signal
PID1; it is not just a passive log read. One read of the 64 KiB jci-boot-diag
partition contained only erased 0xff bytes.

**A shutdown request is not a successful shutdown.** In the exact SYSTEM service,
NotifyShutdown carries requested reboot flags and precedes settings save,
service stop and board reset/power-off. SM's normal and forced stop paths also
share completion signaling. None alone establishes a clean session end.

Private evidence: runs/persistent-policy-research/result.json, exact SYSTEM and
ibclog sources, and the closed watchdog-reset observer/video bundle.

### Readiness must not refund attempts

**A fault after Home still needs to exhaust the startup budget.** A three-boot
test used the same composed service/logging/native/JS configuration with a
two-attempt limit:

| Step | Persistent result |
| --- | --- |
| First selected startup, then explicit confirmation | One attempt used; confirmation refunded nothing |
| Second selected startup reached Home | Both attempts used |
| One bound MMUI SIGSEGV after readiness | Mazda reset; baseline boot kept the exhausted record |

Fresh checks confirmed OEM SM/Opera paths, no optional native mapping or logging
override, Stitcher running again, root RO and Home. The original autostart was
then independently restored and its holds removed. Existing comparison JS stayed.

This earlier experiment proved the finite-budget mechanism in one late-fault
case without choosing an automatic renewal event. Its selected boots all spent
an attempt. The [standalone installer](#standalone-installer-backend) subsequently
qualified its own ACC renewal and one interrupted transaction; arbitrary power
loss during storage writes remains unqualified.

Private evidence: `runs/attempt-budget/result.json`, confirmation, all three
closed observer/video bundles and independent undo. A host import refusal before
device open remains separate from the successful fault run.

### ACC must be a real transition

**A brief ignition interruption can take the driver back to Home within the same boot.**
On the 55.00.750B NA bench we switched only ACC from a running Home screen.
B+ stayed on at 12.02 V. Relay timing, supply current and receive-only UART agreed on two distinct outcomes.

| Time with ACC off | What the CMU did |
| --- | --- |
| 1.06 s | The same SYSTEM process reported OFF and ON. The GUI entered `QuickStartLoop` and completed Home 0.37 s after the logged ON event. The lowest sampled bench current was 0.531 A. |
| 17.29 s | Mazda started saving settings. Bench current fell to about 0.002 A. Switching ACC on started a fresh Linux kernel and the GUI reached Home. |

Each row is one observation with the bench comparison JS installed. The interval at which the CMU commits to shutdown is still unknown. The Home timing comes from GUI logs, without a display measurement.

**Recovery policy:** keep the remaining startup attempts through a quick resume.
The firmware's SYSTEM service reads `/sys/class/gpio/ACC_Sense`; even its first
sample can emit an ACC-on notification. The later installer requires a sustained
off observation followed by a different kernel boot with ACC on, rather than
renewing from that initial notification alone. See its qualification above.

Private evidence: `runs/acc-relay/short-1794948646590/result.json`, `runs/acc-relay/verified-cycle-1794948131443/result.json` and `runs/acc-renewal-research/result.json`.

### Implications for recovery

- **Select early.** init_cmu attempts the data_persist mount before autostart;
  still verify the actual mount. /data_persist/dev/bin/autorun is backgrounded
  inside start_normal_mode.sh and cannot reliably choose SM's configuration.
- **Consume before effects.** Missing, invalid or spent control must select
  baseline. An observed ready screen must not automatically replenish attempts:
  faults can happen later.
- **Do not guess reset causes.** The identical reset words above cannot authorize
  another attempt. Missing crash logs and shutdown-request notifications also
  cannot establish a clean end. Keep diagnosis separate from permission to retry.
- **Bound bootstrap work.** The parent uses a five-second timeout without an
  inherited stdout pipe. Host tests cover invalid control, failed flushes and a
  surviving child. Uninterruptible filesystem I/O remains outside that guarantee.

Still open: interrupted early-boot writes, repeated power cuts, vehicle ACC behavior and
production retry/health policy and automatic renewal. Service/logging/native/JS composition is now
[demonstrated together](#optional-extension-loading).
These results do not establish recovery from a broken baseline, kernel or selector.

Private evidence: runs/early-selector/result.json,
runs/native-fault-trial/result.json, runs/js-hang-trial-v2/result.json,
runs/power-cut-trial/result.json, runs/early-power-cut/result.json and
runs/boot-selector-flush/result.json. Failed attempts and raw captures remain
unchanged. The [architecture direction](extension-architecture.md) describes the
next decision.

Source evidence is retained in runs/startup-recovery-research/result.json and
supporting-slices.txt. Exact source SHA256:

| Source | SHA256 |
| --- | --- |
| autostart | b91b2c5a5b7d036860321da730ad571dbae9164d2632946f6566238c3cd42e31 |
| start_normal_mode.sh | 6a020f2b9a92406510519820cfdee004fd4b9ef41a0ab212eb2727ffe8db80a2 |
| sm | cd1104d9b0a28dcce361520de203c1180b2e6f81d939c4223a369fd66a055f0c |
| log-save.sh | a1beb68337f7c4e334b2510f0c9ad6992acebb8a7533a4022b0fbb6678428c62 |
| init_cmu | a5c3b821236f3993b15021a80130df4e33b359beb7722a8a6a6fa9a74cf455bb |

## Native logging already supports a temporary override

**Use Mazda's own setting first.** Three disposable processes using the actual
`libjcicommon.so` reported `Info → Warn → Info`: only the middle process inherited
`COMMON_LOG_LEVEL=Warn`. Its native filter rejected Info messages and accepted
Warn; two samples two seconds apart agreed. The persistent settings file stayed
unchanged and root stayed read-only.

The compiled initializer reads settings files, then parses environment variables.
This is a simpler candidate for a selected startup than rewriting the log settings
file or isolating all services. The later composed trial confirmed inheritance
by SM/MMUI. Other logging stacks and performance benefits remain untested.
Private evidence: `runs/combined-startup/log-query-result.json`.

## Configuration views without rewriting originals

**A short-lived private mount view worked on the bench.** A child process saw
`COMMON_LOG_LEVEL=Warn` through a read-only bind mount while the parent still saw
the original `Info` file. The view disappeared when the child exited, without an
explicit unmount; the physical root stayed read-only and temporary files were removed.

Mazda's `jci-log.sh` sets this default in `/config/common/log/settings.txt`.
`Logger.xml` selects sinks; it is not that default-level setting.

This proves the filesystem mechanism, not a complete startup architecture.
Isolating all services also isolates later mounts: USB, eMMC resources and
shutdown visibility must be checked before adopting it for service startup.
Mount isolation is not a sandbox for root code and does not make ordinary writes
inside the namespace temporary.

The [historical probe source and checks](https://github.com/aeharding/open-connect/tree/ab4752b/experiments/boot-selection)
are public; exact private evidence is `runs/combined-startup/namespace-result.json`.

### Normal persistent writes

Mazda already writes persistent settings and crash archives. Its `log-save.sh`
first builds an archive in `/tmp`, then moves it to `/data_persist/log/saved_logs`
and updates a counter. For Open Connect, keep frequent measurements in bounded
RAM-backed `/tmp/oc-*` files or stream them to the host; persist configuration
and recovery state when it changes. Small startup/shutdown records per drive
are reasonable; avoid continuous polling writes. Commit the startup record before
optional effects and treat shutdown recording as best effort: power may vanish
before it runs. `/tmp/mnt/data_persist` is a persistent mount despite its `/tmp` prefix.

The [kernel tmpfs documentation](https://docs.kernel.org/filesystems/tmpfs.html)
explains the memory-backed filesystem. Our successful flush/power tests above
do not establish a write-endurance budget or safety during interrupted writes.
