# Settings

Change your preferences in Mazda’s own menus. Choices save automatically.

Open **<span class="oc-nav-path" data-walkthrough="open-connect">Mazda Settings → System → Open Connect</span>**, just above **About**.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/settings.png" alt="Open Connect settings showing Touchscreen While Driving, Startup disclaimer, Startup optimizations, CarPlay and Android Auto, and Audio sources." width="800" height="480"></div>
  <figcaption>Open Connect settings (0.3.0-dev.19).</figcaption>
</figure>

<span id="change-a-preference"></span>

## Choose a setting

The list follows this order:

1. [**Touchscreen While Driving**](touchscreen.md): **Allow** or **Factory Default**.
2. [**Startup disclaimer**](disclaimer.md): **Skip** or **Show**.
3. [**Startup optimizations**](services.md#base-optimizations): reduce background logging and unused services. Off by default.
4. **CarPlay & Android Auto**:
    - [Wireless CarPlay](wireless-carplay.md)
    - [Show CarPlay on connection](carplay-on-connection.md): **Factory** or **Auto**
    - [Android Auto](services.md#android-auto)
5. [**Audio sources**](services.md#audio-sources): DVD, Pandora and SiriusXM.
6. [**Developer options**](developer-options.md): UART, SSH and Import public key.
7. [**Uninstall**](uninstall.md)
8. [**About**](about.md)

Updates keep your choices.

## Impact at a glance

These comparisons describe enabling Startup optimizations or disabling an unused integration. Other rows describe choosing the feature. **Neutral** means no measured startup gain is established. **Faster** and **Slightly faster** are reserved for measured gains; they do not promise faster startup than stock.

| Setting | Startup speed | Free RAM (bench) | Trade-off |
| --- | --- | --- | --- |
| Touchscreen While Driving | Neutral | Not measured separately | Touch stays available while moving. |
| Startup disclaimer | Neutral | Not measured separately | The startup warning is skipped. |
| Startup optimizations | Faster in earlier wired tests | +9.9 MiB minimum MemFree; +2.58 MiB ending, dev.7 | Aha, Stitcher, DAB and TV stop; Mazda Navigation starts about 20 s later with Wireless CarPlay on. |
| Wireless CarPlay | Neutral | No isolated gain established | Requires compatible hardware and phone pairing. |
| Show CarPlay on connection | Neutral | Not measured separately | CarPlay may replace your current screen on connection. |
| Android Auto off | Neutral | Not measured separately | Built-in Android Auto becomes unavailable. |
| DVD off | Neutral | Not measured separately | DVD video disappears from Sources; CDs still work. |
| Pandora off | Neutral | +3.2 MiB minimum MemFree, dev.6 | Mazda’s Pandora integration disappears from Sources; CarPlay apps still work. |
| SiriusXM off | Neutral | Not measured separately | Satellite radio and SiriusXM data become unavailable. |
| Developer options | Neutral | Not measured separately | Gives direct access to the head unit; changes you make can affect maintenance. |

The [Performance evidence](performance.md) records the configurations and limits. Startup optimizations was called **Base optimizations** in those tests: dev.7’s wired dashboard was about 3.8 s earlier with it on. Pandora’s timing difference was below camera resolution. These are earlier bench results, not dev.19 measurements; do not add their RAM figures together. Free RAM here means **MemFree**, not memory available to apps. Final dev.18 pre-car timing and RAM results will refresh this table after the benchmark work is complete.

## Apply changes

Changes take effect on the **next full Mazda Connect startup**. Turn the ignition off and let the system shut down completely before starting again. A quick off/on may resume the same session.

**restart needed** means a choice is saved but not active yet. If a save cannot be confirmed, reopen Open Connect and check the choice before trying again.

The guide describes **0.3.0-dev.19**, still in testing on North American version **74.00.324**. Real-car checks remain; no public download is available yet.
