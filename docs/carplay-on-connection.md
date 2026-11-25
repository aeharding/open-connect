# Show CarPlay on connection

Open **Mazda Settings → System → Open Connect → CarPlay & Android Auto → Show CarPlay on connection**. The list shows **Factory** or **Auto**. It defaults to **Factory behavior**. Choose **Automatically show**, confirm, then restart Mazda Connect.

**Impact:** Neutral — no measured startup or free-RAM gain is established.<br>
**Trade-off:** CarPlay can replace your current screen when your iPhone connects. Your input, calls and Mazda’s safety controls take priority.<br>
**Evidence:** Offline replays and bench wireless checks on 74.00.324A NA; source-accounted own file-page delta is 0 B (`carplay.js` +4 KiB offset by `settings.js` 32→28 KiB). Matched [Performance evidence](performance.md) timing and PSS measurements remain ahead.

With this option enabled, Open Connect requests CarPlay when your iPhone connects,
including after startup and after disconnecting and reconnecting. It supports
wired CarPlay and an already configured wireless connection. Use the separate
[Wireless CarPlay](wireless-carplay.md) option to enable wireless availability.

You can return to Mazda Connect at any time. Open Connect makes at most one
request for each connection; it does not repeatedly pull you back into CarPlay.
Calls, voice control, Settings, maintenance dialogs and deliberate input take
priority. A pending request expires after 15 seconds. Mazda still controls
screen ownership, reverse-camera priority and whether the request succeeds.

Choose **Factory behavior** and restart to restore Mazda's original selection
behavior. Updates retain your choice; upgrading from dev.17 starts with it off.

On the bench, wireless auto-selection succeeded from Mazda Home and OEM
Navigation (`emnavi/Active`) with deliberate suppression in Settings and clean
Long-Home return. One intermittent post-cue native acceptance miss was observed
on the headless bench with Startup optimizations enabled (subsequent reconnects
passed). Wired CarPlay, live call/Siri/reverse interaction, real-car testing
and matched timing/RAM benchmarks remain ahead.
