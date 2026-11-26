# SiriusXM

Control satellite radio and SiriusXM data services.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="siriusxm">Open Connect → Audio sources</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd><span class="oc-default oc-default--on">On</span></dd>
  </div>
  <div>
    <dt>Impact (off vs stock)</dt>
    <dd>+7.4 MiB avail proxy</dd>
  </div>
  <div>
    <dt>Applies</dt>
    <dd>Next full startup</dd>
  </div>
</dl>

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-siriusxm.png" alt="SiriusXM highlighted and on in the Audio sources submenu." width="800" height="480"></div>
  <figcaption>SiriusXM highlighted and on; Bluetooth OFF, with no DVD row. Post-dev.20 PR #149 candidate ecddb381, CI 45597702470; matches merged main 291492fa.</figcaption>
</figure>

## Notes

<p>With SiriusXM <strong>off</strong>: <strong>+7.4 MiB ending available proxy versus Stock</strong> (+6.8 MiB versus Base=0), and <strong>+13.2 MiB minimum MemFree versus Base=0</strong> (+12.6 MiB versus Stock). Home was <strong>34.4 s</strong>: about <strong>1.2 s earlier than Base=0</strong> or <strong>5.5 s earlier than Stock Show</strong>. Boot CPU was <strong>0.6 percentage points lower than Stock</strong> (1.3 points lower than Base=0).</p>

<p>Published <strong>0.3.0-dev.20</strong>, one cold ACC-off boot (<strong>n=1</strong>) against earlier Stock and Base=0 medians; all other installed choices held fixed. Stock used disclaimer <strong>Show</strong>; installed boots used <strong>Skip</strong>. Small timing/CPU differences may be run variation. This sweep is separate from the primary n=3 cohorts. “Available” means the <strong>MemFree + Buffers + Cached + SReclaimable − Shmem proxy</strong>; Linux 3.0.35 has no kernel <code>MemAvailable</code>. It is not guaranteed allocatable RAM, raw <code>MemFree</code> or resident anonymous <code>AnonPages</code>; <code>Committed_AS</code> is the separate commitment counter.</p>

<p>Turning it off hides SiriusXM from <strong>Sources</strong> and stops both satellite radio and SiriusXM data. CarPlay and audio CDs still work.</p>

<p>Saved automatically; takes effect on the <strong>next full Mazda Connect startup</strong>. See <a href="settings.md#apply-changes">restart guidance</a>.</p>

<p><a href="performance.md#stage-2b-isolated-toggle-sweep-n1">Performance evidence</a> records the separate toggle sweep and its limits. The bench has no equipped satellite tuner; radio and data playback remain unqualified. <strong>0.3.0-dev.23</strong> is a development prerelease for <strong>74.00.324A NA</strong>; real-car qualification remains pending.</p>


## Change the setting

Leave **SiriusXM** on if you use satellite radio or its data services. To stop both, turn it off and confirm **Disable**. Turn it on and confirm **Enable** to restore support after a full restart.

Enabled sources retain Mazda’s hardware, connection and availability requirements. This choice is independent of [Startup optimizations](startup-optimizations.md).

[Back to Settings](settings.md)
