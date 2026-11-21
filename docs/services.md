# Services

The **Services** page is under **Mazda Settings → System → Open Connect**.
It controls the optional **Base optimizations** preset and Mazda's built-in
**Pandora** integration. Your selections save automatically and apply after a
full Mazda Connect restart.

| Choice | Fresh-install default | Effect |
| --- | --- | --- |
| Base optimizations | **Off** | Reduce normal native diagnostic logging to Warn |
| Pandora | **On** | Load Mazda's built-in Pandora integration |

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/services.png" alt="Services page with Base optimizations off and Pandora on." width="800" height="480"></div>
  <figcaption>Fresh installations leave Base off and Pandora on.</figcaption>
</figure>

## Base optimizations

Check **Base optimizations** and confirm **Enable** to apply the preset at the
next full restart. Its first contents are the measured native Warn logging
filter. Native warnings/errors remain available; early services and other
logging sources retain their separate behavior. Service selections stay as you
chose them.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/base-enable.png" alt="Enable Base optimizations confirmation explaining reduced native diagnostic logging and the restart requirement." width="800" height="480" loading="lazy"></div>
  <figcaption>Confirm Enable to save the choice.</figcaption>
</figure>

Clear it and confirm **Disable** to return to the original native logging policy
after the next full restart. Updating preserves your choice. Uninstall restores
the pre-install startup configuration; its restart clears the temporary filter.

The [installed-preset comparison](base-comparison.md) found the visible wired
CarPlay dashboard about 3.8 seconds earlier with Base on, with 9.9 MiB higher
minimum MemFree in the matched startup window and 2.58 MiB higher ending free RAM.
It used five starts per condition on the same development build, with Pandora on.
The [earlier isolated comparison](logging-comparison.md) used original features/
services and remains separate evidence. These are bench observations, with
physical-input/audio and vehicle qualification still pending.

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

Other service choices remain under investigation.
The [five-start comparison](pandora-comparison.md) found modestly higher free
RAM with Pandora off, without a resolved wired CarPlay startup gain.

The Pandora control has bench checks for startup, software Settings,
update and restoration; see the [qualification record](pandora-comparison.md#maintenance-and-restoration-qualification).
Physical-input/audio and first-car checks remain pending.
