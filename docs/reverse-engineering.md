# Mazda Connect findings

Evidence is for **55.00.750B North America**. These are current engineering
findings, not a recipe to replay old trial payloads. Detailed original records
remain in [Git history](https://github.com/aeharding/open-connect/tree/1e8efdfea264e4b31704d9e378da1f1b3be0ced6/docs/history).

## Silent Entertainment without a TAU

Mazda's Audio Manager test-menu API provides enableStatus and enable(boolean).
The Lua handler owns audio enable state; SYSTEM startup policy can subsequently
turn it off when the TAU is absent. Service availability alone is therefore not
a sufficient startup activation boundary.

The [bench helper](https://github.com/aeharding/open-connect/blob/main/src/open_connect/bench.py) uses that API. Live setup,
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

The [native prototype](https://github.com/aeharding/open-connect/tree/main/experiments/disclaimer-native/) bypassed the observed
warm Intro route. Early intro-player disposal caused a black interval. The
[paired renderer hook](https://github.com/aeharding/open-connect/tree/main/experiments/intro-handoff/) defers DisposeIntroVideo
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
its holds. See [mapped publication](https://github.com/aeharding/open-connect/blob/main/experiments/mapped-publication/README.md).

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

The [architecture proposal](extension-architecture.md) now covers service and
configuration selection as well as optional code. A one-shot early selector has
now passed the warm-boot test below; the optional loader remains unqualified.
Current source findings:

- index.html:33 loads ../../data/integration/developer_mode_GuiConfig.js before
  Utility/BaseApp/GuiFramework and framework.init(). It resolves to /data/integration,
  whose parent was mode 0777; the script was absent. Utility.js:66–94 handles script
  onload only, not onerror. This is a candidate bootstrap slot, not readiness proof.
- sm.conf:145–169 starts MMUI and Opera through separate dependency sets. Current
  /data resolves to /tmp/mnt/data on /dev/ffx01p4; data_persist is separate.
  Current availability does not establish availability at an earlier boot hook.
- svcjcimmui.so constructs UIA priority/context records before invoking loaders
  (0x2e08–0x2f50). It is not a neutral plugin registry. The host-built
  [probe](https://github.com/aeharding/open-connect/blob/main/experiments/optional-loader/README.md) hooks its final return at
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
Captures were read-only with known completion and closed ports; no OEM write or
reboot occurred. Source ordering is not proof of runtime fallback or cold startup.

## Startup selection and reset evidence

**Main learning:** a consumed trial can fall back without a working GUI or
optional runtime. Mazda's existing watchdog performs the reset; Open Connect
must choose what runs afterward.

The [one-shot selector](https://github.com/aeharding/open-connect/tree/main/experiments/boot-selection)
runs in /usr/bin/autostart before normal-mode setup, the Logger and Service
Manager (SM). It consumes and flushes a trial record before choosing a fixed
configuration. A spent record selects Mazda's original service configuration.

| Actual bench test | Observed result | Limit |
| --- | --- | --- |
| Two ordinary warm boots | Trial configuration once, OEM configuration next; running SM arguments verified | Selection proof, not a feature-health policy |
| SIGSEGV to one identity-checked MMUI process | SM stopped feeding the watchdog; automatic reset booted the baseline configuration | External process fault, not a bug in a modified library |
| Trial-only JS infinite loop | Native GUI Manager closed Opera after missing heartbeats; watchdog reset returned to the original entry page | Reconciled from the saved crash archive and fresh target checks; original serial observer stayed incomplete |
| Supply output off/on after a flushed consumed record | Record survived; fresh root access and read-only root returned | One completed write in normal runtime, not a cut during early selection or rename/fsync |

These tests retained the existing comparison JS and original native library.
“Baseline” here means the pre-existing bench configuration, not an entirely stock
unit. Independent undo removed the startup hook after the warm-boot and native
and JS crash trials. The power-cut test ran with the hook already removed.

The actual power interruption was **6.964 seconds between output requests**.
The DPS150's voltage/current settings were identical before and after; no
voltage-setting command was sent. This tests full supply loss, not ACC behavior.

### What causes a reset?

~~~mermaid
flowchart TD
    JS["JavaScript event-loop hang"] --> Miss["Native monitor misses JS heartbeat"]
    Miss --> Close["Opera closes"]
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

### Implications for recovery

- **Select early.** init_cmu attempts the data_persist mount before autostart;
  still verify the actual mount. /data_persist/dev/bin/autorun is backgrounded
  inside start_normal_mode.sh and cannot reliably choose SM's configuration.
- **Consume before effects.** Missing, invalid or spent control must select
  baseline. An observed ready screen must not automatically replenish attempts:
  faults can happen later.
- **Do not guess reset causes.** Saved crash logs can help diagnose a failure, but
  missing logs do not prove battery loss. No reliable reset-cause or clean-end
  classifier has been established.
- **Bound bootstrap work.** The parent uses a five-second timeout without an
  inherited stdout pipe. Host tests cover invalid control, failed flushes and a
  surviving child. Uninterruptible filesystem I/O remains outside that guarantee.

Still open: interrupted early-boot writes, repeated power cuts, ACC/resume,
persistent retry/health policy, and service/logging/native features selected
through this same boundary. These results do not establish recovery from a
broken baseline, kernel or selector.

Private evidence: runs/early-selector/result.json,
runs/native-fault-trial/result.json, runs/js-hang-trial-v2/result.json,
runs/power-cut-trial/result.json and
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
