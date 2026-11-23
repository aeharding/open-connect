# Services

The **Services** page is under **Mazda Settings → System → Open Connect**.
It controls the optional **Base optimizations** preset and Mazda's built-in
**Android Auto** and **Pandora** integrations. Your selections save automatically
and apply after a full Mazda Connect restart.

| Choice | Fresh-install default | Effect |
| --- | --- | --- |
| Base optimizations | **Off** | Reduce native logging to Warn and stop unused DAB, TV and Stitcher services |
| Android Auto | **On** | Load Mazda's built-in Android Auto integration |
| Pandora | **On** | Load Mazda's built-in Pandora integration |

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/services.png" alt="Services page with Base optimizations off, Android Auto on and Pandora on." width="800" height="480"></div>
  <figcaption>Fresh installations leave Base off and both integrations on.</figcaption>
</figure>

## Base optimizations

Check **Base optimizations** and confirm **Enable** to apply the preset at the
next full restart. The preset combines the native Warn logging filter with
stopping DAB, TV and the two Stitcher services on the supported NA firmware.
Native warnings/errors remain available; early services and other
logging sources retain their separate behavior. Service selections stay as you
chose them.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/base-enable.png" alt="Enable Base optimizations confirmation explaining reduced logging, stopped DAB, TV and Stitcher services, and the restart requirement." width="800" height="480" loading="lazy"></div>
  <figcaption>Confirm Enable to save the choice.</figcaption>
</figure>

Clear it and confirm **Disable** to return to the original logging and service policy
after the next full restart. Updating preserves your choice. Uninstall restores
the pre-install startup configuration; its restart clears the temporary filter.

Android Auto and Pandora keep their own selections when you change Base.
The [complete-preset comparison](services-comparison.md) records its measured
RAM and startup observations, configurations and limits.

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
