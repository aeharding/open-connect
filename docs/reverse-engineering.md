# Mazda Connect findings

Evidence is for **55.00.750B North America**. These are current engineering
findings, not a recipe to replay old trial payloads. Detailed original records
remain in [Git history](https://github.com/aeharding/open-connect/tree/1e8efdfea264e4b31704d9e378da1f1b3be0ced6/docs/history).

## Silent Entertainment without a TAU

Mazda's Audio Manager test-menu API provides enableStatus and enable(boolean).
The Lua handler owns audio enable state; SYSTEM startup policy can subsequently
turn it off when the TAU is absent. Service availability alone is therefore not
a sufficient startup activation boundary.

The [bench helper](https://github.com/aeharding/open-connect/blob/main/src/open_connect/bench.py) uses that API. Live setup,
repeat setup, teardown and setup passed; FM Now Playing and the source list opened
without a TAU. This proves UI access, not sound output or playback. Runtime state
and ownership expire on reboot/service replacement; no persistent hook is verified.

## Disclaimer and intro handoff

Native MMUI selects Disclaimer before the GUI renders it. On the observed Intro
path, ShowDisclaimer1470 in IntroAnimation1021 selects Disclaimer1010.
The loader XML priorities are not bypass flags. Replacing the event with Timeout
or Yes is wrong: those events are unhandled in IntroAnimation.

Disclaimer Timeout1481 has nine continuation rules covering focus, display-off,
navigation, last app and audio availability. Yes omits the display-off rule.
The native prototype reuses the ordered continuation rather than forcing Home.
Rule granted/denied actions are alternatives; actions precede the old context's
exit hook. Cleanup and pending-warning behavior must be preserved.

The [native prototype](https://github.com/aeharding/open-connect/tree/main/experiments/disclaimer-native/) bypassed the observed
warm Intro route. Early intro-player disposal caused a black interval. The
[paired renderer hook](https://github.com/aeharding/open-connect/tree/main/experiments/intro-handoff/) defers DisposeIntroVideo
until renderer completion; the sampled long gap disappeared, but a dim transition
remained. Independent undo and restored-original startup passed. This does not
establish cold ACC, every resume branch or a seamless sub-frame transition.

The separate upstream-derived comparison uses a transparent NoCtrl template and
native Yes; the local Snap variant still showed a handoff. It is excluded from
AGPL distribution under its noncommercial license; see [THIRD_PARTY.md](https://github.com/aeharding/open-connect/blob/main/THIRD_PARTY.md).

## Loaded libraries and read-only remount

Replacing a still-mapped native library caused an EBUSY read-only remount failure.
Keeping same-filesystem hardlink holds through apply, undo and loaded-module
lifetime resolved the observed case. Restoring the file on disk does not unload
modified code: verify a restored-original startup and mapping before releasing
its holds. See [mapped publication](https://github.com/aeharding/open-connect/blob/main/experiments/mapped-publication/README.md).

## Spinner and frontend lifecycle

List2Ctrl and NowPlaying4Ctrl contain a circular loading indicator using
IcnStatBgFunctions_Refreshing_01.png with a two-second repeating rotation.
List2's loading overlay has a default 200 ms show delay. This is distinct from the
shimmering Mazda LoopLogo. We have not established which control causes the user's
post-shimmer spinner or whether it is limited to a particular boot mode.

Replacing the entire frontend document stopped the stock framework heartbeat
and caused Opera to exit. Preserve the document, normal transitions, callbacks
and native initialization rather than suppressing or spoofing the heartbeat.

## Optional extension loading

**One selected startup now controls service policy, logging and native/JS code
together.** A following baseline boot omitted the combination while the prepared
files remained unchanged.

| Part | Selected boot | Following baseline |
| --- | --- | --- |
| Stitcher | Did not auto-start | Process running again |
| Native logging | Inherited Warn; native filter rejected Info | Override absent; native Info messages returned |
| Native extension | Copied MMUI plugin loaded and invoked our marker module | Original plugin; marker module absent |
| GUI extension | Copied index ran our JS marker | Original index; no JS marker |

Both boots reached Communication Home. The original startup file was then restored
and its holds removed, with root read-only. The existing comparison JS stayed
installed, so this baseline is the bench configuration, not a factory-stock unit.

These are code-entry and fallback results, not a performance claim or a shipping
feature. Timing and CPU/RAM samples were retained; one pair cannot establish an
optimization. Private evidence: `runs/composed-generation/result.json`.
See the [architecture direction](extension-architecture.md) for what remains open.

<details>
<summary>Source references and earlier leads</summary>

Current source findings:

- index.html:33 loads ../../data/integration/developer_mode_GuiConfig.js before
  Utility/BaseApp/GuiFramework and framework.init(). It resolves to /data/integration,
  whose parent was mode 0777; the script was absent. Utility.js:66–94 handles script
  onload only, not onerror. This is a candidate bootstrap slot, not readiness proof.
- sm.conf:145–169 starts MMUI and Opera through separate dependency sets. Current
  /data resolves to /tmp/mnt/data on /dev/ffx01p4; data_persist is separate.
  Current availability does not establish availability at an earlier boot hook.
- svcjcimmui.so constructs UIA priority/context records before invoking loaders
  (0x2e08–0x2f50). It is not a neutral plugin registry. The
  [probe](https://github.com/aeharding/open-connect/blob/main/experiments/optional-loader/README.md) hooks its final return at
  0x31ac, before ServiceInit calls AppsLoadingFinish at 0x1914. This cannot select
  services that have already started.
- Websockets.js:507–551 constructs/sends events on an open MMUI socket.
  libjciguiifm.so:0x4d64–0x4d7c resolves the UIA name and passes the complete JSON
  object to ProcessEventJSON (0x4584). That walks UIA records and calls the event
  callback at offset 12. getGuiifmCallbackLLHead is at 0x40dc; Register at 0x40e8
  refuses an existing ID. No new callback or GUI message has been exercised.
- sm.conf:67–74 makes Wi-Fi and voice startup stages depend on blm_ira_aha;
  start_wifi:526–528 in turn depends on stage_wifi. Pandora, Stitcher and Aha
  declarations are at 414–437; TV at 519–523. A service-removal plan must resolve
  retained consumers and startup dependencies, not simply remove declarations.

Private exact sources, checksums, before/after identities and saved disassembly:
runs/runtime-boundary-research/*-result.json and guiifm-disassembly.txt.
The relevant source SHA256 values are:
sm.conf 52dac9b051ab02a07afdc7bdfac56402420f8230901b5a55a76a7e9c44fb2e08;
index.html b0e116b941f29078ced19b864a1b888cf76d8bc3e4974af081efca4693e5c420;
Utility.js eff9e63497fbd0f90d5dc9e2d9403c93fc6171cc71f70319462686a423fea791;
Websockets.js 090486339f83b40d9758faf867f3984e14e659df574fa702033a60d49406c973;
GuiConfig.js 165ef686e419dd562868ac1be206cb2a7bcd6d52ef976578c3246cbc982976e0;
libjciguiifm.so d438121db2d3fa5f75dc9b40f5eb6d54b607ac348cfd490f3ed750621572be09.
Plugin source pins and build reproduction are in the probe README.

</details>
Captures were read-only with known completion and closed ports; no OEM write or
reboot occurred. Source ordering is not proof of runtime fallback or cold startup.

## Startup selection and reset evidence

**Main learning:** a consumed trial can fall back without a working GUI or
optional runtime. Mazda's existing watchdog performs the reset; Open Connect
must choose what runs afterward.

The [one-shot selector](https://github.com/aeharding/open-connect/tree/main/experiments/boot-selection)
runs in /usr/bin/autostart before normal-mode setup, the Logger and Service
Manager (SM). It consumes and flushes a trial record before choosing a fixed
configuration. A spent record selects Mazda's original service configuration.

| Actual bench test | Observed result | Limit |
| --- | --- | --- |
| Two ordinary warm boots | Trial configuration once, OEM configuration next; running SM arguments verified | Selection proof, not a feature-health policy |
| SIGSEGV to one identity-checked MMUI process | SM stopped feeding the watchdog; automatic reset booted the baseline configuration | External process fault, not a bug in a modified library |
| Trial-only JS infinite loop | Native GUI Manager closed Opera after missing heartbeats; watchdog reset returned to the original entry page | Reconciled from the saved crash archive and fresh target checks; original serial observer stayed incomplete |
| Supply output off/on after a flushed consumed record | Record survived; fresh root access and read-only root returned | One completed write in normal runtime |
| Supply cut after early commit, before services | Spent record survived; next boot selected OEM SM configuration | Explicit three-second post-flush pause; not during rename/fsync |

These tests retained the existing comparison JS and original native library.
“Baseline” here means the pre-existing bench configuration, not an entirely stock
unit. Independent undo removed the startup hook and its hardlink holds after
each completed trial. The runtime power test ran with the hook already removed.

The runtime and early-startup power interruptions were **6.964 s** and **6.920 s**
between output requests. DPS150 voltage/current settings were unchanged; no
voltage-setting commands were sent. These test full supply loss, not ACC.

For the early test, the selector emitted a console marker after successful file
and directory flushes, then paused before returning to service startup. Output-off
was confirmed 0.390 s after that marker, within the three-second pause. The next
boot saw the record spent and started OEM SM configuration; fresh root access,
read-only root and Home returned. The original startup script was then restored.

The first early-test observer refused before cutting power: the logged Linux
banner arrives after this early console marker. Its replacement used the actual
ordered bootloader/kernel-handoff text. That failed attempt and subsequent
one-login reconciliation remain separate from the successful power-cut run.

### What causes a reset?

~~~mermaid
flowchart TD
    JS["JavaScript event-loop hang"] --> Miss["Native monitor misses JS heartbeat"]
    Miss --> Close["Opera closes"]
    Native["Critical native process exits"] --> SM["Service Manager stops watchdog feeding"]
    Close --> SM
    SM --> Reset["Watchdog resets CMU"]
    Reset --> Selector["Early selector sees spent trial"]
    Selector --> Baseline["Start baseline services and frontend"]
~~~

This is the chain observed in the controlled tests, not a claim that every JS
exception or native fault resets the unit.

A critical MMUI exit produced SM's reset_board=yes notice and watchdog-feeding
stop, followed by a new kernel boot. Opera also exited in that sequence.
This matches the compiled path through SMHEALTH_StopWatchdog (0x1bb28) and
SM_WD_Stop/stopFeeding (0x311cc). It does not disable or replace the watchdog.

JavaScript exceptions and a stuck event loop are different failure modes.
The framework catches several callback exceptions and continues. In the hang
trial, a copied entry document kept Mazda's framework but scheduled an infinite
loop. The saved log records the hang marker at uptime 48.942 s, then
OnHeartbeatMissed at 58.490 s: no JS heartbeat for ten seconds, so close Opera.
SM detected Opera's exit at 59.691 s and stopped watchdog feeding.

Serial logging was still draining messages from uptime 26 s when the reset
occurred. The observer therefore missed the hang marker and stopped as unknown.
The exact saved crash archive supplied that marker and heartbeat failure; a
separate fresh login verified baseline SM arguments, the OEM Opera entry path,
spent control and read-only root. This is a reconciled result, not an uninterrupted
automated pass. An earlier probe hit Mazda's .js-only log-stack parser before
scheduling the hang; that failed injection remains recorded.

### Implications for recovery

- **Select early.** init_cmu attempts the data_persist mount before autostart;
  still verify the actual mount. /data_persist/dev/bin/autorun is backgrounded
  inside start_normal_mode.sh and cannot reliably choose SM's configuration.
- **Consume before effects.** Missing, invalid or spent control must select
  baseline. An observed ready screen must not automatically replenish attempts:
  faults can happen later.
- **Do not guess reset causes.** Saved crash logs can help diagnose a failure, but
  missing logs do not prove battery loss. No reliable reset-cause or clean-end
  classifier has been established.
- **Bound bootstrap work.** The parent uses a five-second timeout without an
  inherited stdout pipe. Host tests cover invalid control, failed flushes and a
  surviving child. Uninterruptible filesystem I/O remains outside that guarantee.

Still open: interrupted early-boot writes, repeated power cuts, ACC/resume,
persistent retry/health policy, and service/logging/native features selected
through this same boundary. These results do not establish recovery from a
broken baseline, kernel or selector.

Private evidence: runs/early-selector/result.json,
runs/native-fault-trial/result.json, runs/js-hang-trial-v2/result.json,
runs/power-cut-trial/result.json, runs/early-power-cut/result.json and
runs/boot-selector-flush/result.json. Failed attempts and raw captures remain
unchanged. The [architecture direction](extension-architecture.md) describes the
next decision.

Source evidence is retained in runs/startup-recovery-research/result.json and
supporting-slices.txt. Exact source SHA256:

| Source | SHA256 |
| --- | --- |
| autostart | b91b2c5a5b7d036860321da730ad571dbae9164d2632946f6566238c3cd42e31 |
| start_normal_mode.sh | 6a020f2b9a92406510519820cfdee004fd4b9ef41a0ab212eb2727ffe8db80a2 |
| sm | cd1104d9b0a28dcce361520de203c1180b2e6f81d939c4223a369fd66a055f0c |
| log-save.sh | a1beb68337f7c4e334b2510f0c9ad6992acebb8a7533a4022b0fbb6678428c62 |
| init_cmu | a5c3b821236f3993b15021a80130df4e33b359beb7722a8a6a6fa9a74cf455bb |

## Native logging already supports a temporary override

**Use Mazda's own setting first.** Three disposable processes using the actual
`libjcicommon.so` reported `Info → Warn → Info`: only the middle process inherited
`COMMON_LOG_LEVEL=Warn`. Its native filter rejected Info messages and accepted
Warn; two samples two seconds apart agreed. The persistent settings file stayed
unchanged and root stayed read-only.

The compiled initializer reads settings files, then parses environment variables.
This is a simpler candidate for a selected startup than rewriting the log settings
file or isolating all services. Whole-startup inheritance, other logging stacks
and performance benefits remain untested.
Private evidence: `runs/combined-startup/log-query-result.json`.

## Configuration views without rewriting originals

**A short-lived private mount view worked on the bench.** A child process saw
`COMMON_LOG_LEVEL=Warn` through a read-only bind mount while the parent still saw
the original `Info` file. The view disappeared when the child exited, without an
explicit unmount; the physical root stayed read-only and temporary files were removed.

Mazda's `jci-log.sh` sets this default in `/config/common/log/settings.txt`.
`Logger.xml` selects sinks; it is not that default-level setting.

This proves the filesystem mechanism, not a complete startup architecture.
Isolating all services also isolates later mounts: USB, eMMC resources and
shutdown visibility must be checked before adopting it for service startup.
Mount isolation is not a sandbox for root code and does not make ordinary writes
inside the namespace temporary.

The [probe source and checks](https://github.com/aeharding/open-connect/tree/main/experiments/boot-selection)
are public; exact private evidence is `runs/combined-startup/namespace-result.json`.

### Normal persistent writes

Mazda already writes persistent settings and crash archives. Its `log-save.sh`
first builds an archive in `/tmp`, then moves it to `/data_persist/log/saved_logs`
and updates a counter. For Open Connect, keep frequent measurements in bounded
RAM-backed `/tmp/oc-*` files or stream them to the host; persist configuration
and recovery state when it changes. `/tmp/mnt/data_persist` is a persistent
mount despite its `/tmp` prefix.

The [kernel tmpfs documentation](https://docs.kernel.org/filesystems/tmpfs.html)
explains the memory-backed filesystem. Our successful flush/power tests above
do not establish a write-endurance budget or safety during interrupted writes.
