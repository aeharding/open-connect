# Architecture direction

**Architecture research on 55.00.750B NA.** The maintained
[USB installer](usb-installer.md) now implements persistent startup with a finite
attempt budget and ACC-based renewal. Its [qualification evidence](reverse-engineering.md#standalone-installer-backend)
supersedes the trial-only renewal limits below.

Service policy, logging and native/JS code worked under one selection.
A real native/JS feature now ran from selected files, then was omitted on the
next boot without restoring installed feature files. Fault tests support finite
fallback. A Home-only independent deadline now recovered one stuck-logo startup;
other startup paths remain outside that Home-specific experiment.

## Earlier trial mechanism

Select one complete Open Connect configuration **before Mazda's services start**.
On a fallback boot, skip its changes and let Mazda start normally.

~~~mermaid
flowchart TD
    Boot["Mazda startup"] --> Select{"Valid trial / attempts available?"}
    Select -->|No| Baseline["Start baseline configuration"]
    Select -->|Yes| Consume["Reserve attempt + verify flush"]
    Consume -->|Failure or timeout| Baseline
    Consume -->|Success| Trial["Start selected configuration"]
    Trial --> Watch{"Home acknowledgement?"}
    Watch -->|Received| Ready["Finish startup observation; keep attempt spent"]
    Watch -->|Deadline expires| Restart["Request normal reboot"]
    Restart --> Boot
    Trial -->|Mazda watchdog reset| Boot
~~~

An attempt is spent before optional code starts. A new configuration gets one
startup until explicitly confirmed. Confirmation does not refund that attempt.
Once the finite budget is exhausted, the next boot selects baseline—even when
the previous startup reached Home before failing.

“Baseline” means Open Connect features are off. The small installed integration
point remains; this is different from uninstalling it.

## Release responsibilities

| Part | Job |
| --- | --- |
| Build tools | Compile original native code with standard tools and package static installer files plus data manifests into one USB bundle |
| CMU installer | Verify the unit's own originals, compose feature files, and own install/uninstall/recovery through one durable transaction record |
| Early selector | Choose baseline or one configuration before affected services start |
| Firmware adapters | Connect each feature to the Mazda component that owns its behavior |
| Bench tools | Instrument and verify the device; installation must not depend on them |

The product path is a small static USB loader, static installer UI and a CMU-local
backend. Use one explicit UI/backend command contract. Experimental image-request,
receiver and D-Bus callback chains are evidence, not the default product design.
Keep runtime tokens, paths and ports as data; avoid generated application scripts.
The build uses Make/shell and standard compiler/linker tools, not a Python packager
or custom ELF linker. Full OEM files stay on the head unit or in private research.

Compose startup configuration from verified on-device originals where needed.
Add native or JS code where the behavior needs it. A runtime loader alone starts
too late to control earlier services.

## Product scope

Startup/disclaimer behavior, unused services, logging and performance, OEM
controls, and phone/audio reliability. Preserve Mazda's appearance. Bench-only
helpers remain a separate development profile.

Compose shared-file changes together rather than stacking patches over previous
installations. Service changes must account for their remaining consumers.

## Recovery direction

- Record an attempt **before** optional effects. New configurations start as trials.
- Missing or invalid control selects baseline.
- Repeated failures must exhaust a finite attempt budget. Startup-ready alone
  must not replenish it.
- Preserve the user's selection when falling back; a reset does not identify
  which component caused it.
- Recovery must work without optional native code, the GUI or networking.

The [reset comparison](reverse-engineering.md#a-reset-label-is-not-a-cause-classifier)
found the same “Power-up” word after normal reboot and watchdog reset. That label,
a ready screen or a shutdown request must not grant fresh attempts.

The prototype charges every selected boot. Its **two-attempt limit is a test
parameter, not the product policy**. An explicit maintenance operation can renew
a confirmed generation's budget; its stale-command checks have host coverage.
Keep the current budget on a same-boot ACC resume. On v55 a brief interruption
produced both ignition events and returned to Home within the same boot. The Home-specific supervisor can request a reboot
when processes stay alive without a usable Home screen. Other intended screens
and display-off behavior need their own evidence before enabling that policy.
This cannot rescue a broken kernel, baseline or bootstrap.

## Evidence so far

| Test | Result |
| --- | --- |
| Developer CLI cycle | Build/prepare/trial/status/disable completed; selected state reconciled after a console-check failure, baseline return automatic |
| Paired disclaimer feature | Selected native bypass and JS cleanup ran together; next boot omitted both without feature-file restoration |
| Home acknowledgement | Real browser delivered a generation/current-boot signal to an independent receiver; camera confirmed Home |
| Missing native module, responsive GUI loop | Independent deadline requested a normal reboot; spent trial selected baseline and Home returned |
| Combined service/logging/native/JS trial | All four effects selected; following baseline omitted all four |
| Two ordinary warm boots | Trial selected once; baseline selected next |
| Native MMUI process crash | Mazda watchdog reset; baseline selected next |
| Late crash after two selected, ready startups | Confirmation kept the first charge; exhausted budget selected baseline and omitted all four effects |
| Trial-only JS event-loop hang | Mazda closed Opera after missed heartbeats, then reset; original entry page returned |
| Full power cut after a flushed record | Consumed record survived |
| Cut after early commit, before services | Spent record survived; next boot chose baseline |

The JS result needed Mazda's saved crash log plus fresh postboot checks: serial
logging lagged behind the reset. The original observer's incomplete result remains
unchanged. Power cuts covered a completed runtime write and an explicit pause
after the early record flush, before services. Neither cut interrupted rename/fsync.
Each fault/power case has one actual observation; voltage settings were unchanged.

All trial hooks were removed. Existing bench modifications remained.
[CMU findings](reverse-engineering.md#startup-selection-and-reset-evidence)
explain the evidence and limits.

## Next proof

- **Repeatability:** use the [developer CLI](cli.md#developer-feature-trial) for
  further measured trials. Repeated healthy starts and last-app/display-off
  qualification are needed before treating Home as a broader health policy.
  [Actual signal and limits](reverse-engineering.md#a-home-specific-acknowledgement).
- **Renewal:** the installer now uses sustained ACC off followed by a different
  kernel boot with ACC on. Full shutdown, quick resume, software reset and a late
  watchdog fault were checked. Broader vehicle conditions remain unqualified.
- **Durability:** qualify interrupted record updates, beyond completed-flush cuts.

The standalone USB installer development prerelease includes persistent startup
for the installed features. Its transaction and lifecycle checks are described
in the USB guide. The bench's limited trial policy remains instrumentation.
No general plugin framework is needed.
Track the work in [#25](https://github.com/aeharding/open-connect/issues/25).
