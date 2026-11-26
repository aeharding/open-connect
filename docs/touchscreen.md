# Touchscreen

Choose how Mazda Connect handles touch. The Commander knob and normal Mazda
controls remain available. Choices save automatically and apply at the next
full startup; use [Apply changes](settings.md#apply-changes) to restart.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="touchscreen">Mazda Settings → System → Open Connect</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd>Allow (published dev.23); Always enabled (upcoming build)</dd>
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

## Published v0.3.0-dev.23 USB

The published development prerelease calls this setting **Touchscreen While
Driving** and offers two choices:

| Choice | Behavior |
| --- | --- |
| **Allow** (default) | Removes the speed-based touch lockout. |
| **Factory Default** | Uses the touchscreen setting saved before installation. |

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-touchscreen-while-driving.png" alt="Touchscreen While Driving highlighted in Open Connect, with Allow displayed." width="800" height="480"></div>
  <figcaption>Dev.19 screenshot; the Menu walkthrough was recorded on dev.20. Both show the two-choice setting used by published dev.23. The upcoming build changes the row and choice labels.</figcaption>
</figure>

Select the Menu walkthrough above to follow the Commander route. In published
dev.23, select **Touchscreen While Driving**, then **Allow** or **Factory Default**.

## Upcoming build: three choices

The current development branch calls the setting **Touchscreen** and adds
**Always disabled**. These choices are not in the published dev.23 USB:

| Choice | Behavior |
| --- | --- |
| **Factory behavior** | Uses the touchscreen setting saved before installation. |
| **Always enabled** (default) | Removes the speed-based touch lockout. |
| **Always disabled** | Blocks touchscreen input while retaining Commander navigation. |

Use the Commander knob to return to **Touchscreen** and select another choice.
Always disabled requires the exact supported **74.00.324A NA** input libraries.
If those inputs change during an interrupted switch to Always disabled, recovery
returns to the previous choice so maintenance can continue.

To remove this build, use its installed **Uninstall** or compatible maintenance
USB that supports all three choices. The published dev.23 USB refuses maintenance
when Always disabled is saved, including Uninstall. Before using that older USB,
save **Factory behavior** or **Always enabled** in the newer Settings; those map
to **Factory Default** and **Allow**, respectively. Use **Apply changes** to
activate the choice. Uninstall restores the pre-install behavior after restart.

## Qualification

The published two-choice setting has bench checks; touch while moving in a real
car remains unvalidated. Always disabled has partial software-injection evidence;
final packaged startup, earliest input, physical touch and Commander, and active
CarPlay, Android Auto and Navigation checks remain pending. Neither has an
isolated release performance result. See [performance evidence](performance.md)
and the [implementation findings](reverse-engineering.md#boot-scoped-touchscreen-disable-on-v74)
for ABI, memory measurements and remaining qualification.

[Back to Settings](settings.md)
