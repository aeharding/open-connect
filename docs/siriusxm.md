# SiriusXM

Control satellite radio and SiriusXM data services.

**<span class="oc-nav-path" data-walkthrough="siriusxm">Mazda Settings → System → Open Connect → Audio sources → SiriusXM</span>**

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-siriusxm.png" alt="SiriusXM highlighted and on in the Audio sources submenu." width="800" height="480"></div>
  <figcaption>SiriusXM highlighted (dev.19).</figcaption>
</figure>

- **Default**: <span class="oc-default oc-default--on">On</span>.
- **Startup & RAM impact**: **Neutral** — no isolated startup or free-RAM gain is established.
- **Trade-offs & boot implications**: Turning it off hides SiriusXM from **Sources** and stops both satellite radio and SiriusXM data. CarPlay and audio CDs still work.
- **Applies**: Saved automatically; takes effect on the **next full Mazda Connect startup**. See [restart guidance](settings.md#apply-changes).
- **Evidence & limits**: [Performance evidence](performance.md) has no isolated SiriusXM comparison. The bench has no equipped satellite tuner; radio and data playback remain unqualified. Dev.19 UI bench captures on **74.00.324A NA**; real-car qualification and matched dev.19 benchmarks remain pending. **0.3.0-dev.19** is a development prerelease.

## Change the setting

Leave **SiriusXM** on if you use satellite radio or its data services. To stop both, turn it off and confirm **Disable**. Turn it on and confirm **Enable** to restore support after a full restart.

Enabled sources retain Mazda’s hardware, connection and availability requirements. This choice is independent of [Startup optimizations](startup-optimizations.md).

[Back to Settings](settings.md)
