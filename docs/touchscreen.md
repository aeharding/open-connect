# Touchscreen While Driving

Keep touch available while the car is moving, including for a passenger using Mazda’s menus.

<dl class="oc-spec">
  <dt>Location</dt>
  <dd><span class="oc-nav-path" data-walkthrough="touchscreen">Open Connect</span></dd>
  <dt>Default</dt>
  <dd><span class="oc-default oc-default--on">Allow</span>.</dd>
  <dt>Startup &amp; RAM</dt>
  <dd><strong>Neutral</strong> — no isolated startup or RAM measurement is established.</dd>
  <dt>Trade-offs &amp; boot</dt>
  <dd>Touch remains available while moving. The commander knob and normal Mazda controls remain available. Keep your attention on driving.</dd>
  <dt>Applies</dt>
  <dd>Saved automatically; takes effect on the <strong>next full Mazda Connect startup</strong>. See <a href="settings.md#apply-changes">restart guidance</a>.</dd>
  <dt>Evidence</dt>
  <dd>The setting and restoration have bench checks; touch while moving in a real car remains unvalidated. <a href="performance.md">Performance evidence</a> has no isolated comparison. Dev.19 UI bench captures on <strong>74.00.324A NA</strong>; real-car qualification and matched dev.19 benchmarks remain pending. <strong>0.3.0-dev.19</strong> is a development prerelease.</dd>
</dl>

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-touchscreen-while-driving.png" alt="Touchscreen While Driving highlighted in Open Connect, with Allow displayed." width="800" height="480"></div>
  <figcaption>Touchscreen While Driving highlighted (dev.19).</figcaption>
</figure>

<span id="change-the-setting"></span>

## Options

| Choice | Behavior |
| --- | --- |
| **Allow** | Removes the speed-based touch lockout. |
| **Factory Default** | Restores the touchscreen setting saved before installation. |

Select your choice. Return here after the next full startup to check it.

[Back to Settings](settings.md)
