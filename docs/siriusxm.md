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
    <dt>Impact</dt>
    <dd>Neutral</dd>
  </div>
  <div>
    <dt>Applies</dt>
    <dd>Next full startup</dd>
  </div>
</dl>

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-siriusxm.png" alt="SiriusXM highlighted and on in the Audio sources submenu." width="800" height="480"></div>
  <figcaption>SiriusXM highlighted (dev.19).</figcaption>
</figure>

## Notes

<p><strong>Neutral</strong> — no isolated startup or free-RAM gain is established.</p>

<p>Turning it off hides SiriusXM from <strong>Sources</strong> and stops both satellite radio and SiriusXM data. CarPlay and audio CDs still work.</p>

<p>Saved automatically; takes effect on the <strong>next full Mazda Connect startup</strong>. See <a href="settings.md#apply-changes">restart guidance</a>.</p>

<p><a href="performance.md">Performance evidence</a> has no isolated SiriusXM comparison. The bench has no equipped satellite tuner; radio and data playback remain unqualified. Dev.19 UI bench captures on <strong>74.00.324A NA</strong>; real-car qualification and matched dev.19 benchmarks remain pending. <strong>0.3.0-dev.19</strong> is a development prerelease.</p>


## Change the setting

Leave **SiriusXM** on if you use satellite radio or its data services. To stop both, turn it off and confirm **Disable**. Turn it on and confirm **Enable** to restore support after a full restart.

Enabled sources retain Mazda’s hardware, connection and availability requirements. This choice is independent of [Startup optimizations](startup-optimizations.md).

[Back to Settings](settings.md)
