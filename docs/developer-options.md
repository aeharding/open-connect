# Developer options

Use direct SSH or UART access to the head unit for your own purposes. Neither is needed for normal installation, settings or removal.

**<span class="oc-nav-path" data-walkthrough="developer-options">Mazda Settings → System → Open Connect → Developer options</span>**

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-developer-options.png" alt="Developer options highlighted in the Open Connect menu." width="800" height="480"></div>
  <figcaption>Developer options highlighted (dev.19).</figcaption>
</figure>

- **Default**: <span class="oc-default oc-default--off">UART Off; SSH Off</span>; no Open Connect public key imported.
- **Startup & RAM impact**: **Neutral** — no isolated access-toggle startup or RAM benchmark is established.
- **Trade-offs & boot implications**: UART enables a passwordless root serial shell; SSH authorizes your imported key. Changes you leave on head-unit storage can prevent maintenance. Diagnostic logging is separate from interactive login.
- **Applies**: Saved automatically; takes effect on the **next full Mazda Connect startup**. See [restart guidance](settings.md#apply-changes).
- **Evidence & limits**: [Access and restoration bench checks](reverse-engineering.md#developer-access-and-login-script-lifetime-on-v74) cover earlier builds. [Performance evidence](performance.md) has no isolated access comparison. Dev.19 UI bench captures on **74.00.324A NA**; real-car qualification and matched dev.19 benchmarks remain pending. No public download yet.

Restore any changes you make to head-unit storage before installing, upgrading or uninstalling Open Connect. Leaving storage modified can make these operations fail. If you cannot return it cleanly to stock, reinstall Mazda firmware **74.00.324 NA N** first.

## UART

UART is for bench work with the CMU out of the dashboard and jumper wires connected to blue connector 2.

Enables **passwordless root shell access** over the CMU’s physical serial port (`115200` baud, `8N1`, no flow control). Turning it off restores Mazda’s original authenticated serial login without changing passwords or suppressing diagnostic output.

Connect a **3.3 V TTL USB-to-UART adapter** to the CMU’s blue connector 2:

- **2S (CMU TX) → adapter RX**
- **2T (CMU RX) → adapter TX**
- **2C, 2D, or 2L (CMU GND) → adapter GND**
- Leave the adapter’s VCC and handshake lines disconnected.

See [Wire a bench — pin maps](bench-setup.md#pin-maps) and [UART cables](bench-setup.md#cables) for full diagrams.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/uart-console.png" alt="Enable UART confirmation explaining passwordless root access and that changes apply after restart." width="800" height="480" loading="lazy"></div>
  <figcaption>Enabling UART explicitly confirms passwordless root serial access.</figcaption>
</figure>

## SSH

Authorizes your imported public key on Mazda’s built-in SSH server (port **36000**, account `cmu`) while leaving any pre-existing SSH keys untouched. Turning SSH off removes Open Connect’s key authorization on the next full restart.

SSH requires a network path to the CMU — enabling it does not configure Wi-Fi. Plug a supported **USB-to-Ethernet adapter** into the Mazda USB hub’s front data port on the same network as your computer (see [network cables](bench-setup.md#cables)).

### Import a public key

Mazda’s SSH server supports **ECDSA** and **RSA (2048-bit or larger)** keys — it does not support Ed25519. ECDSA avoids legacy RSA signature options on modern SSH clients:

```sh
ssh-keygen -t ecdsa -b 256 -f ~/.ssh/open-connect
```

1. Keep the private key (`~/.ssh/open-connect`) on your computer.
2. Copy **only** `~/.ssh/open-connect.pub` to the root of a FAT32 USB drive and rename it to **`open-connect.pub`**.
3. Insert the drive, select **Import public key**, and confirm **Import**.
4. Verify all 16 MD5 fingerprint pairs shown on screen against your computer:

```sh
ssh-keygen -E md5 -l -f ~/.ssh/open-connect.pub
```

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/ssh-key-imported.png" alt="Public key imported confirmation showing the complete MD5 fingerprint across two lines." width="800" height="480" loading="lazy"></div>
  <figcaption>Compare the complete MD5 fingerprint with your local public key before connecting.</figcaption>
</figure>

After enabling **SSH** and restarting, connect with:

```sh
ssh -p 36000 -i ~/.ssh/open-connect cmu@CMU_ADDRESS
```

Importing a new key replaces only the previously imported Open Connect key; private keys, key options, and multi-key files are rejected.

## Uninstall and recovery

Normal [Uninstall](uninstall.md) restores your saved login and SSH configuration and removes imported keys along with the rest of Open Connect. USB maintenance always stays independent of developer access.

[Back to Settings](settings.md)
