# SiriusXM

Control satellite radio and SiriusXM data services.

<dl class="oc-spec">
  <dt>Location</dt>
  <dd><span class="oc-nav-path" data-walkthrough="siriusxm">Open Connect → Audio sources</span></dd>
  <dt>Default</dt>
  <dd><span class="oc-default oc-default--on">On</span>.</dd>
  <dt>Startup &amp; RAM</dt>
  <dd><strong>Neutral</strong> — no isolated startup or free-RAM gain is established.</dd>
  <dt>Trade-offs &amp; boot</dt>
  <dd>Turning it off hides SiriusXM from <strong>Sources</strong> and stops both satellite radio and SiriusXM data. CarPlay and audio CDs still work.</dd>
  <dt>Applies</dt>
  <dd>Saved automatically; takes effect on the <strong>next full Mazda Connect startup</strong>. See <a href="settings.md#apply-changes">restart guidance</a>.</dd>
  <dt>Evidence</dt>
  <dd><a href="performance.md">Performance evidence</a> has no isolated SiriusXM comparison. The bench has no equipped satellite tuner; radio and data playback remain unqualified. Dev.19 UI bench captures on <strong>74.00.324A NA</strong>; real-car qualification and matched dev.19 benchmarks remain pending. <strong>0.3.0-dev.19</strong> is a development prerelease.</dd>
</dl>

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-siriusxm.png" alt="SiriusXM highlighted and on in the Audio sources submenu." width="800" height="480"></div>
  <figcaption>SiriusXM highlighted (dev.19).</figcaption>
</figure>

## Change the setting

Leave **SiriusXM** on if you use satellite radio or its data services. To stop both, turn it off and confirm **Disable**. Turn it on and confirm **Enable** to restore support after a full restart.

Enabled sources retain Mazda’s hardware, connection and availability requirements. This choice is independent of [Startup optimizations](startup-optimizations.md).

[Back to Settings](settings.md)
