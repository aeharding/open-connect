# Show CarPlay on connection

Open **Mazda Settings → System → Open Connect → CarPlay & Android Auto → Show CarPlay on connection**. The list shows **Factory** or **Auto**. It defaults to **Factory behavior**. Choose **Automatically show**, confirm, then restart Mazda Connect.

**Impact:** Neutral — no measured startup or free-RAM gain is established.<br>
**Trade-off:** CarPlay can replace your current screen when your iPhone connects. Your input, calls and Mazda’s safety controls take priority.<br>
**Evidence:** The connection-selection behavior has offline checks. [Performance evidence](performance.md) has no isolated autoshow timing or RAM result; final dev.18 pre-car measurements will be added after the benchmark work.

With this option enabled, Open Connect requests CarPlay when your iPhone connects,
including after startup and after disconnecting and reconnecting. It works with
wired CarPlay and with an already configured wireless connection. Use the separate
[Wireless CarPlay](wireless-carplay.md) option to enable wireless availability.

You can return to Mazda Connect at any time. Open Connect makes one request for
each connection; it does not repeatedly pull you back into CarPlay. Calls, voice
control, Settings, maintenance dialogs and deliberate input take priority. A
pending request expires after 15 seconds. Mazda still controls screen ownership,
reverse-camera priority and whether the request succeeds.

Choose **Factory behavior** and restart to restore Mazda's original selection
behavior. Updates retain your choice; upgrading from dev.17 starts with it off.

This candidate has offline checks. Live screen selection, phone-call interaction,
browser-reload behavior, timing and RAM qualification are pending bench release.
