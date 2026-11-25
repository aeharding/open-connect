<span id="services"></span>

# Startup optimizations

Reduce background logging and stop unused services at startup. This setting was previously called **Base optimizations**; your saved choice is kept.

Open **<span class="oc-nav-path" data-walkthrough="startup-optimizations">Mazda Settings → System → Open Connect → Startup optimizations</span>**. It defaults to **Off**. Changes apply on the next full startup.

<span id="base-optimizations"></span>

**Impact:** Faster in earlier wired bench tests: about 3.8 s earlier to the CarPlay dashboard with the dev.7 preset on.<br>
**Trade-off:** Stops Aha, Stitcher, DAB and TV. With Wireless CarPlay on, Mazda Navigation starts about 20 s later, even if no phone connects.<br>
**Evidence:** [Performance evidence](performance.md): dev.7 had +9.9 MiB minimum MemFree and +2.58 MiB ending free RAM. Later builds changed the preset; final dev.18 pre-car figures will replace these earlier comparisons.

Confirm **Enable** or **Disable** when prompted. Turning Startup optimizations off restores Mazda’s original logging and startup behavior at the next full start. Your Android Auto, DVD, Pandora and SiriusXM choices stay saved. Leave it off if you want Mazda’s usual Navigation startup timing.

<span id="phone-and-entertainment"></span>

## CarPlay & Android Auto

Open **<span class="oc-nav-path" data-walkthrough="phone-connections">Mazda Settings → System → Open Connect → CarPlay &amp; Android Auto</span>** for [Wireless CarPlay](wireless-carplay.md), [Show CarPlay on connection](carplay-on-connection.md) and Android Auto. These are independent choices.

### Android Auto

Built-in Android Auto support defaults to **On**. Turn it off if you do not use it; turning it back on restores it after a full restart.

**Impact:** Neutral — no measured startup or free-RAM gain is established.<br>
**Trade-off:** Turning it off makes built-in Android Auto unavailable. CarPlay, Bluetooth audio, USB music and CDs still work.<br>
**Evidence:** [Performance evidence](performance.md) covers combined configurations; it does not establish an isolated Android Auto speed or RAM gain.

## Audio sources

Open **<span class="oc-nav-path" data-walkthrough="audio-sources">Mazda Settings → System → Open Connect → Audio sources</span>**. Disabled integrations disappear from Mazda’s **Sources** menu after restart. Turning them back on restores their usual availability, subject to Mazda’s hardware and connection requirements.

### DVD

In-dash DVD video support defaults to **Off**.

**Impact:** Neutral — no measured startup or free-RAM gain is established.<br>
**Trade-off:** Turning it off hides DVD from Sources and stops DVD video support. Audio CDs and CarPlay still work.<br>
**Evidence:** [Performance evidence](performance.md) has no isolated DVD startup or RAM comparison.

### Pandora

Mazda’s built-in Pandora integration defaults to **On**.

**Impact:** Neutral for startup in the measured comparison; turning it off left about 3.2 MiB more minimum MemFree.<br>
**Trade-off:** Turning it off hides Mazda’s Pandora integration from Sources. Pandora through CarPlay or Bluetooth and CD audio still work.<br>
**Evidence:** [Performance evidence](performance.md): five starts per choice on dev.6; wired dashboard timing differed by less than camera resolution. Final dev.18 pre-car figures remain to be refreshed.

### SiriusXM

Satellite radio and SiriusXM data services default to **On**.

**Impact:** Neutral — no measured startup or free-RAM gain is established.<br>
**Trade-off:** Turning it off hides SiriusXM from Sources and stops satellite radio and data. CarPlay and CDs still work.<br>
**Evidence:** [Performance evidence](performance.md) has no isolated SiriusXM startup or RAM comparison.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/audio-sources.png" alt="Mazda Entertainment Sources list with disabled integrations omitted." width="800" height="480"></div>
  <figcaption>Mazda’s Sources list with unused integrations turned off.</figcaption>
</figure>

## Testing

These are development controls for North American version **74.00.324**. Earlier builds have bench checks for saving, startup and removal, and the dev.19 menu layout has live 800×480 bench captures and Settings Uninstall verification. Real-car checks, Android-phone use, equipped SiriusXM/DVD playback and matched dev.19 benchmarks remain ahead. There is no public download yet.

Startup results vary by configuration. See [Performance evidence](performance.md) for the complete measurements. A faster start than stock is not established.
