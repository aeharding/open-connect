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
    <dt>Impact</dt>
    <dd>Faster · +9.9 MiB free (dev.7)</dd>
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

<p><strong>Faster</strong> in dev.7 wired tests: CarPlay dashboard about <strong>3.8 s earlier</strong>, with <strong>+9.9 MiB minimum MemFree</strong> and <strong>+2.58 MiB ending MemFree</strong>.</p>

<p>Stops Aha, Stitcher, DAB and TV. Mazda Navigation starts about <strong>20 s later</strong> only when <strong>both this setting and the saved Open Connect Wireless CarPlay override</strong> are on, even if no phone connects. An already-checked <strong>factory enabled</strong> wireless row leaves that override off and does not trigger this delay. Android Auto, Pandora and SiriusXM stay independent.</p>

<p>In the upcoming development candidate for North American firmware <strong>74.00.324A NA</strong>, enabling Startup optimizations also turns off Mazda’s unused DVD service automatically. Mazda’s DVD interface (<code>libjciuiadvd.so</code>) <a href="reverse-engineering.md#dvd-hardware-and-regional-gating-offline-v74-na-analysis">excludes North America from DVD playback</a>. Audio CDs use a separate service and still work. Older configurations migrate automatically, preserving your Startup optimizations choice; the separate <a href="dvd.md">DVD setting</a> is retired.</p>

<p>Saved automatically; takes effect on the <strong>next full Mazda Connect startup</strong>. See <a href="settings.md#apply-changes">restart guidance</a>.</p>

<p><a href="performance.md">Performance evidence</a> links the <a href="base-comparison.md">dev.7 comparison</a> and later presets’ <a href="sparse-native-loading.md">memory costs and workload limits</a>. These are earlier results, not dev.19 measurements or proof of faster startup than stock. Dev.19 UI bench captures on <strong>74.00.324A NA</strong>; real-car qualification and matched dev.19 benchmarks remain pending. <strong>0.3.0-dev.19</strong> is a development prerelease.</p>

The folded DVD policy has offline checks only; updated screenshots and live upgrade qualification remain pending. No isolated DVD startup or RAM gain is established.


## Change the setting

Turn **Startup optimizations** on or off and confirm **Enable** or **Disable**.
Turning it off restores Mazda’s original logging and startup behavior on the next full startup; your individual service choices stay saved.

If you use the Open Connect wireless override, leave Startup optimizations off to keep Mazda’s usual Navigation startup timing.

MemFree counts free RAM, not memory available to apps. Do not add savings from separate tests.

[Back to Settings](settings.md)
