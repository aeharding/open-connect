# Native wireless CarPlay

**Mazda's v74 firmware already contains wireless CarPlay and a Wi-Fi mode
selector.** The installed dev.8 candidate reached native wireless projection while
preserving the CMU's actual board and generated vehicle/GPS values.

This page records source-backed findings on **North American 74.00.324A**, the
initial narrow trial and installed development checks. The maintained
[Wireless CarPlay control](../wireless-carplay.md) remains a development candidate.
This does not establish physical-input/audio performance, vehicle behavior or
long-parked startup timing.

The owner will uninstall the existing wireless mod before the first Open Connect
installation. The installer requires the supported OEM files. Wireless work
follows the initial release, Developer options and measured Services work;
the existing mods are research references, not compatibility targets.

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

## Narrow enablement result

The successful trial changed six service arguments: MMUI, USB manager, CarPlay,
BDS, BCA and BLM NMS receive their corresponding OEM wireless arguments. Network
startup selects the OEM WCP firewall mode. GPS/location, AAPA hardware selection,
navigation dependencies and original retry/reset policy remain unchanged.

After VBS renders `/tmp/devmgr_config_edit.xml`, one finite process changes
`bWifiSupport` and `bOOBSupport` from FALSE to TRUE. Device Manager waits for its
ready flag before reading that same XML path. Independent before/after byte
comparison found precisely those two value substitutions; every other generated
byte was preserved. The physical master, EEM module, board script, SM profiles
and Device Manager module were unchanged. Native parsing and service lifecycle
remain Mazda's own implementation.

Mazda's native Devices menu then exposed Wi-Fi and the CarPlay page. Selecting
Apple CarPlay started a channel-6 AP. The owner re-paired the iPhone's Bluetooth
connection to enable its wireless Connect button, connected wirelessly, then
moved phone USB to the Mac. Independent intake found no CMU phone USB link, one
Wi-Fi station exchanging traffic and a visible CarPlay dashboard on the physical
display. Later USB inspection identified `iPhone8,4`, iOS **15.8.8**. This setup
observation does not establish that all existing pairings must be replaced.

The original startup inode and read-only physical root were restored before a
separate stock ACC start. That start restored both FALSE values, stopped the AP
and returned the radio to managed mode after entering the test with Mazda's
CarPlay Wi-Fi preference selected. Saved-mode and pairing reuse still need
reconnection checks. This supports the off-path mechanism;
the installed candidate has the separate checks below.

