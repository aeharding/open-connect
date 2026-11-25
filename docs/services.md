# Services

Turn off the phone and entertainment integrations you don’t use. Leave anything you use enabled.

Open **Mazda Settings → System → Open Connect → Services**. Changes apply on the next full startup.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/services.png" alt="Services with Base optimizations off, Android Auto on, DVD off, Pandora on and SiriusXM on." width="800" height="480"></div>
  <figcaption>Fresh-install choices. Each integration can be changed separately.</figcaption>
</figure>

## Phone and entertainment

| Setting | Description | Default |
| --- | --- | --- |
| <span id="android-auto"></span>**Android Auto** | Built-in Android Auto support. Does not affect CarPlay, Bluetooth audio or USB music. | <span class="oc-default oc-default--on"><span aria-hidden="true">✓</span> On</span> |
| <span id="dvd"></span>**DVD** | In-dash DVD video playback. CD audio still works when off. | <span class="oc-default oc-default--off"><span aria-hidden="true">✕</span> Off</span> |
| <span id="pandora"></span>**Pandora** | Mazda’s built-in Pandora app. Does not affect Pandora through CarPlay or Bluetooth. | <span class="oc-default oc-default--on"><span aria-hidden="true">✓</span> On</span> |
| <span id="siriusxm"></span>**SiriusXM** | Satellite radio and SiriusXM data services. | <span class="oc-default oc-default--on"><span aria-hidden="true">✓</span> On</span> |

Confirm **Enable** or **Disable** when prompted. Turning an integration back on makes it available again after a full restart, subject to Mazda’s usual hardware and connection requirements.

## Base optimizations

**Base optimizations** reduces background work at startup. It also stops the built-in Aha, Stitcher, DAB radio and TV integrations. It defaults to **Off** and leaves your individual choices above unchanged.

**If Wireless CarPlay is also on, Mazda Navigation starts about 20 seconds later.** Navigation still starts if no phone connects. Leave Base off if you want Mazda’s usual Navigation startup timing.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/base-enable.png" alt="Enable Base optimizations confirmation, including the Navigation delay when Wireless CarPlay is on." width="800" height="480"></div>
  <figcaption>Read the confirmation before enabling Base optimizations.</figcaption>
</figure>

Turn Base off to restore Mazda’s original startup behavior at the next full start. Your Android Auto, DVD, Pandora and SiriusXM choices stay saved.

## Audio sources

Disabled entertainment integrations disappear from Mazda’s **Sources** menu after restart. Turning them on restores their usual availability.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/audio-sources.png" alt="Mazda Entertainment Sources list with disabled integrations omitted." width="800" height="480"></div>
  <figcaption>An example with Base on and Android Auto, DVD, Pandora and SiriusXM off.</figcaption>
</figure>

## Testing

These are development controls for North American version **74.00.324**. Bench checks cover saving, startup and removal. Real-car checks, Android-phone use and equipped SiriusXM/DVD playback remain unqualified. There is no public download yet.

Startup results vary by configuration. For measurements and technical details, see [Performance evidence](performance.md). A faster start than stock is not established.
