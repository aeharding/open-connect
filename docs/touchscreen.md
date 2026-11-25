# Touchscreen While Driving

Keep touch available while the car is moving, including for a passenger using Mazda’s menus.

**<span class="oc-nav-path" data-walkthrough="touchscreen">Mazda Settings → System → Open Connect → Touchscreen While Driving</span>**

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-touchscreen-while-driving.png" alt="Touchscreen While Driving highlighted in Open Connect, with Allow displayed." width="800" height="480"></div>
  <figcaption>Touchscreen While Driving highlighted (dev.19).</figcaption>
</figure>

- **Default**: <span class="oc-default oc-default--on">Allow</span>.
- **Startup & RAM impact**: **Neutral** — no isolated startup or RAM measurement is established.
- **Trade-offs & boot implications**: Touch remains available while moving. The commander knob and normal Mazda controls remain available. Keep your attention on driving.
- **Applies**: Saved automatically; takes effect on the **next full Mazda Connect startup**. See [restart guidance](settings.md#apply-changes).
- **Evidence & limits**: The setting and restoration have bench checks; touch while moving in a real car remains unvalidated. [Performance evidence](performance.md) has no isolated comparison. Dev.19 UI bench captures on **74.00.324A NA**; real-car qualification and matched dev.19 benchmarks remain pending. No public download yet.

<span id="change-the-setting"></span>

## Options

| Choice | Behavior |
| --- | --- |
| **Allow** | Removes the speed-based touch lockout. |
| **Factory Default** | Restores the touchscreen setting saved before installation. |

Select your choice. Return here after the next full startup to check it.

[Back to Settings](settings.md)