The authored [playground source](https://github.com/aeharding/open-connect/tree/bc9761a/cmu/bench)
retains the initial filters and observed scope. Private captures, generated XML,
OEM source and pairing material are excluded. Its first attempt stopped before
selection when an early root read-only remount returned `EBUSY`; post-startup
restoration passed. That was a boot-trial tooling failure, not a wireless result.

## Finite preparation and cancellation

The maintained helper uses a supervisor and a worker in a separate session.
Before any preparation, the worker acknowledges its PID and waits on inherited
FIFO descriptors. The supervisor verifies its parent, process group and session,
then records that cancellation can stop the group before authorizing preparation.
This closes the launch race where cancellation could otherwise kill the launcher
while leaving XML preparation running. Read/write FIFO opens do not wait for a
peer on this CMU. Timed reads bound a missing acknowledgement.

On the first installed boot, Service Manager logged that it unlinked the ready
flag when the one-shot process stopped. That flag is a startup dependency signal;
it is not a persistent status marker. Current availability uses the selected
snapshot and the separate per-boot applied-policy result.

The observed BusyBox 1.19.2 timeout sends TERM to the supervisor PID. Cancellation
stops preparation before releasing Device Manager; applied status reflects the
actual XML on either side of its atomic rename. A separate synthetic native check
exercised normal and malformed inputs, delayed filtering, both sides of rename,
and three launch/authorization boundaries. All eight cases passed. The six
one-second-timeout cases released in **1.04–1.06 seconds**, with unchanged hashes
five seconds later. Physical originals and the kernel remained unchanged.
This qualifies those failure paths, not installed projection or startup performance.
Private provenance is in `runs/wireless-enable-20261121/native-r1b-identity.json`
and `native-r1b.out`; maintained host coverage is `tests/test_installer_wireless.py`.

## Installed development candidate

The **0.3.0-dev.8** payload from
[CI 44942234519](https://github.com/aeharding/open-connect/actions/runs/44942234519),
source [c25d5202](https://github.com/aeharding/open-connect/tree/c25d5202ddebfed15b2f3eab8cccedb54a244dad),
was installed through the normal maintenance UI on the matching bench. The SD
manual launch was used; this is separate from earlier physical USB-insertion
qualification. All 37 public manifest entries matched the installed runtime.

| Identity | Value |
| --- | --- |
| CI artifact | `14722505940` |
| USB ZIP SHA256 | `e34a91136e526f97f77f67d3455d625bef77b85dec831506ba9059fa2e99c835` |
| Public manifest SHA256 | `3e0d04f7b4af47e0cffffba3ebea52fe8da4631cdb8c1447f77ddd2436948150` |

The dev.7 → dev.8 update retained every existing choice, imported SSH key and
original baseline; Wireless started off. Native Enable/Disable confirmations and
Cancel behaved correctly. Full ACC starts applied each selection. With Wireless
on, the generated XML differed in precisely the two capability values, and all
physical dependencies remained original with root read-only. Selecting the native
Apple CarPlay mode reused the existing Bluetooth pairing and reached visible
projection with no CMU phone USB link and one active Wi-Fi station. A repeated
full ACC start retained that mode and returned to projection without further UI
or phone actions. These were two enabled starts, not a long-run reliability test.

Disable restored both original capability values and managed radio mode, with
no active station or applied-policy marker. A same-version reinstall retained
Wireless on and all other choices/key. Normal menu uninstall from that enabled
state restored 19 originals with metadata, the three added read-only dependencies
and original loaded startup after restart. It removed product state and imported
key access while preserving independent bench access. A subsequent fresh install
restored all documented defaults with Wireless/Base/UART/SSH off and Pandora on.

Private checks are under `runs/wireless-enable-20261121/`: `dev8-upgrade-check.out`,
`installed-wireless-on{1,2}/`, `installed-wireless-off/postboot.out`,
`dev8-reinstall-check.out`, `final-uninstall/closure-stock.json` and
`fresh-dev8-check.out`. Reviewed native guide images have
[separate provenance](../assets/guide/README.md). Raw projection frames, generated
OEM XML and access material remain private. Physical input, audio, vehicle
behavior and long-parked reliability remain unqualified. The later final dev.8
artifact has a separate [wireless ACC timing/RAM baseline](../wireless-comparison.md),
including incomplete retrievals and a watchdog restart; those are not results
of the earlier C25 lifecycle checks.

## Recognize factory wireless

The final UI adds read-only `wirelessFactory` status from the hash-verified OEM
`get_board_type.sh` result: exit 2 selects Mazda's factory wireless branch.
The script reads `DI_TP1056` and `DI_TP1029`; generated RAM capability flags are
not used for this decision. Our override therefore cannot make a non-factory
unit identify itself as factory wireless. A factory row is checked and disabled,
labeled **factory enabled**, without changing the saved override or adding a
durable record. The factory branch is covered by host fixtures; this bench is
non-factory, so actual factory hardware remains untested.

## Internet and the OEM menu

The saved `netmgmtApp.js` has two menu variants:

- **Off / Apple CarPlay**
- **Off / Apple CarPlay / Connected Services**

CarPlay maps to Wi-Fi access-point mode; Connected Services maps to client mode.
Selections send Mazda's normal `SelectWifiMode` event. This supports investigating
the user's preferred explicit switch to a hotspot and back.

The tested North American UI exposes only **Off / Apple CarPlay**.
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
