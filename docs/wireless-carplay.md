# Wireless CarPlay

Connect your iPhone to CarPlay without plugging in a USB cable. Open Connect enables Mazda’s built-in wireless connection on compatible hardware.

**<span class="oc-nav-path" data-walkthrough="wireless-carplay">Mazda Settings → System → Open Connect → CarPlay &amp; Android Auto → Wireless CarPlay</span>**

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-wireless-carplay.png" alt="Wireless CarPlay highlighted and enabled in the CarPlay and Android Auto submenu." width="800" height="480"></div>
  <figcaption>Wireless CarPlay highlighted (dev.19); shown on, with a fresh-install default of Off unless factory enabled.</figcaption>
</figure>

<span id="testing"></span>

- **Default**: <span class="oc-default oc-default--off">Off</span>, unless the unit has factory wireless CarPlay. **factory enabled** units need no change here.
- **Startup & RAM impact**: **Neutral** — no isolated wireless-enable startup or RAM saving is established.
- **Trade-offs & boot implications**: Uses Wi-Fi for CarPlay and requires compatible hardware and phone pairing. Wired CarPlay remains available when this setting is off. With [Startup optimizations](startup-optimizations.md) on, Mazda Navigation starts about **20 s later**, even if no phone connects.
- **Applies**: Saved automatically; takes effect on the **next full Mazda Connect startup**. See [restart guidance](settings.md#apply-changes).
- **Evidence & limits**: [Performance evidence](performance.md) records wireless configurations, not an isolated enable-toggle benefit. Earlier builds have connection and full-restart reconnection checks; real-car audio, physical controls and long-parked reliability remain unqualified. Dev.19 UI bench captures on **74.00.324A NA**; real-car qualification and matched dev.19 benchmarks remain pending. No public download yet.

<span id="connect-an-iphone"></span>

## Setup

If Open Connect shows **factory enabled**, start at step 3.

1. Open **<span class="oc-nav-path" data-walkthrough="wireless-setup">Mazda Settings → System → Open Connect → CarPlay &amp; Android Auto</span>**. Turn on **Wireless CarPlay** and confirm **Enable**.
2. Let Mazda Connect shut down completely, then start it again.
3. Open **<span class="oc-nav-path" data-walkthrough="wireless-wifi">Mazda Settings → Devices → Wi-Fi</span>** and select **Apple CarPlay**.

    <figure class="oc-screen">
      <div class="oc-screen-frame"><img src="assets/guide/wireless-mode.png" alt="Mazda Wi-Fi mode list with Off and Apple CarPlay options." width="800" height="480" loading="lazy"></div>
      <figcaption>Step 3: select Apple CarPlay in Mazda’s Wi-Fi settings (retained dev.8 capture).</figcaption>
    </figure>

4. Enable Wi-Fi and Bluetooth on your iPhone. Pair it with Mazda Connect over Bluetooth and accept the wireless CarPlay prompt if shown.
5. Open **<span class="oc-nav-path" data-walkthrough="wireless-connect">Mazda Settings → Devices → Apple CarPlay</span>**, select your iPhone and choose **Connect**.

If **Connect** stays greyed out for an already paired iPhone, remove that phone’s pairing and pair it again. Leave other phones paired.

The North American Wi-Fi menu offers **Off** and **Apple CarPlay**. Hotspot switching is not included in this setup.

<span id="disable-or-remove"></span>

## Turning it off

If you enabled wireless through Open Connect, clear **Wireless CarPlay** and confirm **Disable**. Your unit’s original wireless availability returns on the next full startup. Saved phone pairings and Wi-Fi preferences stay in place.


[Wireless technical notes](cmu/wireless-carplay.md)

[Back to Settings](settings.md)
