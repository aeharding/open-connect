# Developer options

Implemented in the **74.00.324A NA** development candidate. See
[Quick start](usb-installer.md) for qualification and availability; a qualified
v74 download is not published yet.

Open **Mazda Settings → System → Open Connect → Developer options**.
Both access options start **off**. Checkboxes show your saved choices.
The enable popup explains the restart requirement. Changes take effect
after a full Mazda Connect restart, including disabling access.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/developer-options.png" alt="Developer options with UART and SSH off and Import public key available." width="800" height="480"></div>
  <figcaption>Fresh installations leave both access options off.</figcaption>
</figure>

## UART

**UART** provides passwordless root access over the serial connection.
Confirm **Enable**, then restart.
Use 115200 baud, 8 data bits, no parity, 1 stop bit and no flow control.

Use a **3.3 V TTL USB-to-UART adapter** connected to the CMU's blue connector 2:
**2S (CMU TX) → adapter RX**, **2T (CMU RX) → adapter TX**, and common ground
**(CMU 2C, 2D or 2L) → adapter GND**. Leave the adapter's VCC and handshake
pins disconnected.
See the [connection guide and pin maps](bench-setup.md#pin-maps) for connector
orientation and ground pins, and its [UART cable instructions](bench-setup.md#cables).

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/uart-console.png" alt="Enable UART confirmation explaining passwordless root access and that changes apply after restart." width="800" height="480" loading="lazy"></div>
  <figcaption>Confirm Enable, then restart Mazda Connect.</figcaption>
</figure>

Turning it off restores the original authenticated login behavior. It does not
change passwords or turn off diagnostic output. The checkbox does not set a
password.

## SSH

Import your own public key, enable **SSH**, then restart. This uses
Mazda's existing SSH server on port **36000** and preserves its existing key
authorization. Turning it off removes the Open Connect key's authorization after
restart; any access configured before installing Open Connect is preserved.

SSH also needs a working network connection to the CMU. Enabling this option
does not configure Wi-Fi. You can use a **supported USB-to-Ethernet adapter** in
the Mazda USB hub's front data port, connected to the same router or switch as
your computer; see the [network connection guide](bench-setup.md#cables).
Use the CMU's address on that network and the account name **cmu**. Adapter
driver support is required; not every USB network adapter will work.

### Import a public key

The supported firmware accepts ECDSA keys and RSA keys of at least 2048 bits.
Its old SSH server does not support Ed25519. ECDSA avoids the legacy RSA
signature settings that some modern SSH clients require.

For example, create a dedicated key on your computer:

```sh
ssh-keygen -t ecdsa -b 256 -f ~/.ssh/open-connect
```

Keep `~/.ssh/open-connect` on your computer. Copy only
`~/.ssh/open-connect.pub` to the root of a FAT32 USB drive, naming the copy
**open-connect.pub**. Insert the drive, choose **Import public key**, then
confirm **Import**. The confirmation displays the imported key's MD5 fingerprint.
Compare all 16 pairs, across both lines, with the public key on your computer:

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/ssh-key-imported.png" alt="Public key imported confirmation showing the complete MD5 fingerprint across two lines." width="800" height="480" loading="lazy"></div>
  <figcaption>Verify the fingerprint against the key on your computer.</figcaption>
</figure>

```sh
ssh-keygen -E md5 -l -f ~/.ssh/open-connect.pub
```

Import replaces the previously imported Open Connect key. It leaves Mazda's
keys intact and keeps the SSH checkbox's current selection. Use one drive with
one public key; key options, private keys and files containing multiple keys
are refused. After enabling access and restarting, connect with:

```sh
ssh -p 36000 -i ~/.ssh/open-connect cmu@CMU_ADDRESS
```

## Uninstall and recovery

Normal [Uninstall](uninstall.md) restores the saved login and SSH configuration
and removes imported keys with the rest of Open Connect. It refuses conflicting
later edits. USB maintenance remains available independently of developer access.
Neither option is required for normal installation or removal.
