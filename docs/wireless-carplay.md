# Wireless CarPlay

Connect your iPhone to CarPlay without plugging in a USB cable. Open Connect enables Mazda’s built-in wireless connection on compatible hardware.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="wireless-carplay">Open Connect → CarPlay &amp; Android Auto</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd><span class="oc-default oc-default--off">Off</span></dd>
  </div>
  <div>
    <dt>Impact</dt>
    <dd>+2.2 pp CPU vs stock</dd>
  </div>
  <div>
    <dt>Applies</dt>
    <dd>Next full startup</dd>
  </div>
</dl>

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-wireless-carplay.png" alt="Wireless CarPlay highlighted and enabled in the CarPlay and Android Auto submenu." width="800" height="480"></div>
  <figcaption>Wireless CarPlay highlighted (dev.19); shown on, with a fresh-install default of Off unless factory enabled.</figcaption>
</figure>

## Notes

<p>Default is <span class="oc-default oc-default--off">Off</span>, unless your unit already has <strong>factory enabled</strong> wireless CarPlay (those units need no change here).</p>

<p><strong>Bench results (dev.20, n=1 cold boot with an iPhone connected):</strong> about <strong>+2.2 percentage points boot CPU</strong> (+3.4 points settled) and negligible available-RAM proxy change (~0 MiB) versus Stock, with the main screen at 34.8 s (small timing/CPU differences may be run variation). See <a id="testing" href="performance.md#stage-2b-isolated-toggle-sweep-n1">Performance evidence</a> for memory definitions, single-trial limits and connection tests.</p>

<p>Uses Wi-Fi for CarPlay and requires compatible hardware and phone pairing. Wired CarPlay remains available when off. Turning on both <a href="startup-optimizations.md">Startup optimizations</a> and this override delays Mazda Navigation startup by about <strong>20 s</strong> (factory-enabled units are not affected).</p>

<p>Choices save automatically and apply on the <strong>next full Mazda Connect startup</strong>. Use <a href="apply-changes.md">Apply changes</a> to restart right away. Real-car audio, physical controls and long-parked reliability remain unqualified on <strong>0.3.0-dev.26</strong> (<strong>74.00.324A NA</strong>).</p>

<span id="connect-an-iphone"></span>

## Setup

If Wireless CarPlay is already active (factory enabled, or already turned on with no restart pending), jump straight to step 3.

1. Open **<span class="oc-nav-path" data-walkthrough="wireless-setup">Mazda Settings → System → Open Connect → CarPlay &amp; Android Auto</span>**. Turn on **Wireless CarPlay** and confirm **Enable**.
2. Select [**Apply changes**](apply-changes.md) in Open Connect and confirm **Restart**. Keep the car on until Mazda Connect restarts.
3. Open **Mazda Settings → Devices → Wi-Fi** and select **Apple CarPlay**.

    <figure class="oc-screen">
      <div class="oc-screen-frame"><img src="assets/guide/wireless-mode.png" alt="Mazda Wi-Fi mode list with Off and Apple CarPlay options." width="800" height="480" loading="lazy"></div>
      <figcaption>Step 3: select Apple CarPlay in Mazda’s Wi-Fi settings (dev.8 capture).</figcaption>
    </figure>

4. Enable Wi-Fi and Bluetooth on your iPhone. Pair it with Mazda Connect over Bluetooth and accept the wireless CarPlay prompt if shown.
5. Open **Mazda Settings → Devices → Apple CarPlay**, select your iPhone and choose **Connect**.

If **Connect** stays greyed out for an already paired iPhone, remove that phone’s pairing and pair it again. Leave other phones paired.

The North American Wi-Fi menu offers **Off** and **Apple CarPlay**; hotspot switching is not part of this setup.

<span id="disable-or-remove"></span>

## Turning it off

If you enabled wireless through Open Connect, clear **Wireless CarPlay** and confirm **Disable**. Your unit’s original wireless availability returns on the next full startup while saved phone pairings and Wi-Fi preferences stay in place.

[Wireless technical notes](cmu/wireless-carplay.md)

[Back to Settings](settings.md)
