# Preparing the move to firmware 74

**Current source targets exactly 74.00.324A / cmu150_NA; release qualification
is in progress.** This records the input analysis and local porting evidence.
It does not establish a general firmware upgrade procedure. Earlier v55 releases
remain historical; there is one maintained baseline.

## Verified input

The analyzed input is Mazda's
[`cmu150_NA_74.00.324A_update.up`](https://s3.amazonaws.com/tsd.mazdausa.com/MAZDA_CONNECT/cmu150_NA_74.00.324A_update.up),
1,003,179,676 bytes, SHA-256
`ffd04e2c8cfaf77388aacde0f9c1cddc17cb6b7f02d7caa2fe6ad39c0f40e787`.
The download matched the server's `x-amz-meta-sha256`. The extracted
`/jci/version.ini` identifies `MAZ_CMU-150_74.00.324`, patch `A`, flavor `cmu150_NA`.
Analysis reads files and disassembles ARM instructions; it does not execute native
OEM programs or update a CMU. The renderer check runs extracted JavaScript in Node
with mocked dependencies. Full extracted files and disassembly stay private.

These SHA-256 values identify the principal porting inputs. Matching them is
the exact-base inputs used by the adapter, not a supported-device verdict.

| CMU path | SHA-256 |
| --- | --- |
| `/usr/bin/autostart` | `a8d019650c2a17a50b5ff39435f916c2cbeb3556af128fd913b9714b380e06bd` |
| `/jci/sm/sm.conf` | `fa3484d7c644393ab6cb083990e483201129a207e7755459296dde8ec82a4d84` |
| `/jci/sm/sm_WCP.conf` | `92034449e76689b995fcd369d584f441829a0ee6e8d74c858cd92f4049f7b27d` |
| `/jci/mmui/svcjcimmui.so` | `034d5339116aa2f2da81ec6caaf3426081c452544f3b527af3a2121b7a7e0bca` |
| `/jci/mmui/mmui_config.xml` | `ef9550fa084a34b6a997d2e488c41e50667b409fa2e6ad9c896429c74dc705f0` |
| `/jci/mmui/uia/libjciuiasystem.so` | `32431c6b74c8ba531fcc10c50748075416e0f7dc1a3f903f182d816a0f3f5fc2` |
| `/jci/lib/libjciuiamgr.so` | `1d2c6c1d583493a5b1128a52a75937c6bed720117b1344168bc9b27df6893e29` |
| `/jci/gui/index.html` | `b0e116b941f29078ced19b864a1b888cf76d8bc3e4974af081efca4693e5c420` |
| `/jci/gui/apps/system/js/systemApp.js` | `23106b04bd6bad514dd879b217a34a0f0289d58f86a0ae022488be6a022ca8e1` |
| `/jci/gui/apps/syssettings/js/syssettingsApp.js` | `a83dd588b54531475024b7cd048be1d0e11556abd68bbbcc334cc5ede7534cd1` |
| `/jci/gui/framework/js/GuiFramework.js` | `ca2889f7cb0361610e57b43004572fdd53c00d1d3003409bb92c744fcb253f70` |
| `/jci/gui/framework/js/BaseApp.js` | `1489e544e483c878fa000be378a3bbb92dcc9965aadc5029a58f3fc1147337da` |
| `/jci/lvds/lvds_service` | `19a56b9e7b9f7399b152dbc7e8bd8de3fa01f154e45e8981becec6e96d3f70eb` |

## Changes the port must make

### Startup selection

The existing normal-mode anchor is still present once in `autostart`. After that
anchor, v74 runs `get_board_type.sh` and starts the Service Manager with either
`SMCFG_NORMALMODE` (`sm.conf`) or `SMCFG_WCPMODE` (`sm_WCP.conf`). The old v55 Open
Connect hook assigned only `SMCFG_NORMALMODE`. Reusing it unchanged can leave the
wireless branch outside our selected configuration.

Preserve the actual board branch and compose from its verified original service
configuration. Do not force the normal configuration onto a wireless board or
change board detection as part of installing the two features. Include both
configuration inputs in original/dependency checks if both branches are supported
by the selected baseline. The port composes both profiles and preserves this
decision. The stock board script reads GPIOs `DI_TP1056` and
`DI_TP1029`; an asserted input selects board result 2. Capture those inputs and
the live Service Manager command line before deciding which path the unit uses.
The persistent `ublox.txt` marker alone does not establish hardware identity.

### Native disclaimer bypass

The v55 payload cannot be relocated by changing version strings. In the v74
system UI library, symbol and table analysis establishes:

| Integration point | v74 observation |
| --- | --- |
| Context machine | VA `0x83dac`: 24 columns, 166 rows, 249 cells |
| Current context | `systemCurrentContext`, VA `0x77d48` |
| Intro context | ID **1023**, column index **10**; v55 uses 1021 and index 9 |
| ShowDisclaimer event | ID **1491**, cell index **88**, one rule leading to Disclaimer 1012 |
| Disclaimer timeout continuation | Event **1502**, cell index **238**, **13 ordered rules**, VA `0x88f5c` |
| Disclaimer Yes continuation | Event **411**, cell index **239**, **12 ordered rules**, VA `0x89198` |
| Intro exit | `UIA_SYSTEM_CheckForSystemWarning`, VA `0x1db88` |
| Logo state | `uiaSystem_tranLogoState`, VA `0x8b2b0` |
| Ordinary-event callback call site | VA `0xbfb4` calls `UIAHLP_ProcessContextEvent` through PLT `0x6aac`; this carries ShowDisclaimer |
| Separate focus callback call site | VA `0x83d4` calls the same helper for focus changes |

Indices above are zero-based. The lookup array stores row/column/cell triples;
its row and column labels are one-based, while the cell index is zero-based.
The timeout continuation includes display-off restoration and CarPlay-specific
branches. The Yes continuation omits the display-off rule. Preserve the ordered
stock continuation rather than hard-coding Home or substituting the Yes path.
The manager library is a separate changed dependency. The port binds its exact
hash, checks the nested event ABI, and tests granted/denied focus in the host C
contract. Broader real startup paths remain qualification work.

The v74 executable `PT_LOAD` ends at
file offset **`0x6f79c`**, where the writable segment's file bytes immediately
begin (mapped at VA `0x7779c`). There is no file padding there for the current
append-and-extend technique. Extending the executable segment and writing our
payload there would overwrite live data. The old v55 injection offset `0x48c00`
also falls inside v74 code. The maintained port now inserts an aligned file
interval while preserving virtual addresses; its first loader check passed.
See the [port and failure evidence](../reverse-engineering.md#v74-installer-port-and-native-code-placement).
This does not qualify the complete release.

The MMUI plugin has a different layout too: its executable segment ends at
`0x3dc4` and its writable segment begins at file offset `0x4000`. The port
patches both XML-path consumers (counting and loading), using verified padding
and standard assembler-emitted length/pointer words.

### Renderer, Settings and touch

`index.html` is byte-identical to the v55 input. The system app, BaseApp and GUI
framework are not. The v74 `IntroAnimation` still has no
`noLongerDisplayedFunction`; BaseApp still supplies that lifecycle callback, and
GuiFramework hides outgoing native surfaces before calling it from
`_templateTransitionCompleteCallback`. The initial offline check inserted the old
600-byte CRLF cleanup fragment at byte
**17463**, immediately after the IntroAnimation opening brace, produces SHA-256
`d8ee047077e2ae714b57f7e4de94b7801c8d73d490ba9f9e982f1276ae9ae3c9`.
That initial candidate passed Node syntax checking and the existing
`tests/fixtures/disclaimer-behavior.js` against the actual v74 BaseApp dispatcher:
no early disposal, one completion event, stock Disclaimer cleanup, duplicate
notification handling and lost-focus cleanup. This is offline lifecycle evidence;
the subsequent CMU trial found a second cleanup requirement. V74's Disclaimer
outgoing callback also sends `NotifyDisclaimerEnd`, which stops its separate
new looping-logo surface. The first paired callback emitted both stock events
after transition completion. Its 677-byte insertion produced SHA-256
`c88a9b6053b6e1e23ceb3ccc25882281543008f369492c060f1a777357f81da8`.
A later supply-output interruption recovered its prepared preference transaction,
but the outgoing-Intro callback missed cleanup while the framework reached the
CarPlay enable dialog. The current candidate observes Mazda's completed incoming
frame instead, delegates the original callback and restores its wrapper after
handoff. It also handles a missing outgoing Intro template. Its 2148-byte insertion
produces SHA-256
61cb4085195bcc1ea6f0efdd01ab691a10b9f9cee45d32e8a78b4410c9b07f40.
Host regression checks, a local update/restart and the matched prepared-record
supply interruption pass; reviewed CI qualification remains in progress.
See the [native and visible failure evidence](../reverse-engineering.md#v74-installer-port-and-native-code-placement).
Do not reuse the v55 insertion offset or composed-file hash. Settings must
also be checked against the new `syssettingsApp.js`, including list refresh,
radio selection, Back, and the About row's positional assumptions.

The v74 LVDS function `LVDS_getSpeedRestconfigNVRAM` at VA `0x3bf9c` reads the same
`/sys/class/nvram/nv-config/keys/lvds_speed_restriction` key. Its `enable` branch
returns 1; `disable` returns 0; an unavailable setting defaults to 1. This supports
retaining the absent/enable/disable backup model. It does not prove physical
touch or CarPlay behavior, NVRAM commit semantics, or startup timing on the new
bench. Recheck these and the [separate CarPlay restriction](../reverse-engineering.md#touch-input-and-carplay-on-v74).

## Access and firmware upgrade

The extracted image retains `rungetty`, which invokes getty on `/dev/console` at
115200, and `runlogin`, which invokes `/bin/login -p`. This shows an authentication
path in the image, not working root credentials on a live unit. The packaged SSH
configuration uses port **36000**, allows root login, and explicitly disables
password authentication. It does not establish a running listener or accepted
key. Do not assume the old bench's SSH identity or authentication carries over.

The update instruction manifest includes `passwdupdate` and `neutralizeid7`
steps as well as root filesystem and boot-component updates. Their presence is
another reason not to promise retained access; their names alone do not establish
their full behavior. The broad compatibility check in `versions.ini` is not an
approved upgrade sequence.

[Mazda bulletin 09-018/22](https://static.nhtsa.gov/odi/tsbs/2022/MC-10226834-0001.pdf)
covers the 2014–2018 Mazda3, specifies 74.00.324 or later, and says rollback to
an earlier version is unavailable. It refers the actual procedure to Mazda's
MGSS update instructions. We have **not established the official intermediate
versions, power/ACC procedure or interrupted-flash recovery for the replacement's
starting firmware**. Confirm its installed version first; a unit already on the
exact target needs no firmware flash.

[Kenatia's pinned upstream release](https://github.com/Kenatia/mazda-cmu150-wcp-mod/tree/2069d1e6de20a37ef17654cb5a2fcfa9a4ffdddf)
reports USB installation on 74.00.324. That supports testing the existing small
trigger/loader on v74, but does not qualify Open Connect's complete flow. Its
wireless board spoofing is a separate modification. Preserve existing edits and
stop on mismatching original hashes rather than overwriting them.

## Replacement bench sequence

1. **Observe the stock unit first.** With the current lab parked, identify the
   replacement and adapter afresh. Capture a stock boot, actual firmware/region,
   commander behavior and physical touch on the same display and cable. Do not
   install the development profile or Open Connect before that baseline. The
   firmware's OEM part-number field is software metadata, not a physical label.
2. **Establish access and collect intake.** Distinguish UART receive, authenticated
   shell and SSH; one does not prove the others. With a confirmed shell, run
   [`cmu/bench/intake.sh`](https://github.com/aeharding/open-connect/blob/main/cmu/bench/intake.sh)
   through the existing transport. It reads identity, mount flags, board/ACC GPIOs,
   the touch setting, file hashes/metadata and relevant process mappings. It
   writes only stdout/stderr, never remounts or changes NVRAM. Keep the report
   private under `runs/`, with an external execution deadline. Missing inputs or
   process-read failures produce `INTAKE_INCOMPLETE` and exit 74; this may be an
   unsupported layout or a transient process, not a broken CMU. A changed boot ID
   exits 75. Even a complete intake is an observation, not an atomic backup or
   installation authorization.
3. **Select the next operation from the evidence.** On exact v55, the published
   development bundle remains the available installer. On exact v74, finish the
   adapter against the hashes above. For any other starting firmware, establish
   the applicable official route before flashing. Save the replacement's own
   original files and touch state; never restore the outgoing CMU's backups onto
   it. Prepare and verify independent undo through the confirmed access path.
4. **Qualify the whole selected baseline.** Verify USB insertion, Install,
   restart without USB, both Settings choices, repeated fresh ignition cycles,
   recovery, replacement-USB maintenance, Uninstall and Undo using the actual CI
   bundle. Compare stock/enabled/restored physical touch under the same reproduced
   restriction. Include last-app, display-off and CarPlay in disclaimer checks.
   Confirm actual loaded modules and original startup after undo, not just disk
   hashes. Recheck touchscreen fallback timing; the v55 recovery intentionally
   restores the preference for the next boot without requesting another restart.

For already verified SSH and a confirmed BusyBox `timeout -t` interface, a bounded
intake invocation from the checkout is:

~~~sh
mkdir -p runs/replacement-intake
# Use a verified host alias and a fresh local report name.
(set -C; ssh -T -o ConnectTimeout=10 -o ServerAliveInterval=10 \
  -o ServerAliveCountMax=2 my-cmu 'timeout -t 60 sh -s' \
  < cmu/bench/intake.sh > runs/replacement-intake/stock.txt 2>&1)
~~~

UART-only intake uses the existing verified RAM staging/file-transfer path and a
short guarded execution command with a host deadline; do not paste this whole
script as a single UART input line. Neither transport requires a new `oc` command.

Firmware/access work remains in [#2](https://github.com/aeharding/open-connect/issues/2),
physical touch in [#60](https://github.com/aeharding/open-connect/issues/60), and
the production installer qualification in [#7](https://github.com/aeharding/open-connect/issues/7).
