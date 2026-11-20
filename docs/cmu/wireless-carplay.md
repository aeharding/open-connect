# Native wireless CarPlay

**Mazda's v74 firmware already contains wireless CarPlay and a Wi-Fi mode
selector.** The research question is how to enable the needed capabilities on
older hardware without pretending the whole CMU is a different board.

This is source-backed research on **North American 74.00.324A**, not a working
Open Connect wireless feature. The maintained installer targets that exact
baseline; [release qualification](../installer-development.md#qualification)
and native wireless enablement are separate work.

## What the existing mods change

We inspected the two implementations the user tried:
[Kenatia](https://github.com/Kenatia/mazda-cmu150-wcp-mod/tree/2069d1e6de20a37ef17654cb5a2fcfa9a4ffdddf)
and [luxubuok](https://github.com/luxubuok/mazda-carplay-wireless-enable/tree/934b362769854f9469a7a992bbd82a6cdae1ef46).

They change board-detection behavior according to the caller and select Mazda's
wireless startup configuration. They also adjust GPS/navigation configuration
and service reset policy. This enables more than a single menu option.

Both produced similar cold-start lag for the user. **That does not establish
that spoofing causes the lag.** Cleaner enablement and performance diagnosis
are separate tasks.

## The narrower leads

| OEM component | Finding | Implication |
| --- | --- | --- |
| `autostart` | Board detection controls an UBLOX marker and selection of `sm.conf` versus `sm_WCP.conf`. | Replacing board detection has effects outside CarPlay. |
| Service Manager configuration | The two configurations differ in 12 service entries, including MMUI, CarPlay, USB, Bluetooth, networking, GPS and navigation. | Determine the necessary subset; do not copy all differences blindly. |
| Device Manager configuration | `bWifiSupport` and `bOOBSupport` use the `@board@` placeholder. EEM renders it while also choosing location-reporting values. | Investigate changing these capability fields independently of GPS/board reporting. |
| MMUI startup | Its `wcp` service argument sets an internal WCP status. | There is an explicit service-level input to trace. |

The proposed experiment is a selected boot configuration with narrowly scoped
wireless capabilities and required service arguments, while preserving actual
hardware detection, GPS behavior and OEM reset policy. These leads are **not
yet proven sufficient**; Device Manager consumers and the remaining service
gates still need tracing before building the candidate.

## Internet and the OEM menu

The saved `netmgmtApp.js` has two menu variants:

- **Off / Apple CarPlay**
- **Off / Apple CarPlay / Connected Services**

CarPlay maps to Wi-Fi access-point mode; Connected Services maps to client mode.
Selections send Mazda's normal `SelectWifiMode` event. This supports investigating
the user's preferred explicit switch to a hotspot and back.

We have not established which native region/capability checks expose the
three-option menu on this hardware, or verified usable internet and CarPlay
reconnection. Menu code alone does not prove either.

[The measurement plan](../carplay-testing.md) targets the cold-start black screen
and delayed inputs. Work is tracked in [#8](https://github.com/aeharding/open-connect/issues/8)
and [#54](https://github.com/aeharding/open-connect/issues/54).

## Firmware source

Analysis used Mazda's hosted
[`cmu150_NA_74.00.324A_update.up`](https://s3.amazonaws.com/tsd.mazdausa.com/MAZDA_CONNECT/cmu150_NA_74.00.324A_update.up):
1,003,179,676 bytes, SHA-256:

```text
ffd04e2c8cfaf77388aacde0f9c1cddc17cb6b7f02d7caa2fe6ad39c0f40e787
```

The downloaded hash matches its `x-amz-meta-sha256` response metadata.
The initial package-analysis trial extracted files without executing firmware
scripts or upgrading a CMU. The later replacement-unit upgrade and owner-key
access have a [separate record](../reverse-engineering.md#owner-key-access-after-the-replacements-v74-upgrade).
The package identity is not an upgrade recipe or proof of applicability to every
unit.

Key anchors: EEM `GetBoardType` at `0xee8c`, configuration writers at
`0xf3c8` and `0xfd2c`; `/etc/devmgr_config_master.xml`;
MMUI `ServiceInit`; `netmgmtApp.js` modes and selection handler.
Private hashes, service diff and slices are indexed in
`runs/firmware74-research/boundary-result.json`.
