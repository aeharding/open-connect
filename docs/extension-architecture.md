# Architecture direction

**Working proposal, backed by composition and fault tests on 55.00.750B NA.**
Service policy, logging and native/JS code now worked under one selection.
One-shot fallback also worked after an MMUI crash and a deliberate JS hang.
A finite attempt budget now passed a late-fault test; automatic renewal remains open.

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
ACC value is insufficient. This cannot rescue a broken kernel, baseline or bootstrap.

## Evidence so far

| Test | Result |
| --- | --- |
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

Qualify **when attempts may be renewed automatically** without allowing a late
crash loop. Trace and test actual ACC transitions when control is available.
The finite ledger is now demonstrated; production retry counts, false-fallback
behavior and interrupted writes remain open. Keep explicit developer trials
while that policy is unproved.

Then exercise a useful feature through the qualified adapters. Native/JS markers
prove entry and baseline omission; they do not yet constitute that feature.
Use Mazda's own configuration mechanisms where they fit. Track the work in
[#25](https://github.com/aeharding/open-connect/issues/25).
