Workspace-only UVC exposure control; hardware owner t14 only.
Existing tool: https://github.com/jtfrey/uvc-util
Pinned source8110da7025c95eea3096a7181af9a46c0cc7ac37 in vendor/ with MIT license
and exact URL/hash records source-provenance.json. Built with installed clang,
Foundation and IOKit; no install/driver/extension/TCC change. Native macOS
AVFoundation custom duration/ISO/bias APIs are unavailable in current SDK.
Binary uvc-util SHA256 a35369c8776c49baf27d5449de27ff2e4535da8980a954114005f33720c7230d.

Operator verified unique046d:0825, serial1AD54210, location0x08310000 and read-only
query succeeds. Originals: AE8, exposure330, brightness128. AE bitmap9 supports
manual1; exposure range1..10000, step1. Raw originals/identity:
runs/20261113T005731-0600-t14-webcam-control/ (workspace-relative).

Read-only query (camera capture closed; record exit/stdout/stderr):
 hc exec --timeout 20 --cwd /Users/aeharding/mazda-cmu-bench experiments/webcam-control/uvc-util -V 0x046d:0x0825 -c -S auto-exposure-mode -g auto-exposure-mode -S exposure-time-abs -g exposure-time-abs -S brightness -g brightness

Authorized one trial, after fresh baseline: manual1/exposure82, brightness untouched:
 hc exec --timeout 15 --cwd /Users/aeharding/mazda-cmu-bench experiments/webcam-control/uvc-util -V 0x046d:0x0825 -s auto-exposure-mode=1 -s exposure-time-abs=82 -g auto-exposure-mode -g exposure-time-abs -g brightness
Capture fresh original with unchanged bench.py camera settings; read controls again
and compare visible text. No raster processing or physical movement; no UI repeat.
If worse/unclear, restore in TWO separate calls so AE8 is attempted if first fails:
 hc exec --timeout 15 --cwd /Users/aeharding/mazda-cmu-bench experiments/webcam-control/uvc-util -V 0x046d:0x0825 -s auto-exposure-mode=1 -s exposure-time-abs=330
 hc exec --timeout 15 --cwd /Users/aeharding/mazda-cmu-bench experiments/webcam-control/uvc-util -V 0x046d:0x0825 -s auto-exposure-mode=8 -g auto-exposure-mode -g exposure-time-abs -g brightness
Observed result: trial read back1/82/128; after fresh capture it read1/87/128.\nThe fresh frame was clearer, so t14 retained manual1/exposure87/brightness128.\nRequested82 and observed87 are distinct; cause of the change was not assigned.\nOriginal8/330/128 is preserved with the exact restore sequence above.
No system permissions, device seize/reset, CMU changes or scheduled work.
