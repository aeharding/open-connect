# Backup & restore

Export your Open Connect preferences to a plain-text file on a USB drive, restore them later, or include them on an installer USB drive as a fresh-install preset.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="backup-restore">Open Connect → Backup &amp; restore</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd>—</dd>
  </div>
  <div>
    <dt>Impact</dt>
    <dd>On demand</dd>
  </div>
  <div>
    <dt>Applies</dt>
    <dd>Import applies next full startup</dd>
  </div>
</dl>

## Notes

<p>Preferences are stored in a plain-text file named <code>open-connect.prefs</code> at the root of a single FAT32 USB drive. Insert only one USB drive while exporting or importing.</p>

<p>For safety, <code>open-connect.prefs</code> only includes normal Open Connect feature toggles — it never exports or imports Developer options (UART, SSH, or SSH public keys). Choices imported in Settings apply on the <strong>next full Mazda Connect startup</strong> (use <a href="apply-changes.md">Apply changes</a> to restart right away). Verified on live v74 bench hardware in <strong>0.3.0-dev.27</strong> (<strong>74.00.324A NA</strong>); real-car qualification remains pending.</p>

## Export preferences

1. Insert a single **FAT32** USB drive.
2. Open **<span class="oc-nav-path" data-walkthrough="backup-restore">Settings → System → Open Connect → Backup &amp; restore</span>**.
3. Select **Export preferences** and confirm **Export**.

Open Connect writes `open-connect.prefs` at the root of the USB drive (replacing any existing `open-connect.prefs`).

## Import preferences

1. Place `open-connect.prefs` at the root of a single **FAT32** USB drive and insert it.
2. Open **<span class="oc-nav-path" data-walkthrough="backup-restore">Settings → System → Open Connect → Backup &amp; restore</span>**.
3. Select **Import preferences** and confirm **Import**.
4. Use [Apply changes](apply-changes.md) to restart Mazda Connect, or let the imported choices take effect on the next full startup.

If the file matches your already saved settings, Open Connect leaves your installation unchanged and no restart is needed. On units with factory wireless CarPlay enabled, a file requesting Open Connect’s Wireless CarPlay override is rejected instead of overriding factory wireless.

## Fresh-install preset

To apply your preferred settings automatically during a **fresh installation**:

1. Prepare an installer USB drive as described in [Quick start](usb-installer.md#2-prepare-a-usb-drive).
2. Copy your `open-connect.prefs` file to the **root** of that same USB drive (next to `jci-autoupdate` and the `open-connect` folder).
3. Install Open Connect normally.

Open Connect validates `open-connect.prefs` before changing system storage and applies those choices to the initial installation. Updates and reinstalls ignore `open-connect.prefs` and keep your currently saved settings.

## File format (`OCPREFS1`)

`open-connect.prefs` is plain text (up to 1023 bytes). Blank lines and `#` comments are allowed; keys not listed below or invalid values cause import or fresh install to refuse the file without making changes.

```ini
OCPREFS1
# Optional comments start with #
base=0
carplay-autoshow=0
hold-scroll=0
menu-loop=0
service.android-auto=1
service.pandora=1
service.siriusxm=1
source-order=0
touch=1
warning=1
wireless=0
```

| Key | Allowed values | Meaning |
| --- | --- | --- |
| `base` | `0`, `1` | [Startup optimizations](startup-optimizations.md) (`0` Off, `1` On) |
| `carplay-autoshow` | `0`, `1` | [Show CarPlay on connection](carplay-on-connection.md) (`0` Factory, `1` Auto) |
| `hold-scroll` | `0`, `1` | [Commander Dial — Faster hold-scroll](commander-dial.md#faster-hold-scroll) |
| `menu-loop` | `0`, `1` | [Commander Dial — Wrap-around menus & lists](commander-dial.md#wrap-around-menus-lists) |
| `service.android-auto` | `0`, `1` | [Android Auto](android-auto.md) (`0` Off, `1` On) |
| `service.pandora` | `0`, `1` | [Pandora](pandora.md) (`0` Off, `1` On) |
| `service.siriusxm` | `0`, `1` | [SiriusXM](siriusxm.md) (`0` Off, `1` On) |
| `source-order` | `0`, `1` | [Source order](source-order.md) (`0` Factory order, `1` Phone & media first) |
| `touch` | `0`, `1`, `2` | [Touchscreen](touchscreen.md) (`0` Factory, `1` Always enabled, `2` Always disabled) |
| `warning` | `0`, `1` | [Startup disclaimer](disclaimer.md) (`0` Show, `1` Skip) |
| `wireless` | `0`, `1` | [Wireless CarPlay](wireless-carplay.md) (`0` Off, `1` On; refused if factory wireless is enabled) |

Any omitted key keeps its default value on a fresh install or its current saved value during **Import preferences**.

[Back to Settings](settings.md)
