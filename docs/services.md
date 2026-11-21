# Services

The **Services** page is under **Mazda Settings → System → Open Connect**.
Its first development control is **Pandora**, which defaults to **on**.
This controls Mazda's built-in Pandora integration.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/services.png" alt="Services page with Pandora checked." width="800" height="480"></div>
  <figcaption>Pandora starts by default.</figcaption>
</figure>

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

Other service choices and a Base optimizations bundle remain under investigation.
The [five-start comparison](pandora-comparison.md) found modestly higher free
RAM with Pandora off, without a resolved wired CarPlay startup gain.

This development control has bench checks for startup, software Settings,
update and restoration; see the [qualification record](pandora-comparison.md#maintenance-and-restoration-qualification).
Physical-input/audio and first-car checks remain pending.
