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
  <figcaption>Pandora highlighted and on; Bluetooth OFF, with no DVD row. Post-dev.20 PR #149 candidate ecddb381, CI 45597702470; matches merged main 291492fa.</figcaption>
</figure>

## Notes

<p>With Pandora <strong>off</strong>: <strong>+1.9 MiB ending available proxy versus Stock</strong> (+1.2 MiB versus Base=0), and <strong>+2.5 MiB minimum MemFree versus Base=0</strong> (+1.9 MiB versus Stock). Home was <strong>36.0 s</strong>: <strong>0.4 s later than Base=0</strong>, or <strong>3.9 s earlier than Stock Show</strong>. One trial; repeatability is unknown. No repeatable boot-time benefit is established. Boot CPU was <strong>2.4 percentage points higher than Stock</strong>.</p>

<p>Published <strong>0.3.0-dev.20</strong>, one cold ACC-off boot (<strong>n=1</strong>) against earlier Stock and Base=0 medians; all other installed choices held fixed. Stock used disclaimer <strong>Show</strong>; installed boots used <strong>Skip</strong>. Small timing/CPU differences may be run variation. This sweep is separate from the primary n=3 cohorts. “Available” means the <strong>MemFree + Buffers + Cached + SReclaimable − Shmem proxy</strong>; Linux 3.0.35 has no kernel <code>MemAvailable</code>. It is not guaranteed allocatable RAM, raw <code>MemFree</code> or resident anonymous <code>AnonPages</code>; <code>Committed_AS</code> is the separate commitment counter.</p>

<p>Turning it off hides Mazda’s Pandora integration from <strong>Sources</strong>. Pandora through CarPlay or Bluetooth, and audio CDs, still work.</p>

<p>Saved automatically; takes effect on the <strong>next full Mazda Connect startup</strong>. See <a href="settings.md#apply-changes">restart guidance</a>.</p>

<p><a href="performance.md#stage-2b-isolated-toggle-sweep-n1">Performance evidence</a> records the separate toggle sweep and its limits. The older <a href="pandora-comparison.md">dev.6 comparison</a> is historical evidence; its MemFree figures do not describe dev.20. <strong>0.3.0-dev.20</strong> is a development prerelease for <strong>74.00.324A NA</strong>; real-car qualification remains pending.</p>


## Change the setting

Turn **Pandora** off and confirm **Disable** to remove Mazda’s integration after a full restart. Turn it on and confirm **Enable** to restore its usual availability.

Enabled sources retain Mazda’s hardware, connection and availability requirements. This choice is independent of [Startup optimizations](startup-optimizations.md).

[Back to Settings](settings.md)
