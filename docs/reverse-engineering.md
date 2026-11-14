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
configuration selection as well as optional code. No early selector or disable
mechanism has been tested on the CMU. Current source findings:

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

Read-only source work identified a **normal-boot insertion point before the
service manager**, not an installed recovery mechanism:

- /usr/bin/autostart:65–69 sources start_normal_mode.sh, launches the Logger, then
  runs SM with an explicit configuration argument. Selection immediately before
  line 67 can precede all three. The existing normal/test/RF branches must retain
  their meanings; stock test mode is not Open Connect safe mode.
- init_cmu's startup graph calls the data_persist mount before autostart:
  mount record 0x24a70 → autostart record 0x24bb0, following the same execution
  chain. The mount handler at 0xb1a8 calls mount; fluxProcess at 0xc450 advances
  through the chain. This proves ordering of the **attempt**, not mount success.
  Inspect the actual mount/device and owned files before consuming persistent
  control. Missing storage must select baseline without waiting indefinitely.
- start_normal_mode.sh:49–50 launches /data_persist/dev/bin/autorun **in the
  background**. Its completion is not ordered before the Logger or SM. It is not
  a suitable hook for selecting their configuration. stage_1.sh is only an empty
  shell script and, as an SM service, is too late to choose SM's graph.

The actual SM distinguishes stopping watchdog feeding from disabling the watchdog.
A critical-service exit reaches SMHEALTH_StopWatchdog at 0x1bb28; its notice goes
to /dev/console (0x27e2c–0x27e34), then SM_WD_Stop calls stopFeeding at 0x311cc.
This is compiled fault behavior, not a fault we induced.

sm.conf:11–19 configures fault reports, including log-save.sh and sync.
log-save.sh:13/97/127 archives running logs into /data_persist/log/saved_logs.
Those archives may explain a failure, but absence is not evidence of a clean
power loss: capture can fail or be interrupted, and archives are rotated.
The inspected kernel messages, standard watchdog status files and filtered NV
key names supplied no usable reset cause. This is a bounded negative result,
not proof that the hardware exposes none.

Neither generic SM completion nor the init shutdown handler is a clean-end
classifier. Both sm_stop and sm_forceStop flush the event log and post the same
shutdown semaphore (0x6dd60 / 0x6d508). No verified power-loss/normal-end classifier
was found. A health event, shutdown callback or missing crash log must therefore
not replenish the proposed retry budget.

**Next proof:** a minimal synchronous normal-branch selector with baseline as its
default; first exercise a no-change generation and unavailable/corrupt control.
No optional service, native or JS behavior belongs in that first experiment.
The selector, bounded execution, durable attempt accounting, cold/ACC behavior
and automatic fallback still need qualification. See [the implementation order](extension-architecture.md#next-proof-and-implementation-order).

Private captures and derived addresses: runs/startup-recovery-research/result.json
and supporting-slices.txt. New sources have exact before/after identity, byte count,
MD5 and CRC agreement; all capture ports closed. No device write, reset, signal
or watchdog operation occurred. Source SHA256 values:

| Source | SHA256 |
| --- | --- |
| autostart | b91b2c5a5b7d036860321da730ad571dbae9164d2632946f6566238c3cd42e31 |
| start_normal_mode.sh | 6a020f2b9a92406510519820cfdee004fd4b9ef41a0ab212eb2727ffe8db80a2 |
| sm | cd1104d9b0a28dcce361520de203c1180b2e6f81d939c4223a369fd66a055f0c |
| log-save.sh | a1beb68337f7c4e334b2510f0c9ad6992acebb8a7533a4022b0fbb6678428c62 |
| init_cmu (previous capture) | a5c3b821236f3993b15021a80130df4e33b359beb7722a8a6a6fa9a74cf455bb |
