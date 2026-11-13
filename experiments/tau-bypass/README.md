# TAU-free silent bench UI — firmware 55

Actual result on 55.00.750B / cmu150_NA: Mazda's existing audio-manager
enable API unlocks FM Now Playing and the Entertainment source list without
a connected TAU. No binary/JS/config patch or service restart was needed.

## Mechanism

The shipped /usr/bin/audioMgr.lua has a built-in test-menu operation for
enable/disable (source lines3067–3097, preserved Lua bytecode listing).
Its enable implementation (7729–7880) runs control hooks, changes
g_audioEnable, and sends enableEvent to HMI and app clients. It does not
report a fictitious TAU connection. Native MMUI receives this notification as
StatusUpdateAudioEnabled1479 and allows normal source activation.

Live introspection establishes:
- Bus: unix:path=/tmp/dbus_hmi_socket
- Service: com.xsembedded.service.AudioManagement
- Object: /com/xse/service/AudioManagement/HmiMode
- Method: com.xsembedded.ServiceProvider.Request
- Two input strings: operation and JSON arguments; one result string.

Read status with operation enableStatus and {}. Enable with operation enable and
{"enable":true}; restore disabled with {"enable":false}. Resolve the current
service owner and read/save the initial status before changing it. The experiment
bound the actual owner :1.26, which is historical, never a reusable identity.

The actual command recipe and undo are saved under the private run as enable.sh
and disable.sh. Future calls must bind the current service owner. Use the existing
authenticated bench Session; do not replay historical unique bus identities.
The handler replies before finishing its state update, so a method return alone
is not success: verify enableStatus and actual UI/native behavior afterward.

## Actual trial

1. Saved original enableStatus=false and source-backed argument/undo contract.
2. One enable(true); readback true; MMUI logged Audio is Enabled.
3. Ordinary Home menu input reached fmradio.NowPlaying, visible FM screen.
4. Selecting its source button opened system.Entertainment, visible source list.
5. One enable(false); readback false and MMUI Audio is Disabled.
6. Home returned; fresh readback false, physical root RO, authenticated root55.
All owned serial/camera helpers closed. No reboot, installed file edit or
persistent startup automation. Normal UI selection may update normal last-source
state; we do not claim every user setting was restored.

Two initial navigation attempts landed in Applications/Compass because Home
selection behavior was assumed. They are preserved. A fresh Home photo established
Communication focus, then LEFT+ENTER reached Entertainment. Early misleading
photo filenames entertainment.jpg and actual-entertainment.jpg belong to those
navigation attempts; use working-now-playing.jpg and sources.jpg for success.

## Limits and next use

This is a deliberate, transient BENCH override of audio readiness, not a complete
TAU emulator or a car modification. Radio reception, actual sound, Bluetooth/USB/
CarPlay playback and cold-start/resume behavior were not tested. The FM screen
has no station data without a tuner. Do not add speakers for the user's scope.
No persistence across reboot/ACC or resistance to later disable notifications is
claimed. Prefer explicitly invoking it for silent UI tests, with readback,
instead of installing an always-on startup patch.

Evidence: runs/open-connect-tau-bypass/result.json, enable-source/result.bin,
api-introspect/result.bin, enable/result.bin, enter-confirmed/result.bin,
sources/result.bin, disable/result.bin, final/result.bin and actual photos.
This supersedes the earlier recommendation to buy a TAU merely to open menus.
