# Touchscreen While Driving

Keep touch available while the car is moving, including for a passenger using Mazda’s menus.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="touchscreen">Open Connect</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd><span class="oc-default oc-default--on">Allow</span></dd>
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
  <div class="oc-screen-frame"><img src="assets/guide/setting-touchscreen-while-driving.png" alt="Touchscreen While Driving highlighted in Open Connect, with Allow displayed." width="800" height="480"></div>
  <figcaption>Touchscreen While Driving highlighted (dev.19).</figcaption>
</figure>

## Notes

<p><strong>Not measured separately</strong> for RAM, CPU or startup. The dev.20 installed cohorts held Touchscreen While Driving at Allow; their results do not isolate this preference.</p>

<p>Touch remains available while moving. The commander knob and normal Mazda controls remain available. Keep your attention on driving.</p>

<p>Saved automatically; takes effect on the <strong>next full Mazda Connect startup</strong>. See <a href="settings.md#apply-changes">restart guidance</a>.</p>

<p>The setting and restoration have bench checks; touch while moving in a real car remains unvalidated. <a href="performance.md">Performance evidence</a> has no isolated comparison. The screenshot above remains dev.19 on <strong>74.00.324A NA</strong>. <strong>0.3.0-dev.23</strong> is a development prerelease; real-car qualification remains pending.</p>


<span id="change-the-setting"></span>

## Options

| Choice | Behavior |
| --- | --- |
| **Allow** | Removes the speed-based touch lockout. |
| **Factory Default** | Restores the touchscreen setting saved before installation. |

Select your choice. Return here after the next full startup to check it.

[Back to Settings](settings.md)
