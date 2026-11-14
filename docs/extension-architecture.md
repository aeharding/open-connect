# Architecture direction

**Working proposal, backed by composition and fault tests on 55.00.750B NA.**
Service policy, logging and native/JS code worked under one selection.
A real native/JS feature now ran from selected files, then was omitted on the
next boot without restoring installed feature files. Fault tests support finite
fallback; partial-startup health detection and automatic renewal remain open.

## The idea

Select one complete Open Connect configuration **before Mazda's services start**.
On a fallback boot, skip its changes and let Mazda start normally.

~~~mermaid
flowchart TD
    Boot["Mazda startup"] --> Select{"Valid trial / attempts available?"}
    Select -->|No| Baseline["Start baseline configuration"]
    Select -->|Yes| Consume["Reserve attempt + verify flush"]
    Consume -->|Failure or timeout| Baseline
    Consume -->|Success| Trial["Start selected configuration"]
    Trial -->|Fault causes reset| Boot
~~~

An attempt is spent before optional code starts. A new configuration gets one
startup until explicitly confirmed. Confirmation does not refund that attempt.
Once the finite budget is exhausted, the next boot selects baseline—even when
the previous startup reached Home before failing.

“Baseline” means Open Connect features are off. The small installed integration
point remains; this is different from uninstalling it.

## Three responsibilities

| Part | Job |
| --- | --- |
| Host tools | Build the selected features together from verified originals; install and recover them |
| Early selector | Choose baseline or one configuration before affected services start |
| Firmware adapters | Connect each feature to the Mazda component that owns its behavior |

Use generated startup settings or temporary file views where possible. Add
native or JS code where the behavior needs it. A runtime loader alone starts too
late to control earlier services.

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
Automatic renewal still needs a proven event, such as a real ACC cycle. A cached
ACC value is insufficient. A partial startup can leave processes alive without a
working UI: fallback chooses the next boot, but does not itself cause that boot.
This cannot rescue a broken kernel, baseline or bootstrap.

## Evidence so far

| Test | Result |
| --- | --- |
| Paired disclaimer feature | Selected native bypass and JS cleanup ran together; next boot omitted both without feature-file restoration |
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

- **Health:** detect incomplete initialization outside the optional component.
  A failed library load left MMUI alive; process existence alone was insufficient.
- **Renewal:** test actual ACC OFF → ON before allowing automatic retries.
  This physical test is deferred until controlled ACC is available.
- **Durability:** qualify interrupted record updates, beyond completed-flush cuts.

Continue useful feature development with explicit trials while those production
policies remain open. No general plugin framework is needed.
Track the work in [#25](https://github.com/aeharding/open-connect/issues/25).
