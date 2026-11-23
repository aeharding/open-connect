# Services

The **Services** page is under **Mazda Settings → System → Open Connect**.
It controls the optional **Base optimizations** preset and Mazda's built-in
**Android Auto**, **DVD**, **Pandora** and **SiriusXM** integrations. Your selections save automatically
and apply after a full Mazda Connect restart.

| Choice | Fresh-install default | Effect |
| --- | --- | --- |
| Base optimizations | **Off** | Reduce logging and startup work; stop unused DAB, TV, Stitcher and Aha services |
| Android Auto | **On** | Load Mazda's built-in Android Auto integration |
| DVD | **Off** | Load Mazda's DVD integration |
| Pandora | **On** | Load Mazda's built-in Pandora integration |
| SiriusXM | **On** | Load Mazda's satellite-radio integrations |

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/services.png" alt="Services page with Base optimizations off, Android Auto on and Pandora on." width="800" height="480"></div>
  <figcaption>Earlier development build. The new candidate adds DVD and SiriusXM choices.</figcaption>
</figure>

## Base optimizations

Check **Base optimizations** and confirm **Enable** to apply the preset at the
next full restart. The preset combines native and browser Warn logging with
stopping DAB, TV, Stitcher and Aha on the supported NA firmware.
Warnings and errors remain available. Other logging sources retain their
separate behavior. Service selections stay as you chose them.

The dev.14 preset also reduces unnecessary flash read-ahead and lets two busy
Mazda services use both CPU cores. With **Wireless CarPlay** enabled, it waits
twelve seconds after the CarPlay and network services are ready before releasing
six background fuel, maintenance and driver-data services. These services become
available later in startup; the delay starts at service readiness, independently
of whether a phone connects. It does not wait for a CarPlay session.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/base-enable.png" alt="Enable Base optimizations confirmation explaining reduced logging, stopped DAB, TV and Stitcher services, and the restart requirement." width="800" height="480" loading="lazy"></div>
  <figcaption>Confirm Enable to save the choice.</figcaption>
</figure>

Clear it and confirm **Disable** to return to the original logging and startup policy
after the next full restart. Updating preserves your choice. Uninstall restores
the pre-install startup configuration; its restart clears the temporary policies.
An immediate ignition off/on can resume the same running kernel, so allow a full
Mazda Connect shutdown for changes to take effect.

Android Auto, DVD, Pandora and SiriusXM keep their own selections when you change Base.
Shared streaming helpers stop only when their remaining integrations are off.
Radio, DVD and streaming source rows follow the applied choices after restart;
pending changes do not alter the current menu. Mazda's USB/projection handling
remains separate.
The [dev.14 startup comparison](base-startup-tuning.md) records its timings,
CPU, flash reads and RAM cost. The earlier
[complete-preset comparison](services-comparison.md) retains its own configuration
and results.

The dev.13 candidate also changes wireless startup scheduling when Base and
Wireless CarPlay are enabled together. Its [matched comparison](wireless-startup-speed.md)
records earlier visible Maps and the accepted CPU tradeoff; other selections
retain their existing launch policy.

## Android Auto

Clear **Android Auto** and confirm **Disable** if you do not use that integration.
It stops loading after the next full restart. Check it again and confirm **Enable**
to restore it. This choice is separate from CarPlay and Pandora.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/android-auto-disable.png" alt="Disable Android Auto confirmation explaining that it will stop loading after Mazda Connect restarts." width="800" height="480" loading="lazy"></div>
  <figcaption>Cancel keeps the saved choice.</figcaption>
</figure>

A **restart needed** label means the saved choice differs from the current session.
Android-phone, audio and vehicle checks remain pending.

## Pandora

Clear the checkbox to stop that integration from loading. The confirmation
explains that changes apply after restarting Mazda Connect. Switching ignition
off and immediately on may resume the existing session; let it shut down fully.
Updating preserves the selection. Uninstall restores the pre-install startup
configuration.

Checking it again and confirming **Enable** restores the integration after the
next full restart. The checkbox shows your saved choice; the current session
keeps its existing services until that restart.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/services-disable.png" alt="Disable Pandora confirmation explaining that changes apply after restarting Mazda Connect." width="800" height="480" loading="lazy"></div>
  <figcaption>Confirm Disable to save the choice.</figcaption>
</figure>

The [five-start comparison](pandora-comparison.md) found modestly higher free
RAM with Pandora off, without a resolved wired CarPlay startup gain.

The Pandora control has bench checks for startup, software Settings,
update and restoration; see the [qualification record](pandora-comparison.md#maintenance-and-restoration-qualification).
Physical-input/audio and first-car checks remain pending.

## DVD

DVD defaults **off** in dev.15, including the first upgrade from a package with
no DVD choice. Check **DVD** and confirm **Enable** to load it after a full restart.
Later updates preserve your explicit choice. CD keeps its original behavior.

## SiriusXM

SiriusXM defaults **on**. Leave it enabled if you use satellite radio or its data
features. Clear **SiriusXM** and confirm **Disable** to stop those integrations
after a full restart; check it again to restore Mazda's normal tuner selection.
Its Audio Sources and Applications entries follow the applied choice.

The dev.15 controls and menu changes are under development. Equipped-tuner
playback, subscription/data behavior and vehicle save/resume are unqualified;
the bench has no satellite tuner. Keep SiriusXM enabled for ordinary use while
those checks remain outstanding.
