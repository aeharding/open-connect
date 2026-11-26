# Startup optimizations

Reduce background logging and stop unused services at startup. Previously called **Base optimizations**; your saved choice is kept.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="startup-optimizations">Open Connect</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd><span class="oc-default oc-default--off">Off</span></dd>
  </div>
  <div>
    <dt>Impact (on vs stock)</dt>
    <dd>+21.2 MiB avail proxy</dd>
  </div>
  <div>
    <dt>Applies</dt>
    <dd>Next full startup</dd>
  </div>
</dl>

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-startup-optimizations.png" alt="Startup optimizations highlighted and enabled in Open Connect." width="800" height="480"></div>
  <figcaption>Startup optimizations highlighted (dev.19); shown on, with a fresh-install default of Off.</figcaption>
</figure>

## Notes

<p><strong>Bench results (dev.20, n=3 cold boots):</strong> the main screen appeared at <strong>32.2 s</strong> — about <strong>7.7 s earlier than Stock</strong> (39.9 s, Stock Show vs installed Skip) and <strong>3.4 s earlier than Open Connect defaults</strong> (35.6 s) — with <strong>+21.2 MiB available RAM proxy</strong> (−17.8 MiB AnonPages; 500 KiB own allocated tmpfs) and <strong>−4.8 percentage points boot CPU</strong> versus Stock. See <a href="performance.md#published-dev20-cold-acc-off-comparison-2026-11-25">Performance evidence</a> for memory definitions, full cohorts and trial limits.</p>

<p>Stops unused services including Aha, Stitcher, DAB, TV, and Mazda’s unused North American <a href="dvd.md">DVD</a> service (audio CDs use a separate service and continue to work). Android Auto, Pandora and SiriusXM remain independent toggles.</p>

<p><strong>Navigation delay note:</strong> Mazda Navigation starts about <strong>20 s later</strong> when <strong>both</strong> Startup optimizations and the saved Open Connect <a href="wireless-carplay.md">Wireless CarPlay</a> override are turned on, even if no phone connects. Units with <strong>factory enabled</strong> wireless CarPlay are not affected.</p>

<p>Choices save automatically and apply on the <strong>next full Mazda Connect startup</strong>. Use <a href="apply-changes.md">Apply changes</a> to restart right away. <strong>0.3.0-dev.24</strong> is a development prerelease for <strong>74.00.324A NA</strong>; real-car qualification remains pending.</p>

## Change the setting

Turn **Startup optimizations** on or off and confirm **Enable** or **Disable**. Turning it off restores Mazda’s original logging and startup behavior on the next full startup while keeping your other service choices saved.

If you use Open Connect’s Wireless CarPlay override and want Mazda’s usual Navigation startup timing, leave Startup optimizations off.

[Back to Settings](settings.md)
