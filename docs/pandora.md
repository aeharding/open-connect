# Pandora

Control Mazda’s built-in Pandora integration.

**<span class="oc-nav-path" data-walkthrough="pandora">Mazda Settings → System → Open Connect → Audio sources → Pandora</span>**

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-pandora.png" alt="Pandora highlighted and on in the Audio sources submenu." width="800" height="480"></div>
  <figcaption>Pandora highlighted (dev.19).</figcaption>
</figure>

- **Default**: <span class="oc-default oc-default--on">On</span>.
- **Startup & RAM impact**: **Neutral** for startup in the dev.6 comparison: the wired-dashboard timing difference was below camera resolution. Turning it off left about **3.2 MiB more minimum MemFree**.
- **Trade-offs & boot implications**: Turning it off hides Mazda’s Pandora integration from **Sources**. Pandora through CarPlay or Bluetooth, and audio CDs, still work.
- **Applies**: Saved automatically; takes effect on the **next full Mazda Connect startup**. See [restart guidance](settings.md#apply-changes).
- **Evidence & limits**: [Performance evidence](performance.md) links the [dev.6 comparison](pandora-comparison.md): five starts per choice on one bench. MemFree is free RAM, not memory available to apps; these are not dev.19 results. Dev.19 UI bench captures on **74.00.324A NA**; real-car qualification and matched dev.19 benchmarks remain pending. **0.3.0-dev.19** is a development prerelease.

## Change the setting

Turn **Pandora** off and confirm **Disable** to remove Mazda’s integration after a full restart. Turn it on and confirm **Enable** to restore its usual availability.

Enabled sources retain Mazda’s hardware, connection and availability requirements. This choice is independent of [Startup optimizations](startup-optimizations.md).

[Back to Settings](settings.md)
