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

<p><strong>Published dev.20, n=3 cold ACC-off boots per condition:</strong> Home appeared at <strong>32.2 s</strong> with Base=1, versus <strong>39.9 s Stock Show</strong> and <strong>35.6 s Base=0 Skip</strong>. That is about <strong>7.7 s earlier than Stock</strong>, including the disclaimer difference, or <strong>3.4 s earlier than Base=0</strong> with Skip held fixed. This is a bundle comparison, not isolated read-ahead causality.</p>

<p>Versus Stock: <strong>+21.2 MiB ending available-RAM proxy</strong>, <strong>−17.8 MiB AnonPages</strong> (resident anonymous memory), <strong>−4.8 percentage points boot CPU</strong> and <strong>−6.0 busy CPU-s</strong>. Own allocated tmpfs was <strong>500 KiB</strong>, versus 396 KiB with Base=0 and none on Stock. “Available” means the <strong>MemFree + Buffers + Cached + SReclaimable − Shmem proxy</strong>; Linux 3.0.35 has no kernel <code>MemAvailable</code>. It is not guaranteed allocatable RAM, raw <code>MemFree</code> or resident anonymous <code>AnonPages</code>; <code>Committed_AS</code> is the separate commitment counter.</p>

<p>Stops Aha, Stitcher, DAB and TV. Mazda Navigation starts about <strong>20 s later</strong> only when <strong>both this setting and the saved Open Connect Wireless CarPlay override</strong> are on, even if no phone connects. An already-checked <strong>factory enabled</strong> wireless row leaves that override off and does not trigger this delay. Android Auto, Pandora and SiriusXM stay independent.</p>

<p>The dev.21 North American prerelease also turns off Mazda’s unused DVD service with Startup optimizations. Mazda’s DVD interface <a href="reverse-engineering.md#dvd-hardware-and-regional-gating-offline-v74-na-analysis">excludes North America from DVD playback</a>; audio CDs use a separate service. Older configurations migrate automatically, preserving this choice; the separate <a href="dvd.md">DVD setting</a> is retired. The measured dev.20 release has that separate toggle, held off in these measurements.</p>

<p>Saved automatically; takes effect on the <strong>next full Mazda Connect startup</strong>. See <a href="settings.md#apply-changes">restart guidance</a>.</p>

<p><a href="performance.md#published-dev20-cold-acc-off-comparison-2026-11-25">Performance evidence</a> retains all 11 primary attempts, including the SSH bind failure and uncommanded restart; nine clean traces supply the medians. #9 remains open. PR #149 has separate DVD-policy/reinstall checks and new Audio sources captures, <strong>no new performance cohort</strong>. The screenshot above remains dev.19. <strong>0.3.0-dev.21</strong> is a development prerelease for <strong>74.00.324A NA</strong>; real-car qualification remains pending.</p>


## Change the setting

Turn **Startup optimizations** on or off and confirm **Enable** or **Disable**.
Turning it off restores Mazda’s original logging and startup behavior on the next full startup; your individual service choices stay saved.

If you use the Open Connect wireless override, leave Startup optimizations off to keep Mazda’s usual Navigation startup timing.

Do not add RAM differences from separate tests; combined configurations need their own measurements.

[Back to Settings](settings.md)
