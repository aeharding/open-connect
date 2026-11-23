# Wireless CarPlay

The v74 development candidate adds **Wireless CarPlay** under **Mazda Settings →
System → Open Connect**. It defaults off. Enabling it makes Mazda's native
wireless controls available after a full restart, while retaining the CMU's
actual hardware identity and GPS configuration.

The installed dev.8 CI candidate reached visible wireless projection and
reconnected after a full restart without phone or menu actions. Installation,
updates, controls and restoration have software bench checks. Vehicle behavior,
audio, physical input and long-parked startup remain unqualified. See the
[qualification record](cmu/wireless-carplay.md#installed-development-candidate).

If your hardware already has factory wireless CarPlay, the checkbox is checked
and disabled, labeled **factory enabled**. Use Mazda's Wi-Fi menu to connect;
Open Connect does not need to enable it.

## Connect an iPhone

1. Check **Wireless CarPlay**, confirm **Enable**, then let Mazda Connect shut
   down fully before starting again. A quick ignition off/on can resume the old
   session.
2. Open **Mazda Settings → Devices → Wi-Fi** and select **Apple CarPlay**.
3. Keep Wi-Fi and Bluetooth enabled on the iPhone and pair it with Mazda Connect.
   Accept the phone's wireless CarPlay prompt if offered.
4. Select your iPhone under **Devices → Apple CarPlay** and connect.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/wireless-enable.png" alt="Enable Wireless CarPlay confirmation explaining restart, Mazda Wi-Fi settings and Bluetooth pairing, with Cancel and Enable buttons." width="800" height="480"></div>
  <figcaption>Enable the option, then finish setup in Mazda's own menus.</figcaption>
</figure>

In the first bench trial, the existing Bluetooth pairing left Connect disabled;
re-pairing made it available. If that happens, re-pair that iPhone. Other devices
do not need to be removed.

On the tested North American configuration, Mazda's Wi-Fi choices are **Off**
and **Apple CarPlay**. Joining a phone/home hotspot through Connected Services
remains under investigation; it is not exposed by this setting.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/wireless-mode.png" alt="Mazda Wi-Fi mode selector with Off and Apple CarPlay choices." width="800" height="480" loading="lazy"></div>
  <figcaption>Select Apple CarPlay in Mazda Settings → Devices → Wi-Fi.</figcaption>
</figure>

## Disable or remove

Clear **Wireless CarPlay** and confirm **Disable** to restore the CMU's original
wireless availability after the next full restart. Updating retains your choice.
Uninstall restores pre-install startup; the restart clears the RAM configuration.
The current session continues until it shuts down.

Open Connect leaves Mazda's Wi-Fi preferences and paired-phone records alone;
Mazda still controls its own Wi-Fi mode. The installed bench reused its existing
pairing and retained Apple CarPlay mode across a repeated enabled start. Disabling
the override restored the original unavailable state on this non-factory unit.
On factory-wireless hardware, factory availability remains intact.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/wireless-disable.png" alt="Disable Wireless CarPlay confirmation explaining that original behavior returns after restart, with Cancel and Disable buttons." width="800" height="480" loading="lazy"></div>
  <figcaption>Disable restores the original availability after a full restart.</figcaption>
</figure>

With both Base optimizations and Wireless CarPlay enabled, dev.13 also adjusts
wireless startup scheduling. A [three-start-per-version comparison](wireless-startup-speed.md)
reached visible Maps about 2.21 seconds earlier, with higher CPU use and no resolved
Home or RAM improvement. This does not qualify long-parked startup or usable input.

A separate [wireless startup baseline](wireless-comparison.md) compares Base
optimizations off/on, including its failed attempts. Long-parked startup
improvement remains unqualified.
