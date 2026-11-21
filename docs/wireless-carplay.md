# Wireless CarPlay

The v74 development candidate adds **Wireless CarPlay** under **Mazda Settings →
System → Open Connect**. It defaults off. Enabling it makes Mazda's native
wireless controls available after a full restart, while retaining the CMU's
actual hardware identity and GPS configuration.

The maintained candidate is still under qualification. A separate narrow bench
trial reached visible wireless projection; this is not a vehicle, audio, input
latency or long-parked startup result. See the [source findings](cmu/wireless-carplay.md).

## Connect an iPhone

1. Check **Wireless CarPlay**, confirm **Enable**, then let Mazda Connect shut
   down fully before starting again. A quick ignition off/on can resume the old
   session.
2. Open **Mazda Settings → Devices → Wi-Fi** and select **Apple CarPlay**.
3. Keep Wi-Fi and Bluetooth enabled on the iPhone and pair it with Mazda Connect.
   Accept the phone's wireless CarPlay prompt if offered.
4. Select your iPhone under **Devices → Apple CarPlay** and connect.

In the first bench trial, the existing Bluetooth pairing left Connect disabled;
re-pairing made it available. If that happens, re-pair that iPhone. Other devices
do not need to be removed.

On the tested North American configuration, Mazda's Wi-Fi choices are **Off**
and **Apple CarPlay**. Joining a phone/home hotspot through Connected Services
remains under investigation; it is not exposed by this setting.

## Disable or remove

Clear **Wireless CarPlay** and confirm **Disable** to restore the CMU's original
wireless availability after the next full restart. Updating retains your choice.
Uninstall restores pre-install startup; the restart clears the RAM configuration.
The current session continues until it shuts down.

Mazda retains its Wi-Fi preference and paired phones. This option does not erase
those choices or replace Mazda's own Wi-Fi mode control. The first stock-start
check stopped the AP and restored both original capability values despite the
CarPlay Wi-Fi preference selected before that start.

Performance comparisons, repeated reconnection and maintained installer
qualification are separate work. No cold-start improvement is claimed yet.
