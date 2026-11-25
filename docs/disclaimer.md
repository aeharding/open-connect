# Startup disclaimer

Skip Mazda’s startup warning and continue to your usual screen.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="disclaimer">Open Connect</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd><span class="oc-default oc-default--on">Skip</span></dd>
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
  <div class="oc-screen-frame"><img src="assets/guide/setting-startup-disclaimer.png" alt="Startup disclaimer highlighted in Open Connect, with Skip displayed." width="800" height="480"></div>
  <figcaption>Startup disclaimer highlighted (dev.19).</figcaption>
</figure>

## Notes

<p><strong>Neutral</strong> — no isolated startup or RAM measurement is established.</p>

<p>The startup warning is skipped; the screen may briefly go black. Mazda’s normal resume behavior remains, including audio, display-off and Fuel Economy Monitor.</p>

<p>Saved automatically; takes effect on the <strong>next full Mazda Connect startup</strong>. See <a href="settings.md#apply-changes">restart guidance</a>.</p>

<p>Startup and restoration have bench checks. <a href="performance.md">Performance evidence</a> does not isolate this setting. Dev.19 UI bench captures on <strong>74.00.324A NA</strong>; real-car qualification and matched dev.19 benchmarks remain pending. <strong>0.3.0-dev.19</strong> is a development prerelease.</p>


<span id="change-the-setting"></span>

## Options

| Choice | Behavior |
| --- | --- |
| **Skip** | Bypasses the startup warning. |
| **Show** | Displays Mazda’s original warning. |

Select **Show** to bring the warning back after the next full startup.

[Back to Settings](settings.md)
