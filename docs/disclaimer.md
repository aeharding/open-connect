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
    <dd>Not measured separately</dd>
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

<p>With disclaimer <strong>Skip</strong>, published dev.20 Base=0 Home appeared at <strong>35.6 s</strong>, versus <strong>39.9 s Stock Show</strong> (n=3 cold ACC-off boots per condition). The <strong>4.3 s Home difference</strong> includes skipping the disclaimer, but also compares Stock with the installed Base=0 configuration. It is <strong>not an isolated disclaimer-toggle trial</strong> or a measurement of the disclaimer wait alone. No separate RAM/CPU saving is established.</p>

<p>The startup warning is skipped; the screen may briefly go black. Mazda’s normal resume behavior remains, including audio, display-off and Fuel Economy Monitor.</p>

<p>Saved automatically; takes effect on the <strong>next full Mazda Connect startup</strong>. See <a href="settings.md#apply-changes">restart guidance</a>.</p>

<p>Startup and restoration have bench checks. <a href="performance.md#published-dev20-cold-acc-off-comparison-2026-11-25">Performance evidence</a> keeps the Show/Skip distinction explicit; #9 remains open. The screenshot above remains dev.19. <strong>0.3.0-dev.22</strong> is a development prerelease for <strong>74.00.324A NA</strong>; real-car qualification remains pending.</p>

<span id="change-the-setting"></span>

## Options

| Choice | Behavior |
| --- | --- |
| **Skip** | Bypasses the startup warning. |
| **Show** | Displays Mazda’s original warning. |

Select **Show** to bring the warning back after the next full startup.

[Back to Settings](settings.md)
