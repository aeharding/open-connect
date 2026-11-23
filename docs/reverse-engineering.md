# Mazda Connect findings

These findings cover **74.00.324A North America / cmu150_NA**. Observations,
offline source analysis and unqualified behavior are distinguished below.
Retired experiments remain in [Git history](https://github.com/aeharding/open-connect/blob/84471d2c69c13829c714650edf67ea22a1f9b2c0/docs/reverse-engineering.md);
old evidence has not been relabeled as testing the current implementation.

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
upgrade route. The maintained port is recorded below. Private evidence:
`runs/post-upgrade-20261120T052126Z/` and `runs/access-resume-20261120T053952Z/`.

## Early startup resource collection on v74

On the stock-service 74.00.324A NA bench, the first SSH-started RAM/CPU/I/O sample
arrived at kernel uptime 41.09 seconds, after native UI was already visible.
Camera/UART covered the preceding restart; resource counters did not. SSH is
therefore a retrieval channel for the replacement startup experiment, rather
than its launch trigger. See [performance evidence](performance.md#startup-observer-coverage-november-21-2026).

Service Manager's stock configuration runs `/jci/scripts/stage_1.sh` with no
service dependencies and permits its exit. On this exact firmware the script
contains only its shell interpreter line and blank lines, SHA256
`2ec71fc955d0107a6e90d1ab4e6f00c9438b56d3e621ef018d57c8ef07bfae7f`.
This provides a narrow temporary bench hook without changing product-managed
startup/service files. The experiment detaches a finite system-counter observer,
writes only RAM output, preserves the original inode with a same-filesystem
hardlink, and provides an independent guarded restore entry. Actual first-sample
uptime establishes coverage; this hook is not assumed to cover kernel startup.
The local trial first sampled at 11.16 seconds and completed 171 samples. Its
independent restore returned the original inode; a subsequent ACC restart
verified the original script, absent observer output and physical root read-only.

The [original experiment source and undo](https://github.com/aeharding/open-connect/blob/34d7c293a9cc7476884f88c2061164a3d7b5becd/cmu/bench/STARTUP-REFERENCE.md)
is on a playground branch, not an owner installation feature. Private intake,
camera-clock qualification and trial records remain under
`runs/startup-baseline-20261120/`. No OEM script or raw capture is published.

## Service-manager dependencies and Pandora restart

On exact **74.00.324A NA**, both stock SM profiles declare Pandora as a leaf:
no other configured service depends on `blm_ira_pandora`. Aha is different:
`stage_wifi`, `stage_vr` and `stage_gap2` depend on it. Stitcher also has a
separate helper. These static edges do not establish every runtime dependency.

The native `/jci/sm/smctl` client can query service information and request
stop/launch with `--wait`. Its verified SHA256 is
`a51a03ce7bc1f602ccca7b15af8c9698fed5debfb904f01fcc358f57ca46330f`.
A bounded stock-bench pilot stopped Pandora, observed it stopped throughout a
120-second resource window, then launched it again. The phone projection and
checked peers remained present while it was stopped. This was warm mechanism
exploration, not a startup or audio qualification.

The later launch deliberately restarted `irs_server`: the stock Pandora library
contains that initialization path, and device logs record its initialization,
the helper receiving SIGKILL, SM relaunching it, and Pandora completing startup.
It was not a clean restore of all original process identities. The Services
candidate therefore selects policy before SM starts and applies changes after a
full restart, rather than offering live service stop/start.

Pandora's initial RSS was 6,304 kernel kB, but private clean/dirty pages totaled
1,980 kB and PSS was 2,271 kB. The before/stopped resource windows had median
MemFree 198,024/200,120 kB. After launch, median MemFree was 159,576 kB, with a
large increase in Buffers and reclaimable slab accompanying Mazda's diagnostic
archive. Do not subtract RSS as freed RAM or call this single sequential pilot a
CPU/RAM improvement. A fresh original startup restored the expected stock
configuration and native/frontend code, with all 19 original hashes/metadata,
read-only physical root, absent product/runtime and both projection/network links.

Private originals, raw traces, logs and restoration receipts remain in
`runs/services-20261121/`. No OEM source or raw capture is published. The candidate
host check of both exact profiles verifies that disabling changes only Pandora's
single `autorun` attribute in the selected copy; enabled copies remain identical.
Five enabled and five disabled ACC starts then verified the selected policy:
native SM reports one Pandora start when enabled and none when disabled, with
wired projection returning in every trial. The [comparison](pandora-comparison.md)
records the modest MemFree difference, unresolved dashboard timing gain and
measurement limits. The later maintenance fixes have separate artifact identity;
these measurements remain attributed to the actually tested c98 build.

## Developer access and login-script lifetime on v74

The **74.00.324A NA / cmu150_NA** Developer options candidate provides an optional
passwordless UART root console and owner-key SSH through Mazda's normal server
on port 36000. Both default off. The [owner guide](developer-options.md) shows the
controls and import flow. Direct CMU parser checks accepted ECDSA and 2048-bit
RSA and rejected Ed25519; the private test key stayed on the host.

With [CI run 44847049064](https://github.com/aeharding/open-connect/actions/runs/44847049064)
(source `5414d59`, version 0.3.0-dev.3), a normal SD-launched Install/update
preserved both enabled access choices and the imported key, restarted
automatically and displayed completion on the physical screen. All 34 public
runtime files matched CI. Open settings and repeated import worked; the complete
MD5 fingerprint fit across two lines. The dedicated key authenticated as `cmu`,
UID 0, and a fresh UART identity probe verified the passwordless root shell.

Both off selections saved when made back-to-back. The page showed the old
startup-applied state and a restart requirement; the test key still worked
before restart. After a 30.018-second ACC-off interval, both applied bits were
off, the key was rejected, and Mazda's original `cmu login:` prompt returned.
Existing bench authorization remained usable. The original login inode was
restored at its pathname, sharing a second link with the retained hold. Both
options then enabled again and survived another ignition restart.

Normal Settings Uninstall from that enabled startup restored all **19 intake
file hashes and metadata**, the absent touchscreen NVRAM key, stock native
mappings and the stock Opera entry point. The original login inode retained one
link; its hold and staging files were gone. Product state, imported keys and
runtime were absent after the automatic restart, the test key was rejected, and
physical root was read-only. Independent recovery preflights passed. This is
single-unit evidence using virtual commander input and ignition cycles, not
physical-controller, matching-car or exhaustive power-loss qualification. No
original UART credentials were attempted. SD maintenance remains distinct from
the earlier physical USB-insertion evidence.

### Why the original login needs a hardlink

The first UART enable stopped at a failed read-only remount. Its old reader had
exited before inspection, so that failure alone did not prove the cause. A
bounded experiment with owned data files reproduced `EBUSY` while an unlinked
inode remained open, then remounted read-only with the same reader open when a
same-filesystem hardlink retained the inode. Linux 3.0's
[read-only remount check](https://github.com/torvalds/linux/blob/v3.0/fs/file_table.c)
rejects open unlinked inodes, consistent with this observation.

The maintained fix links the original login script before replacing it, keeps
that inode through repeated changes, restores it when disabling UART, and
removes the hold only after restoration on uninstall. The fresh held-original
trial used [CI run 44843072197](https://github.com/aeharding/open-connect/actions/runs/44843072197)
at `ccb3a25`; the hold retained its inode across subsequent kernel boots and the
physical root returned to read-only. Host interruption checks separately covered
13 boundaries and six toggles; they do not simulate CMU power loss.

### Maintenance request lifetime

A UI reinstall of [CI run 44845680376](https://github.com/aeharding/open-connect/actions/runs/44845680376)
(`c40f08f`) stopped with an unconfirmed result, a prepared `install` record and
no remaining backend process. Root was still read-only. The service capped each
request at 60 seconds; guarded recovery of that exact revision completed without
error in **44.434 seconds**. That was a separate host-run recovery, not a clean UI
pass. The candidate now allows a bounded 180-second request plus five seconds of
client response headroom and loads the staged USB client, so an older installed
client cannot retain its shorter deadline. The repeated `5414d59` update above
completed through the normal UI without intervention.

Private evidence stays under `runs/developer-options-20261120/`, with original
source/CI identities preserved: `fs-hold-probe.out`, `stock-before-held.json`,
`held-access-on-restarted.json`, `fingerprint-update-observer/`,
`fingerprint-recover-timing.json`, `deadline-update-observer/`,
`deadline-update-complete.json`, `deadline-key-reimported.json`,
`deadline-uart-root/`, `deadline-both-off-restarted.json`,
`deadline-both-on-again-restarted.json`, `deadline-uninstall-observer/`,
`deadline-stock.json` and `deadline-key-after-uninstall.json`.

### Settings listener port collision

On exact v74, a wireless-pilot setup boot reached CarPlay but failed to start
Open Connect Settings: `tcpsvd` reported `Address already in use`. There was no
listener on the expected port. The actual socket table showed MMUI holding an
established client connection from `127.0.0.1:35555` to Service Manager on
`127.0.0.1:9091`. The unit's ephemeral port range was **32768–61000**, which
included Open Connect's former fixed port, 35555. Checking only listening sockets
would miss this collision.

The candidate uses **127.0.0.1:15555**, below that observed range, for the same
authenticated local POST contract. During USB replacement of a verified live
35555 listener, it retains that endpoint for the current boot so cancelling UI
loading leaves the installed client usable. The next boot selects 15555. The
three-field listener record stays compatible; the USB client receives its port
as bounded launch data after actual socket ownership is verified. A Linux regression holds an established
outbound socket on 35555 while starting the Settings service and serving its
first request. Foreign occupancy of the new port still refuses publication.
Private evidence: `runs/carplay-speed-20261122/port-collision-proof.out`,
`mmui-session-diagnose.out` and `port-fix-service-tests.log`. This setup failure
preceded the timing trial; it is not a measured MMUI-affinity performance result.

### Developer UI and maintenance version identity

CI [44856371233](https://github.com/aeharding/open-connect/actions/runs/44856371233),
source `356cd7e`, rendered a normal thin Developer options title with only UART,
SSH and Import public key. Native enable dialogs explain the restart requirement;
there are no passive list rows or always-visible startup-state header. A normal
SD update, restart, completion and Open settings passed. All 34 runtime files
matched CI. UART cancel, key import with the full fingerprint, and SSH
Enable/save/off passed through virtual commander input, with verified target
bytes and physical root read-only. This does not repeat access-startup qualification.

The version in a maintenance client's status previously identified that running
client, not necessarily the installed package. CI
[44857345909](https://github.com/aeharding/open-connect/actions/runs/44857345909),
source `17b5715` / 0.3.0-dev.4, reports the current snapshot's verified package
version separately. Before any update, its actual status showed source dev.4 and
installed dev.3, and both the native screenshot and physical panel showed those
From / To values with the warning intact. All 34 staged files matched CI.
The normal dev.3 → dev.4 update then restarted automatically into boot
`5ce1f885-3fb1-4f5f-a714-67ea7d378f66`, with both version identities dev.4,
all 34 runtime files matching CI, saved access choices/key retained and physical
root read-only. Completion and Open settings passed. Normal Settings Uninstall
from this off-access startup restarted into stock code; independent verification
matched all 19 intake hashes and metadata, the original login inode with one link,
absent touch NVRAM and product/runtime state, stock mappings and stock Opera
entry, with root read-only. Raw verification SHA-256:
`692f3db7436bfe347cbbb52af0a80d969759eed071cccdad3260e1bb4d096dfb`.
The owned SD test public key was removed separately by its hash guard.
These are virtual-controller and software-restart checks, not physical-input,
matching-car or exhaustive power-loss qualification.

Unavailable identity is explicit; the renderer does not substitute its target
version for an unknown installed version. Host checks also cover same-version
reinstallation and older responses without the added field.

Separate synthetic host checks informed the [plugin proposal](extension-architecture.md):
stacked wrappers using the current Settings helper could retain or resurrect a
removed participant, and a conflict-free text merge could produce an invalid
cross-reference. These are host counterexamples, not tests of a CMU plugin API.
Supporting records remain private under runs/developer-ui-20261120/,
popup-* and version-* in runs/developer-options-20261120/, and
runs/plugin-architecture-20261120/research.md. Earlier trials retain their actual
source and artifact identities.

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
radio page then ran on v74. These are local-build,
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

`LastAppType` is Mazda's coarse saved resume category, not an arbitrary
foreground app ID. `uiaSystem_CacheLastAppType` at `0xe610` groups Home,
Communication and Settings under **Other (6)**. Their sharing that value is not
a persistence failure. **DriverInfo (3)** covers `ecoenergy` and `idm`; ordinary
Maintenance (`schedmaint`) is outside that whitelist. A running cached value
need not reflect a newly foregrounded app until Mazda's shutdown cache/save path
runs. Confirm the saved category on the next boot and observe the actual screen.
The no-TAU Fuel Economy entry uses `SelectEcoEnergy` with no audio source, making
it a distinct available startup-continuation case. Private source anchors and
normal restoration to Other are in release-batch/lastapp-handoff.txt under the
same release evidence root. Earlier type-6 wired captures retain their original
scope; they do not qualify DriverInfo or startup audio.

The current OEM-only bundle subsequently passed a matched DriverInfo check.
Fuel Economy Monitor was foreground before each normal sustained ACC shutdown.
Allow/Skip and installed Factory/Show each booted a new kernel, read saved
category 3 and returned to the actual Fuel Economy screen. Display mode stayed
0/3. Skip loaded the selected RAM native module and live LVDS configuration 0;
Show loaded the original native module and configuration 1, with the warning
visible in the camera record. This compares the installed feature choices,
not a fully uninstalled stock baseline. It adds DriverInfo continuation coverage
without qualifying tuner/audio startup, physical controls or performance.
Private release-batch/driverinfo-comparison.json links the captures. An initial
read helper chose a path from file presence and failed; the corrected reader
used actual mappings, without repeating the startup.

Before the earlier type-6 wired cases, fixture setup needed recovery: one stock
supply-output reset recovered its inactive projection link, and a separate normal ACC cycle
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

## OEM-only bundle regression

After retiring the wireless-mod allowance, CI **44798623680** / source `14919e1`
passed fresh install, automatic restart, completion, Open settings and normal UI
Uninstall through the unchanged loader staged on SD. All 32 public entries
matched the durable package and runtime; INSTANCE was the sole addition. Both
preferences were selected, and the native bypass executed. Removal restored all
19 intake hashes/metadata, absent touch NVRAM, original loaded code and root
read-only in a new kernel. The ZIP SHA-256 was
28181c1058ba9c440b015e35339a3459a72753ea78ed078ac172d0e407d4f49a.

Opening Communication before a stock warm restart did not establish another
saved last-app case: startup still read LastAppType 6 and reached Home. Stock
logs entered Disclaimer, but the corresponding camera sequence showed the logo
until Home; a visibly displayed stock disclaimer remains unqualified. The stock
warm restart also left the projection link inactive. A separate output-only
reset restored the link, followed by normal long-Home to foreground CarPlay.
This does not establish a product reliability improvement or an audio result.

Private supporting records are under
runs/v74-release-20261120T064850Z/oem-last-app/: ci-identity.json,
installed-qualification.json, uninstall-qualification.json and the raw observers.
Earlier captures keep their actual source identities.

On a later current-bundle trial, Factory/Show visibly displayed the warning
after normal ACC shutdown/start and after the OEM SYSTEM `GenericReboot(0)`
operation. The original native route and all saved source files/metadata were
verified. A low retry budget renewed correctly across the actual ACC startup.
The first relay attempts occurred while the owner's override held ACC on; native
GPIO observations stayed high and no new kernel resulted. After the override was
removed, native ACC OFF/save logs and a new flag-[0] boot established the actual
shutdown/start. The failed SSH read during shutdown is retained separately.

This explains the older warm-reboot result. `init_cmu` reads
`/data/unexpectedshutdownflag`; a nonzero value selects the higher recovery-logo
surface. The renderer can enter and leave Disclaimer beneath it. Normal ACC
shutdown clears the flag, as does the normal OEM GenericReboot request with
flags exactly 0; `/sbin/reboot` bypasses that OEM request. The controlled reboot
saves settings/stops services and resets the VIP before restarting. Its success
is not physical ACC, standby-current or retry-renewal evidence. No direct flag
write, player kill or factory reset was used. Private source anchors and captured
outcomes are in release-batch/power-route-handoff.txt, oem-show-v2-observer/ and
show-acc-after-override/ under the release evidence root.

## Touch input and CarPlay on v74

The [v74 porting record](cmu/firmware74.md) pins the analyzed files and maps the
startup, disclaimer and renderer changes needed for the single-baseline move.
It also provides the replacement's read-only intake and qualification sequence.
The native payload requires an exact state-machine and executable-layout
adapter; this image has no file padding between its executable and writable
system-UI segments.

The 74.00.324A NA firmware has two places to test. Mazda’s LVDS display service
checks a restriction before forwarding physical touch events. It has a
display-specific setting in nonvolatile memory. CarPlay also receives a
restriction signal and sets the phone’s limited-UI mode. The firmware alone
doesn’t tell us what a user will see when only the display setting changes.

On the exact v74 LVDS executable, `LVDS_GetTouchEvents` at `0x37f48` reads and
validates the controller response before checking the NVRAM-derived
`g_SpeedRestrictionConfig` and the current speed-restriction state. When both are
nonzero, it suppresses the press report; it can still send a release. Otherwise,
it forwards the report. The relevant gate is at `0x38120`–`0x38144`.

Mazda's `TouchSimulation` service takes a different path:
`LVDS_TouchSimulationEvents` at `0x3a068` writes synthesized reports without
passing through that gate. Its dispatcher does not add the missing speed check.
Injecting Linux input events is also downstream of the LVDS filter. These
interfaces can operate the UI, but successful clicks alone do not qualify the
touch-enablement feature under restriction. Software qualification needs to feed
reports before this gate and distinguish press suppression from release cleanup.

An owner-authorized isolated probe then exercised the actual ARM parser/filter
on the CMU. A private copy had an exit guard in place of service startup; a
temporary preload substituted the controller response and suppressed logging
and notifications. The filter, release sender, NVRAM reader and speed
setter/getter remained byte-equivalent to OEM code. Reports went only to a
private pipe. Independent native review checked the startup ABI and isolation.

With the actual NVRAM setting absent, unrestricted controls passed and all three
restricted presses were suppressed. The maintained setting primitive changed
absent to disable; the real OEM reader returned 0, and all five reports passed,
including the three restricted presses. The saved independent primitive restored
the absent setting, and restriction blocked presses again. All **15** samples
passed. The live LVDS process, configuration and speed state stayed unchanged;
the temporary executable/helper were removed. All 19 original files/metadata
still matched, and actual CarPlay remained visible.

This qualifies the software filter under a declared process-local speed
restriction. It does not establish physical-controller delivery, actual vehicle
motion, CarPlay's separate limited-UI behavior or performance. Supporting record:
runs/v74-release-20261120T064850Z/oem-last-app/filter-qualification.json, with
raw trial output, byte-equivalence checks and independent review beside it.

Separate stationary UI tests used the existing `com.jci.lvds.TouchSimulation`
method through host `gdbus` and a loopback-bound owner-SSH TCP forward to the
OEM HMI bus on port 3001. Its input is `(y(qq)(qq)(qq)(qq))`: a contact count and
four unsigned coordinate pairs. Press and release must be serialized; the
asynchronous dispatcher shares one event buffer. Wait for
`TouchSimulationStatus(1)` before sending the matching release. An acknowledgement
alone does not establish a visible response.

Actual camera/native evidence confirmed Home → Communication → Home, and a
Virtual Keyboard Right event changed Home focus. A CarPlay Mazda-app tap at
`(400,240)` also returned to native Home. A bounded read of the already-enabled
CarPlay consumer captured pressed then released state; the phone's native-UI
request and the visible transition corroborated delivery. An earlier `(400,260)`
attempt had no visible effect. Both coordinate and dwell changed in the successful
trial, so its cause remains unresolved. Source analysis shows CarPlay converts
raw coordinates differently from the native UI. Its advertised `TouchScreen`
D-Bus handler is a stub; the working route uses filtered multitouch input.
The optional LVDS touch FIFO is diagnostic capture, not this projection route.
These are software-generated stock UI inputs, not physical-controller or motion
qualification. Private supporting records are in
runs/v74-release-20261120T064850Z/touch-ui/, including ui-results-current.json,
projection-touch-handoff.txt and the corresponding camera/UART captures.

The current bundle repeated the UI checks with Allow/Skip active after a normal
ACC start. The CarPlay Mazda-app tap, native Communication, Back and Virtual
Keyboard Right all produced their intended visible results. The live LVDS
configuration was 0, with stationary restriction state 0. This adds active-feature
UI regression coverage; it still does not reproduce motion or physical controls.
Private release-batch/active-input-qualification.json links the paired input,
producer signals, actual camera and native logs.

The fresh-SD maintenance cycle then completed normal Settings Uninstall after the
second package had been installed and exercised. Both owned package/state trees
were removed. All 19 intake hashes and mode/UID/GID matched independently; absent
touch NVRAM, original loaded native/frontend and root read-only were verified.
A subsequent normal stock ACC start restored the visible warning, live LVDS
configuration 1, saved Other (6) and display 0/3. Actual wired CarPlay was returned
to the panel with normal long-Home. The final stock audio-helper read was false.
Private release-batch/uninstall-qualification.json and final-stock-qualification.json
link those closure records.

A separate host UI-readiness mistake toggled Mazda Tool Tips and VR Examples
before the intended page opened. Recorded checked states were restored and
verified before continuing; product preferences were unchanged by that attempt.
Subsequent input followed a visually confirmed Open Connect page, and uninstall
navigation waited for its exact row and an idle framework. Failed guards,
deadlines and the unsuccessful software gadget reset remain in the private
captures, separately from successful feature/startup results. None establishes
a CMU feature failure. All 49 new UI/batch observers are sealed with closed
handles and 472 matching artifacts; six preserve incomplete outcomes rather
than being counted as successful checks. See release-batch/capture-validation.json.

On the stationary replacement bench, first verify that stock touch works in
Mazda’s menus and CarPlay. Then establish a controlled condition that reproduces
the stock restriction. Compare both screens under that same condition before
the change, with the display-specific change active and after undo. Record
the original setting, including whether it was unset. [Touch investigation](https://github.com/aeharding/open-connect/issues/60)

## V74 USB launch and SD bench storage

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

## First reproducible startup comparison

The [November 21 stock/candidate batch](startup-comparison.md) retains five
accepted starts per condition, with local pre-SSH resource collection and
camera/UART coverage before ACC-on. Open Connect 0.3.0-dev.4 / source `3713f24`
reached the visible Home and wired CarPlay milestones later, with higher CPU and
similar free RAM. The blocked order does not isolate the cause. Three excluded
candidate attempts retain their original retrieval/foreground/cancellation
outcomes; none is evidence of a CMU boot failure. Numeric samples, I/O endpoints,
frame bounds and immutable reproduction source are linked with the result.
Normal UI uninstall plus independent observer restoration verified originals,
stock loaded code and read-only root. Private supporting records are under
`runs/startup-comparison-20261121/`; raw capture collections remain private.

## Native logging configuration lifetime on v74

On exact **74.00.324A NA**, `libjcicommon.so` uses a global RAM logging override
at `/tmp/common/log/settings.txt`, separate from the physical default at
`/config/common/log/settings.txt`. The inspected native initialization path also
recognizes a per-process RAM settings filename. This firmware behavior is used
by the development candidate's [Base optimizations](services.md#base-optimizations);
production and vehicle qualification remain separate. The original library SHA256 is
`637cc53cd0621ec7fed24be2519b3e208191dd22954d2442d70e854413874b0d`.

**Observed:** supplying Warn after startup left all 83 existing native contexts
at Info. A separate newly spawned read-only SM client, with an original getter
probe, reported Info → Warn → Info → Info as the RAM override was added, changed
and removed. Cache/enabled getters stayed 1. The probe was loaded only into that
new client; no running service was injected or modified.

Supplying the same override from a temporary stage-1 hook before ordinary service
startup then produced 74 initialized contexts with current/normal Warn and peak
Info, seven earlier initialized contexts still at Info and two uninitialized
contexts. A later primary block-end read found 73 Warn/eight Info/two uninitialized,
with `L_settings` also initialized at Info. Those counts describe their particular
reads, not a fixed whole-system split for every startup or
all diagnostic sources. Existing services cache their initial level; adding or
removing the file alone does not qualify a running policy change or restoration.
Restoration requires a fresh original startup and loaded-state verification.

The original Info configuration, service files and library remained unchanged.
Read-only state inspection used the exact mapped library, PID/start identity and
initialized logger PID. The original getter/read probes and hook are available
in [experiment source 173a839](https://github.com/aeharding/open-connect/tree/173a839d3a0f225b1d32fb2ba34c74ffe3f172c2/cmu/bench);
the [comparison method](logging-comparison.md) keeps mechanism evidence separate
from timings. Supporting records are `startup-mechanism-result.json` and
`fresh-process-mechanism.json` under private `runs/logging-prefilter-20261121/`.
OEM inputs, compiled OEM dependencies and raw process reads remain private.

The installed dev.7 candidate publishes the Warn file only for a selected Base-on
boot, after ordinary feature preparation. It checks the exact physical Info file
and common library first. Base off skips publication; exhausted-budget fallback
returns before it. A failed publication clears the selected marker. Existing RAM
resources are refused rather than adopted, replaced or deleted. These failure
paths have host checks; the installed on/off paths have separate
[CI-bundle qualification](base-comparison.md#maintenance-and-restoration-qualification).

**Observed tooling constraint:** this CMU's BusyBox 1.19.2 `ln` has no `-T`.
An existing or racing destination directory can change ordinary `ln` semantics.
The existing native flush helper's small link mode instead calls ARM's `link`
syscall directly, atomically refusing any existing destination. The Warn source
is an owned staging file in the same RAM directory; cleanup removes only that
staging name. This avoids overwriting another provider or linking inside its
directory. Actual ARM publication succeeded on the CI-built candidate; independent
host probes also checked existing files/directories/symlinks and a late directory
race. Supporting records are `link-capability.out`, `reinstalled-verified.out`
and `review-base.md` under private `runs/base-optimizations-20261121/`.

## Wireless timing clocks and bench Ethernet fallback on v74

**Source-backed, 74.00.324A NA:** `/etc/syslog-ng.conf` constructs native log
prefixes with `r_jci_log_tstamp`, using `R_DATE` and removing the date portion.
The [syslog-ng macro documentation](https://support.oneidentity.com/technical-documents/syslog-ng-open-source-edition/3.22/administration-guide/63)
defines `R_DATE` as reception time. A prefix near `00:00:55.000` is therefore
receiver wall-clock time of day, not a direct `/proc/uptime` sample or the exact
time a function executed. The original configuration SHA256 is
`fa6c51bac24de38f6a7e3e81a4a6ae7733ce4127a4424d1c3d467fad73448de7`.

The [wireless baseline](wireless-comparison.md) keeps these events separate from
camera/ACC and mapped kernel timings. Its fixed-event export requires a unique
new-boot syslog marker, ignores prior shutdown messages, keeps repeats and missing
events, and exports no log bodies or phone identifiers. Wall-clock calibration,
delivery buffering and drops remain limits; a native session event does not
establish visible projection, input or audio readiness.

**Source-backed:** `/jci/scripts/start_eth1_dhcp.sh` waits for Ethernet, runs
`udhcpc` with quit-on-lease and exit-on-failure options for ten attempts, then
adds a static fallback address and waits until the interface disappears. It does
not retry DHCP while the interface remains present. The original script SHA256 is
`4738ab12939b2dade5e5873d11931b7bc4acf02e29721f78e6062e454f2d1f25`.

**Observed:** Base-off wireless attempts 4 and 5 show the SSH listener starting,
Ethernet with no IPv4 address, and DHCP ending with “No lease, failing.” Attempts
1–3 obtain the expected lease. CarPlay is camera-visible in all five starts;
only the first three have retrieved resource traces and kernel-clock mappings.
Fresh ACC recovery restored the pinned SSH connection, without changing IP or
firewall configuration. This supports Ethernet DHCP failure as the missing-access
mechanism; why the DHCP exchange failed remains unresolved. It is not evidence
of a wireless CarPlay boot failure.

Supporting records are the five `rx.bin` captures, original fetch failures,
`network-uart-private.txt` extracts and `network-uart-counts.json` under private
`runs/wireless-enable-20261121/wireless-base-off/`, with separate recovery
observations. Raw logs and firmware sources remain private; the public comparison
retains the failed attempts and numeric observations.

## Native startup file metadata on v74

**Observed on 74.00.324A NA:** a bounded RAM-only candidate using the Linux 3.0
[ARM stat64 interface](https://github.com/torvalds/linux/blob/v3.0/arch/arm/include/asm/stat.h)
matched BusyBox's device, inode, size, mode, UID, GID, modification time and
change time for the GUI framework, LVDS service and a synthetic RAM file. The
104-byte ARM layout and architecture-specific open flags were checked against
the kernel interfaces. Streaming SHA-256 matched the pinned firmware files and
independent host vectors. This did not install a hook or change product state.

One subsequent ACC restart of the unchanged CI control preserved all ten sampled
metadata fields, including available timestamp nanoseconds, for eight inputs:
the two physical-root files, three persistent package files, composed UIA,
current config and baseline autostart. Checking the earlier sealed plan and
independently resealing the same source hashes both succeeded; the plans were
byte-identical. The record, preferences, physical read-only root and normal
wireless projection remained intact. The four-file SD probe was removed after
exact hash/count checks.

This supports metadata stability for those inputs across one kernel restart.
It does not establish a fast-path hit rate or startup saving. Matching metadata
does not prove uncopied file bytes are identical; maintenance retains full
hashes and selected runtime bytes must be checked during copying. Supporting
records are private `runs/native-boot-20261121/abi-result.json`, `abi-source/`,
`cross-result.json`, the single ACC capture and `cross-cleanup.out`.

The v74 NVRAM sysfs leaf `keys/lvds_speed_restriction` returned `disable` followed
by a terminal NUL byte (`64 69 73 61 62 6c 65 00`); ACC returned `31 0a`.
The native NVRAM reader must handle this driver convention separately from
immutable text files, while rejecting interior NULs or trailing data. A read-only
pre-install check recorded these bytes in private `sysfs-byte-intake.out`; it
changed no device state.

## Overlapping the native selector with Mazda startup

The dev.12 candidate uses one locked native worker across two exact autostart
anchors: before normal-mode setup and after its original one-second sleep,
immediately before board detection. An authenticated policy check samples ACC
and touchscreen NVRAM before releasing the worker. Remaining checks, selected
file staging and both durable record barriers overlap Mazda's existing work.
The original shell always joins that worker before choosing SM profiles. There
is no delayed shell recovery or second NVRAM read after release. Recovery stays
before Mazda's profile and HDCP/NVRAM jobs.

Both Base settings use this path. Warn is published before SM starts. Mazda's
earlier `cpugauge` job can initialize logging during the overlap; the owner chose
this tradeoff over adding synchronous Base-on delay. Three readbacks from both
initialized gauge and MMUI processes reported Warn in each checked Base-on pilot. Those observations
do not prove every possible initialization order.

A byte-identical inode or timestamp change refuses selection for that boot.
Only after all covered digests still match can it save a root-private request
for full verification on the next boot. The request names the current snapshot;
it cannot select files, change NVRAM or spend an attempt. The verified shell
reseals inputs and commits the authoritative record before removing a matching
request. Stale requests are ignored; corrupt bytes do not create requests.

UIA and the modified system-app script remain in their immutable, verified
package directory on persistence. Small RAM symlinks select them without
duplicating their contents in tmpfs. Native UIA mappings confirmed this path.
Independent installed-Settings Uninstall then restored the original loaded
UIA/MMUI, original startup and touch state, and removed both persistent and RAM
Open Connect directories. Private supporting evidence is
`runs/stock-parity-20261122/dev12-uninstall-stock-verify-retry.out` and
`dev12-installed-ui-uninstall-retry/`, at source `1ff3fe2` before the later
read-only hint/plan-verification fixes.

The [matched dev.12 comparison](stock-startup-comparison.md) on reviewed CI
`2fedfcdf` recorded zero join wait in all three Base-off starts, with native SM
`stage_1` median +0.085 s versus stock. Home was still about +0.397 s later,
shared-window CPU +0.831 percentage points and minimum MemFree 3180 KiB lower.
One separate Base-on warm restart confirmed zero join wait and three current
Warn readbacks each for MMUI/cpugauge; it does not qualify Base-on performance.
Unique allocated runtime tmpfs measured 408 KiB, with 208 KiB private pages in
the listener/ignition processes in one postflight. These observations do not
establish the no-overhead/no-unapproved-RAM target.

## Opera rejects block function declarations in strict code

The dev.9 CI candidate `06ae21f` reached native wireless projection, but its
installed Settings client did not initialize. The actual Opera engine rejected
`settings.js` with `FunctionDeclaration in Statement context` at line 393:
`function show` was declared inside an `if` block in strict code. Modern Node
accepted the same source. The resulting missing `OpenConnectSettings` prevented
runtime initialization and the maintenance prompt. That startup is retained as
a failed UI qualification attempt; its earlier visible timing alone cannot
establish the benefit of the complete working candidate.

Use a function expression in that branch. The maintained UI checks now parse
every installer JavaScript file as ES5 and reject declarations outside source
or function bodies, including legacy extensions Acorn otherwise accepts. The
intro property fragment is checked inside its object context. This is a host
syntax check, not an emulation of Opera or proof of hardware behavior.

During diagnosis, script loads issued directly inside a D-Bus `Navigate`
JavaScript URL did not complete. Deferring the same probe with `setTimeout`
loaded the OEM control and runtime and exposed the Settings parse error. The
existing USB session already defers its loader. Do not infer a file-permission
or URL-hostname defect from those immediate navigation probes. Private supporting
records are `runs/native-boot-20261121/ui-diagnostic-v6.out` and the preceding
failed UI observations; raw DOM and captures remain private.

The corrected `152bc77` bundle displayed the maintenance prompt and initialized
the installed client. Navigating away from completion nevertheless caused an
unrequested status read and an error alert. A warm loopback status read took
3.78 seconds; the same request through actual Opera XHR took 3.717 seconds,
leaving little margin under the installed client's four-second timeout. These
measurements do not prove the duration of the earlier failed request. Cancellation
now performs no backend action, and installed status reads share one twelve-second
allowance across retries. The transaction request deadline and rule against
retrying writes are unchanged. Supporting records are private
`fixed-status-latency.out`, `native-status-request.out` and the completion video
under the same run directory. This setup observation is not a primary timing run.

## SM service choices and composition on v74

The exact v74 SM service-attribute parser does not recognize
`delay_before_start`; it is not a supported process-start delay setting.
This was checked in `sm_ReadConfigServicesAttributes` at `0x5f0c0` in the
SM binary with SHA-256
`d442cefe28d6cc5d914ad661ce965f6ee644588cf89d8298a2be59a10852231c`,
also matched against the running bench's file. The factory `stage_vr` profile
passes `5s` to its shell wrapper, which sleeps before publishing its readiness
flag. That delay comes from the wrapper, not an SM XML delay attribute.

Both exact normal/WCP profiles declare Android Auto's `aap_service` and `jciAAPA`
as separate startup services. The bounded Android Auto pilot suppressed only
their `autorun` attributes, then independently restored both processes with the
reviewed control bundle. Android-phone and audio behavior remain unqualified.
DAB, TV and the two Stitcher leaves are a separate
[RAM candidate](service-pilots.md#four-discontinued-or-non-na-services).
The voice-delay experiment moved a resource burst and phone/voice lifecycle
readiness later without a projection/RAM gain; its original delay is retained.

The dev.10 source consolidates service selection, wireless argument changes and
the Settings worker in one composer over verified frontend templates. The
32-case exact-original matrix covers both boards and every Base, Wireless,
Android Auto and Pandora combination. With Base off and Android Auto on, all
eight outputs match the dev.9 composer byte for byte. Per-member checks reject
missing/duplicate stanzas and existing worker/edge claims. Both boards render
before transaction preparation, so a deterministic profile conflict does not
strand recovery or block Uninstall. These are source/host checks, distinct from
the pilot observations and installed lifecycle evidence.

Dev.9 writes five-field stock baseline/Uninstall snapshots and eight-field
active snapshots. Newer maintenance must retain the baseline identity and use
the verified target package's writer and renderer for pending old work. Merely
rebinding a package path leaves the newer shell functions in memory and is
insufficient. The new active preferences are bounded named data inside the same
snapshot and `OCBP1` plan, with the existing record as transaction authority;
see [the data contract](installer-development.md#services-data-and-composition).

The v74 BusyBox AWK parser treats `value (conditional)` as a function call,
including when whitespace separates the tokens. Host AWK accepted that
concatenation. The initial dev.10 maintenance attempt on `be66b573` refused before
prepare, leaving the exact dev.9 record, selected snapshot and baseline unchanged.
Constructing these strings in explicit steps passed a RAM-only target matrix:
all 32 profile hashes matched the exact-original host outputs, Services JSON
parsed, and malformed bit/key-set/UID cases refused. The maintained preferences
and composition suite also runs through BusyBox when available. This was an
installer compatibility failure, not a primary startup timing attempt.

The subsequent `8a4a22be` upgrade retained the stock baseline and selected the
dev.10 policy, but its first Android Auto save returned `plan_failed` before
prepare. The browser sent the correct request. In the full target backend,
`preferences_package`'s final `printf` returned 1 when redirected to `/dev/null`;
the isolated writer had succeeded. The writer now captures one `package_programs`
result that verifies the full manifest and every required interpreter/composer
member before executing target code. A guarded target preparation with that
change succeeded without changing the record or activating the new snapshot.

The exact `0b5a4af7` CI bundle then passed the actual Settings saves and restarts:
Android Auto off left Pandora running; Pandora off left both Android Auto members
running; restoring each and switching Base verified the four Base member states.
The existing stock-five baseline remained unchanged through the upgrade and saves.
This is live lifecycle evidence, separate from Android-phone/audio qualification.
Private supporting records are `runs/services-pilots-20261122/verify-reviewed-dev10.out`,
`verify-reviewed-aa-restart.out`, `verify-reviewed-pandora-restart.out` and `verify-base-off-setup.out` /
`verify-base-on-setup.out`. See the [complete-preset measurements](services-comparison.md).

A fresh extraction of that exact CI payload, manually launched from the same SD,
then passed independent UI Uninstall. The new kernel loaded the original UIA/MMUI,
SM and Opera paths; all seven checked Base/Android Auto/Pandora members were
running. The exact original hashes/modes, absent original touchscreen key,
read-only physical root and removal of installed product state/helper/runtime
were verified. Existing lab access and the independent startup observer remained.
Supporting private record: `runs/services-pilots-20261122/independent-dev10-verify-stock.out`.

## Base startup tuning and SM ready-flag lifetime on v74

The dev.14 complete-preset [comparison](base-startup-tuning.md) retains three
dev.13 and three dev.14 starts with Base/Wireless/Android Auto/Pandora enabled.
The complete dev.14 preset, including 4 KiB `ffx01` read-ahead, browser logging
and service scheduling, had lower shared-window read volume. This comparison
does not isolate read-ahead's contribution. Most of the higher MemFree
corresponded to a smaller file cache, rather than an equivalent reduction in
application footprint. Unique tmpfs allocations grew 12 KiB while
listener/ignition private pages and PSS were unchanged.

Only the six children of `stage_gap2` receive the new twelve-second gate, with
their original dependencies retained. A live gate started at native 35.341 s,
reported STARTED at 47.420 s and released `stage_gap2` at 47.420 s. SM logged
unlinking its ready flag at 47.436 s. The flag is consumed on normal worker exit;
checking for a persistent flag afterwards misclassifies successful readiness.
All six children and the separately checked updater, favorites, diagnostics,
USB, navigation and JVM services reached ready states. Stock Websockets and
OEM ELF bytes remain unchanged by this increment.

The selected page applies the small authenticated browser Warn override inline
after Mazda's original logging configuration, before the logger constructor.
There is no new persistent logging file/link to strand on compatible-media
purge. Native and shell selectors record unavailable queue tuning in bounded
RAM diagnostics after publication, without a blocking stderr write. The exact
composed set is checked by the target package before prepare and again at seal,
so an unlisted entry cannot strand a physical Settings transaction.

The maintained dev.13→dev.14 upgrade retained choices and the stock-five-field
baseline. A fresh Base-off/Wireless-off kernel had read-ahead 128 KiB, stock
thread masks, Info logging and no delay gate. Compatible dev.13 media's real UI
Uninstall then restored exact as-found paths/modes and original UIA/MMUI mappings
on a fresh stock kernel, with product state/helper/runtime absent and root read
only. The temporary measurement hook and files were removed independently.
Supporting private evidence: `runs/wave-a-20261123/` (CI identity, six captures,
live state, original-media UI, stock verification and observer cleanup).


## Applied source visibility and the System script boundary

On exact v74, disabled source visibility belongs to the boot page, independently
of disclaimer bypass. Dev.15 loads the OEM System script URL and intercepts
`_initApp` before `framework.init()`. It pins the exact applied disabled entries'
`appData.isVisible` getters false, ignoring later Visible assignments. The app
name is `aharadio`, not `aha`. This retains the OEM master array and USB_A index
12; deleting/splicing rows would break consumers of those indices. The same
page-owned hook attaches the existing IntroAnimation cleanup only when requested.

Live Presto checks confirmed the applied policy, late-Visible refusal and the
actual Entertainment list. During compatible dev.14 purge, a fresh dev.15 page
still loaded `file:///jci/gui/apps/system/js/systemApp.js`, connected MMUI and
kept DVD hidden with USB_A index 12. It was in IntroAnimation at eight seconds;
later Opera disappeared and the CMU rebooted without the planned explicit
restart. The preceding fault was not captured. This does not qualify a fully
usable manual page reload, nor establish the stock Websocket fatal-close branch
as the cause. Fresh stock restoration passed. See the [evidence and limits](services-expansion.md#build-controls-and-restoration).

Source/disassembly findings keep sparse VUI omission separate: this firmware's
`svcjcivui.so` ServiceInit opens `/jci/vui/vui_config.xml` directly; the presence
of a `-cfgxml` parser does not establish that this startup path uses it. The
planned sparse MMUI/VUI experiment is deferred until actual consumers and
retained destinations qualify. Private supporting records are
`runs/wave-a-20261123/wave-b-plan-review.md` and `runs/wave-b-20261123/`.
