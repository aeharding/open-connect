# Pandora

Control Mazda’s built-in Pandora integration.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="pandora">Open Connect → Audio sources</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd><span class="oc-default oc-default--on">On</span></dd>
  </div>
  <div>
    <dt>Impact (off vs stock)</dt>
    <dd>+1.9 MiB avail proxy</dd>
  </div>
  <div>
    <dt>Applies</dt>
    <dd>Next full startup</dd>
  </div>
</dl>

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-pandora.png" alt="Pandora highlighted and on in the Audio sources submenu." width="800" height="480"></div>
  <figcaption>Pandora highlighted in Audio sources.</figcaption>
</figure>

## Notes

<p><strong>Bench results (dev.20, n=1 cold boot with Pandora off):</strong> <strong>+1.9 MiB available RAM proxy</strong> versus Stock (+1.2 MiB vs Open Connect defaults), with no repeatable startup-time improvement established (36.0 s main screen, +2.4 pp boot CPU vs Stock). See <a href="performance.md#stage-2b-isolated-toggle-sweep-n1">Performance evidence</a> for memory definitions and single-trial limits.</p>

<p>Turning it off hides Mazda’s built-in Pandora app from <strong>Sources</strong>. Streaming Pandora through CarPlay or Bluetooth, as well as audio CDs, still work.</p>

<p>Choices save automatically and apply on the <strong>next full Mazda Connect startup</strong>. Use <a href="apply-changes.md">Apply changes</a> to restart right away. <strong>0.3.0-dev.26</strong> is a development prerelease for <strong>74.00.324A NA</strong>; real-car qualification remains pending.</p>

## Change the setting

Turn **Pandora** off and confirm **Disable** to remove Mazda’s built-in integration after a full restart. Turn it on and confirm **Enable** to restore it.

Enabled sources keep Mazda’s normal hardware and connection requirements. This choice is independent of [Startup optimizations](startup-optimizations.md).

[Back to Settings](settings.md)
