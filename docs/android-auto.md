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
    <dt>Impact</dt>
    <dd>Off: +4.6 MiB vs stock</dd>
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

<p>With Android Auto <strong>off</strong>: <strong>+4.6 MiB ending available proxy versus Stock</strong> (+4.0 MiB versus Base=0), and <strong>+7.8 MiB minimum MemFree versus Base=0</strong> (+7.2 MiB versus Stock). Home was <strong>35.2 s</strong>: about <strong>0.4 s earlier than Base=0</strong> or <strong>4.7 s earlier than Stock Show</strong>. Boot CPU was <strong>0.9 percentage points higher than Stock</strong>.</p>

<p>Published <strong>0.3.0-dev.20</strong>, one cold ACC-off boot (<strong>n=1</strong>) against earlier Stock and Base=0 medians; all other installed choices held fixed. Stock used disclaimer <strong>Show</strong>; installed boots used <strong>Skip</strong>. Small timing/CPU differences may be run variation. This sweep is separate from the primary n=3 cohorts. “Available” means the <strong>MemFree + Buffers + Cached + SReclaimable − Shmem proxy</strong>; Linux 3.0.35 has no kernel <code>MemAvailable</code>. It is not guaranteed allocatable RAM, raw <code>MemFree</code> or resident anonymous <code>AnonPages</code>; <code>Committed_AS</code> is the separate commitment counter.</p>

<p>Turning it off makes built-in Android Auto unavailable. CarPlay, Bluetooth audio, USB music and audio CDs still work.</p>

<p>Saved automatically; takes effect on the <strong>next full Mazda Connect startup</strong>. See <a href="settings.md#apply-changes">restart guidance</a>.</p>

<p><a href="performance.md#stage-2b-isolated-toggle-sweep-n1">Performance evidence</a> records the separate toggle sweep and its limits. Android-phone use remains unqualified. The screenshot above remains dev.19. <strong>0.3.0-dev.20</strong> is a development prerelease for <strong>74.00.324A NA</strong>; real-car qualification remains pending.</p>


## Change the setting

Turn **Android Auto** off and confirm **Disable** if you do not use it.
Turn it back on and confirm **Enable** to restore built-in support after a full restart.

This choice is independent of [Wireless CarPlay](wireless-carplay.md) and [Show CarPlay on connection](carplay-on-connection.md).

[Back to Settings](settings.md)
