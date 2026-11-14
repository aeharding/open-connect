# Mazda Connect findings

Evidence is for **55.00.750B North America**. These are current engineering
findings, not a recipe to replay old trial payloads. Detailed original records
remain in [Git history](https://github.com/aeharding/open-connect/tree/1e8efdfea264e4b31704d9e378da1f1b3be0ced6/docs/history).

## Silent Entertainment without a TAU

Mazda's Audio Manager test-menu API provides enableStatus and enable(boolean).
The Lua handler owns audio enable state; SYSTEM startup policy can subsequently
turn it off when the TAU is absent. Service availability alone is therefore not
a sufficient startup activation boundary.

The [bench helper](../src/open_connect/bench.py) uses that API. Live setup,
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

The [native prototype](../experiments/disclaimer-native/) bypassed the observed
warm Intro route. Early intro-player disposal caused a black interval. The
[paired renderer hook](../experiments/intro-handoff/) defers DisposeIntroVideo
until renderer completion; the sampled long gap disappeared, but a dim transition
remained. Independent undo and restored-original startup passed. This does not
establish cold ACC, every resume branch or a seamless sub-frame transition.

The separate upstream-derived comparison uses a transparent NoCtrl template and
native Yes; the local Snap variant still showed a handoff. It is excluded from
AGPL distribution under its noncommercial license; see [THIRD_PARTY.md](../THIRD_PARTY.md).

## Loaded libraries and read-only remount

Replacing a still-mapped native library caused an EBUSY read-only remount failure.
Keeping same-filesystem hardlink holds through apply, undo and loaded-module
lifetime resolved the observed case. Restoring the file on disk does not unload
modified code: verify a restored-original startup and mapping before releasing
its holds. See [mapped publication](../experiments/mapped-publication/README.md).

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
  [probe](../experiments/optional-loader/README.md) hooks its final return at
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
