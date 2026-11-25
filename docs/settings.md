# Settings

Open **Mazda Settings → System**, scroll near the bottom, and select **Open Connect** (right above **About**).

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/settings-entry.png" alt="Mazda Settings with the System tab selected and Open Connect highlighted just above About." width="800" height="480"></div>
  <figcaption>Open Connect appears natively inside Mazda’s System settings tab.</figcaption>
</figure>

## What each setting does

Every preference is saved automatically as soon as you choose or confirm it, and updating Open Connect later preserves all of your choices.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/settings.png" alt="Open Connect settings with Touchscreen While Driving, Startup disclaimer, Wireless CarPlay, Services and Developer options visible." width="800" height="480" loading="lazy"></div>
  <figcaption>Current selections appear beside each item. Scroll down for Uninstall and About.</figcaption>
</figure>

| Setting | Default | Why it exists &amp; what it changes |
| --- | --- | --- |
| [**Touchscreen While Driving**](touchscreen.md) | **Allow** | Mazda locks touchscreen input above ~5 mph. **Allow** keeps touch working while moving; **Factory Default** restores your pre-install behavior. |
| [**Startup disclaimer**](disclaimer.md) | **Skip** | Mazda pauses every boot on a legal warning. **Skip** goes straight to your normal screen; **Show** keeps the stock warning. |
| [**Wireless CarPlay**](wireless-carplay.md) | **Off** | Turns on Mazda’s native wireless CarPlay option on non-factory units so you can pair an iPhone wirelessly through Mazda’s Wi-Fi menu. On factory-wireless hardware it shows **factory enabled** automatically. |
| [**Services**](services.md) | Base **Off** · DVD **Off** · others **On** | Lets you enable **Base optimizations** (less logging, dead regional services stopped, faster startup) and individually disable unused integrations (**Android Auto**, **DVD**, **Pandora**, **SiriusXM**). |
| [**Developer options**](developer-options.md) | **Off** | Optional **UART** root console and **SSH** key login over USB-Ethernet for contributors and diagnostics. Leave off for normal driving. |
| [**Uninstall**](uninstall.md) | — | Restores your pre-install files and settings, removes Open Connect, and restarts Mazda Connect automatically. |
| **About** | — | Displays your installed Open Connect version. |

## How changes take effect

Settings changes apply on the **next full Mazda Connect startup**:

- **Saved vs. active:** If a setting has been saved for the next start but isn’t active yet in the current session, Open Connect labels it **restart needed**.
- **Full shutdown:** Switch the ignition off and let Mazda Connect power down completely before starting again. A quick off/on can wake the previous running session without reloading startup settings.
- **Unconfirmed save:** If Mazda Connect can’t confirm a save, reopen **Open Connect** to check the displayed choice before trying again.
