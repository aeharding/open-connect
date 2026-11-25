# Wireless CarPlay

Connect your iPhone to CarPlay without plugging in a USB cable.

**Impact:** Neutral — no measured startup or free-RAM gain is established.<br>
**Trade-off:** Uses Wi-Fi for CarPlay and requires compatible hardware and phone pairing. Wired CarPlay remains available when it is off.<br>
**Evidence:** Earlier builds have connection and restart checks. [Performance evidence](performance.md) records wireless configurations, not an isolated wireless-enable speed or RAM saving.

Open Connect enables Mazda’s built-in wireless connection on compatible hardware. It starts **Off**. Units with factory wireless CarPlay show **factory enabled** and need no change here.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/wireless-enable.png" alt="Open Connect Wireless CarPlay enable confirmation." width="800" height="480"></div>
  <figcaption>Enable Mazda’s built-in wireless CarPlay through Open Connect.</figcaption>
</figure>

<span id="connect-an-iphone"></span>

## Setup

If Open Connect shows **factory enabled**, start at step 3.

1. Open **<span class="oc-nav-path" data-walkthrough="wireless-setup">Mazda Settings → System → Open Connect → CarPlay &amp; Android Auto</span>**. Turn on **Wireless CarPlay** and confirm **Enable**.
2. Let Mazda Connect shut down completely, then start it again.
3. Open **<span class="oc-nav-path" data-walkthrough="wireless-wifi">Mazda Settings → Devices → Wi-Fi</span>** and select **Apple CarPlay**.

    <figure class="oc-screen">
      <div class="oc-screen-frame"><img src="assets/guide/wireless-mode.png" alt="Mazda Wi-Fi mode list with Off and Apple CarPlay options." width="800" height="480" loading="lazy"></div>
      <figcaption>Step 3: select Apple CarPlay in Mazda’s Wi-Fi settings.</figcaption>
    </figure>

4. Enable Wi-Fi and Bluetooth on your iPhone. Pair it with Mazda Connect over Bluetooth and accept the wireless CarPlay prompt if shown.
5. Open **<span class="oc-nav-path" data-walkthrough="wireless-connect">Mazda Settings → Devices → Apple CarPlay</span>**, select your iPhone and choose **Connect**.

If **Connect** stays greyed out for an already paired iPhone, remove that phone’s pairing and pair it again. Leave other phones paired.

The North American Wi-Fi menu offers **Off** and **Apple CarPlay**. Hotspot switching is not included in this setup.

<span id="disable-or-remove"></span>

## Turning it off

If you enabled wireless through Open Connect, clear **Wireless CarPlay** and confirm **Disable**. Your unit’s original wireless availability returns on the next full startup. Saved phone pairings and Wi-Fi preferences stay in place.

If you also enable [Startup optimizations](services.md#base-optimizations), Mazda Navigation starts about 20 seconds later.

## Testing

This is still in testing for North American version **74.00.324**. Bench tests include connection and reconnection after full restarts. Real-car audio, physical controls and reliability after long periods parked remain unqualified. No public download is available yet.

[Back to Settings](settings.md) · [Wireless technical notes](cmu/wireless-carplay.md)
