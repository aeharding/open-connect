# Snap startup trial and loading-asset finding — 2026-11-13

One recorded startup passed with stock native and the single-file Snap JS
variant. Source identity 64785:1606:1293:93955:755:1018:3015:2; native original
64785:9457:1433953535:454142:755:1018:3015:1. Root55/NA/read-only,
new boot and independent JS/native verification passed. It remains installed
for observation; originals and independent undo retained.

Three focused host checks passed before publication. Real OEM Transitions,
TransitionsGen and BaseApp executed under host DOM stubs: precise
Disclaimer-to-Home Snap exception; ordinary asynchronous completion; no watchdog
completion; logo disposal afterward. Other destination transitions untested.
Original comparison was undone and holds cleaned before this successor.

Actual CMU timeline:
- 25.894 IntroAnimation -> Disclaimer Snap
- 26.232 Disclaimer -> HomeScreen Snap
- 26.361 MainMenu transition complete
- 26.369 TRANLOGOEND surface hidden and DisposeIntroVideo event received
- 26.493 ending surface unregistered
No transition watchdog firing observed. This is log ordering, not pixel latency.

Visual result: user still sees a flash. The 5FPS contact sheet confirms a frame
with live clock/background but absent menu icons, followed by icons arriving.
No visible warning in the inspected interval. This does NOT establish seamless
startup or improved subjective appearance over the comparison.
The changed transition removes the 600ms fallback, but first-menu paint remains.

Exact newly read MainMenuTmplt delegates endTransitionTo to MainMenuCtrl.
MainMenuCtrl.endTransitionTo only adds Visible to the label; constructor already
builds icons and selects default focus. Its CSS has 200ms focus/glow/label
transitions and external bitmap icon images. Missing-icon frame cause remains
unresolved: source does not establish bitmap readiness or compositor frame
ordering. Do not call it inevitable OEM behavior or add arbitrary delays.

Spinner investigation:
- Service configuration explicitly maps quicktranlogo to splashplayer -l using
  /jci/resources/LoopLogo.ivf; normal tranlogo uses TranLogo.ivf.
- Exact LoopLogo exported read-only, strict whitespace-only base64 decoded;
  pre/post identity and MD5/CRC verified. 151428B, MD5
  8980b1c0c412bc4cf03ba57cc3b81829, CRC2343846244.
- Decoded VP8 800x480 asset shows shimmering Mazda emblem, NOT a circular
  spinner. This corrects any assumption equating QuickStartLoop with a spinner.
- System55 JS contains list loading callbacks; no startup-spinner identification
  established. User was asked where their observed spinner appears.
- QuickStartLoop native state routing remains described in the preceding
  approach comparison; it was not exercised by this trial.

Evidence: runs/open-connect-snap55/boot-C/{manifest.json,final.json,
comparison-result.json,camera.mkv}; visual/{handoff-27-to-37.jpg,
lifecycle-lines.bin,extraction.json}; loading-source/{asset-result.json,
loop-contact.jpg,MainMenuTmplt.js,MainMenuCtrl.js,MainMenuCtrl.css,
menu-result.json,menu-control-result.json,menu-css-result.json}.
Full OEM files remain private. Host checks/source pins and cleanup in same run.
No native patch, service manipulation, mask, spinner injection or forced event
was used. New source/asset work after trial was read-only.
