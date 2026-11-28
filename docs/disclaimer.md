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

<p>The startup warning is skipped; the screen may briefly go black during startup. Mazda’s normal resume behavior stays intact, including audio, display-off and Fuel Economy Monitor.</p>

<p>In cold-boot bench tests (dev.20), the main screen appeared at <strong>35.6 s</strong> with Open Connect defaults (Skip) versus <strong>39.9 s</strong> on Stock (Show), a 4.3 s difference that reflects both skipping the disclaimer and the rest of the default install rather than an isolated disclaimer-only trial. See <a href="performance.md#published-dev20-cold-acc-off-comparison-2026-11-25">Performance evidence</a> for details.</p>

<p>Choices save automatically and apply on the <strong>next full Mazda Connect startup</strong>. Use <a href="apply-changes.md">Apply changes</a> to restart right away. <strong>0.3.0-dev.26</strong> is a development prerelease for <strong>74.00.324A NA</strong>; real-car qualification remains pending.</p>

<span id="change-the-setting"></span>

## Options

| Choice | Behavior |
| --- | --- |
| **Skip** | Bypasses the startup warning. |
| **Show** | Displays Mazda’s original warning. |

Select **Show** to bring the warning back after the next full startup.

[Back to Settings](settings.md)
