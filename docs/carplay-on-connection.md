# Show CarPlay on connection

Open CarPlay when your iPhone connects, including after startup and reconnection.

**<span class="oc-nav-path" data-walkthrough="carplay-on-connection">Mazda Settings → System → Open Connect → CarPlay &amp; Android Auto → Show CarPlay on connection</span>**

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-show-carplay-on-connection.png" alt="Show CarPlay on connection highlighted in the CarPlay and Android Auto submenu, with Factory displayed." width="800" height="480"></div>
  <figcaption>Show CarPlay on connection highlighted (dev.19), showing the Factory default.</figcaption>
</figure>

- **Default**: <span class="oc-default oc-default--off">Factory behavior</span> (**Factory** in the list).
- **Startup & RAM impact**: **Neutral** — no isolated startup gain is established. Source-accounted own file pages changed **0 B** (`carplay.js` +4 KiB offset by `settings.js` 32→28 KiB); matched timing and PSS measurements remain ahead.
- **Trade-offs & boot implications**: CarPlay may replace your current screen on connection. Input, calls, voice control, Settings and maintenance dialogs take priority; Mazda retains screen and reverse-camera control.
- **Applies**: Saved automatically; takes effect on the **next full Mazda Connect startup**. See [restart guidance](settings.md#apply-changes).
- **Evidence & limits**: Offline replays and wireless bench checks cover **74.00.324A NA**. One intermittent native acceptance miss occurred with Startup optimizations on; subsequent reconnects passed. Wired auto-selection, live call/Siri/reverse interaction and real-car use remain unqualified. See [Performance evidence](performance.md); matched dev.19 benchmarks remain ahead. No public download is available.

## Options

| Choice | List label | Behavior |
| --- | --- | --- |
| **Factory behavior** | Factory | Uses Mazda’s original screen-selection behavior. |
| **Automatically show** | Auto | Requests CarPlay when your iPhone connects. |

Select **Automatically show**, confirm **Enable**, then let Mazda Connect shut down fully before restarting. Select **Factory behavior** and restart to restore Mazda’s behavior. Updates retain your choice; upgrading from dev.17 starts with it off.

This supports wired CarPlay and an already configured wireless connection. Use [Wireless CarPlay](wireless-carplay.md) to enable wireless availability.

You can return to Mazda Connect at any time. Open Connect makes at most one request per connection; a pending request expires after 15 seconds. It does not repeatedly pull you back into CarPlay. Bench wireless selection worked from Mazda’s main screen and Navigation, with deliberate suppression in Settings and a clean Long-Home return.

[Back to Settings](settings.md)
