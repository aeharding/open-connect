# Android Auto

Control Mazda’s built-in Android Auto support.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="android-auto">Open Connect → CarPlay &amp; Android Auto</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd><span class="oc-default oc-default--on">On</span></dd>
  </div>
  <div>
    <dt>Impact (off vs stock)</dt>
    <dd>+4.6 MiB avail proxy</dd>
  </div>
  <div>
    <dt>Applies</dt>
    <dd>Next full startup</dd>
  </div>
</dl>

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-android-auto.png" alt="Android Auto highlighted and enabled in the CarPlay and Android Auto submenu." width="800" height="480"></div>
  <figcaption>Android Auto highlighted (dev.19).</figcaption>
</figure>

## Notes

<p><strong>Bench results (dev.20, n=1 cold boot with Android Auto off):</strong> <strong>+4.6 MiB available RAM proxy</strong> versus Stock (+4.0 MiB vs Open Connect defaults) and main screen at 35.2 s (0.4 s earlier than defaults; +0.9 pp boot CPU vs Stock). See <a href="performance.md#stage-2b-isolated-toggle-sweep-n1">Performance evidence</a> for memory definitions and single-trial limits.</p>

<p>Turning Android Auto off makes built-in Android Auto unavailable. CarPlay, Bluetooth audio, USB music and audio CDs still work.</p>

<p>Choices save automatically and apply on the <strong>next full Mazda Connect startup</strong>. Use <a href="apply-changes.md">Apply changes</a> to restart right away. Live Android-phone and real-car testing remain unqualified on <strong>0.3.0-dev.24</strong> (<strong>74.00.324A NA</strong>).</p>

## Change the setting

Turn **Android Auto** off and confirm **Disable** if you don’t use it. Turn it back on and confirm **Enable** to restore built-in support after a full restart.

This choice is independent of [Wireless CarPlay](wireless-carplay.md) and [Show CarPlay on connection](carplay-on-connection.md).

[Back to Settings](settings.md)
