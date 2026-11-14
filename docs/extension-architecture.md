# Architecture direction

**Working proposal.** The early boot selector and automatic fallback are not
implemented. We are testing this design on **55.00.750B North America** before
committing to it.

## The idea

Select one complete Open Connect configuration **before Mazda's services start**.
On a fallback boot, skip its changes and let Mazda start normally.

~~~text
Mazda startup → small selector → baseline or selected configuration
                              → Mazda services, native code and GUI
~~~

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

- Record an attempt **before** optional effects. Start with one-shot trials.
- Missing or invalid control selects baseline.
- Repeated failures must exhaust a finite attempt budget. Startup-ready alone
  must not replenish it.
- Preserve the user's selection when falling back; a reset does not identify
  which component caused it.
- Recovery must work without optional native code, the GUI or networking.

Retry counts, reliable health signals and treatment of power loss are still open.
This cannot rescue a broken kernel, baseline or bootstrap.

## Evidence so far

Source analysis identifies an insertion point in the normal branch of
**/usr/bin/autostart**, before the Logger and Service Manager. Native/JS feature
experiments and independent undo have worked separately.

We have **not** demonstrated the combined selector and automatic fallback.
[CMU findings](reverse-engineering.md#startup-selection-and-reset-evidence)
hold the supporting evidence and limitations.

## Next proof

Build the smallest selector and test it on the bench: a no-change trial, an
interrupted trial and a fresh baseline boot. Then exercise a service setting,
logging setting and code feature through that same boundary.

The result should decide the architecture. Track the experiment in
[#25](https://github.com/aeharding/open-connect/issues/25); expand the design only
when implementation exposes a concrete need.
