# Touchscreen

Choose how Mazda Connect handles touchscreen input. Commander navigation remains
available to change the preference. Choices save automatically and take effect
on the next full startup; use [Apply changes](settings.md#apply-changes).

| Choice | Behavior |
| --- | --- |
| **Factory behavior** | Uses the touchscreen setting saved before installation. |
| **Always enabled** (default) | Removes the speed-based touch lockout. |
| **Always disabled** | Selects a boot-scoped input service shim that releases touchscreen devices and suppresses their sends. |

Always disabled requires the exact supported **74.00.324A NA** devices libraries.
Changing back to another mode or uninstalling does not require those libraries
to remain unchanged. Uninstall preserves the running input service's RAM copy
until restart, when Mazda's original service resumes. Recovery selects the stock
service and restores the pre-install speed setting; Mazda samples that setting
earlier, so its restoration takes effect on the following boot.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-touchscreen-while-driving.png" alt="Historical dev.19 Open Connect touchscreen row showing Allow." width="800" height="480"></div>
  <figcaption>Historical dev.19 view; the current row is Touchscreen with three choices.</figcaption>
</figure>

The prototype's software-injected touchscreen events reached the raw input but
not the filtered device, while injected Commander events navigated Mazda's UI.
This is partial bench evidence. The final packaged shim still needs SM startup,
dependency registration and idle checks, earliest-input coverage, physical touch
and Commander validation, and active CarPlay, Android Auto and Navigation tests.
AR1XXX hardware and touch while moving in a real car remain unvalidated.

There is no isolated release performance result. Installed Factory behavior and
Always enabled do not stage the shim in feature tmpfs or the 16-file Settings
working set. They add one boot-plan package row (native open/stat) and one package
member hashed by the Settings worker. USB maintenance stages one extra **4 KiB**
page in every mode. Always disabled adds one **4 KiB** feature copy plus release
input-service PSS that has not yet been measured. The prototype's 1,305 → 1,318 KiB
PSS comparison used a different service copy and cannot qualify release overhead.
Matched timing, allocated-page and PSS measurements and explicit owner RAM
acceptance remain pending. See the [implementation findings](reverse-engineering.md#boot-scoped-touchscreen-disable-on-v74)
and [performance evidence](performance.md).

[Back to Settings](settings.md)
