# Show CarPlay on connection

The dev.18 candidate adds **Show CarPlay on connection** under **Mazda Settings →
System → Open Connect**. It defaults to **Factory behavior**. Choose
**Automatically show**, confirm, then restart Mazda Connect to apply the change.

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
