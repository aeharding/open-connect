# Open Connect — roadmap

Updated 2026-11-20. [STEERING.md](STEERING.md) defines product intent; GitHub
issues track implementation. This roadmap sets delivery order and completion
criteria, without calendar promises. One primary owns each complete release.

## Product direction

**Make Mazda Connect feel factory-original, work more reliably, and be easy to
maintain—with optional improvements people can install and undo.**

Keep Mazda’s interface and normal controls. The first production release combines
always-enabled touchscreen input and the startup disclaimer bypass on one exact
firmware. A small developer menu follows that release. Then establish performance
baselines and ship qualified controls in a dedicated Services menu. Cold-start native
wireless CarPlay reliability is last in the agreed sequence. Establish stock
wired CarPlay early as a qualification and measurement fixture.

## Delivery order

The owner chose the five phases below. Later candidates remain backlog with no
fixed delivery slot. Each performance claim needs comparable measurements.

| Phase | Outcome | Done when | Work |
| --- | --- | --- | --- |
| **1. First v74 release** | Install the two initial features on the owner’s car using a normal USB bundle | Both features, startup recovery and the complete maintenance flow pass on the matching bench; the first car installation confirms the intended behavior | [#2 firmware](https://github.com/aeharding/open-connect/issues/2), [#60 touch](https://github.com/aeharding/open-connect/issues/60), [#6 bypass](https://github.com/aeharding/open-connect/issues/6), [#7 delivery](https://github.com/aeharding/open-connect/issues/7) |
| **2. Developer options** | Control development access from Open Connect Settings | UART console-login checkbox and SSH enable/disable with public-key import work, show actual state and restart requirements, and restore pre-install configuration on uninstall | [#85](https://github.com/aeharding/open-connect/issues/85) |
| **3. Performance baselines** | Know where startup time and resource pressure go before changing services | Repeatable stock/Open Connect timing, CPU, RAM and I/O batches; compare relevant Miatafy milestones and explain matches or differences | [#5 starts](https://github.com/aeharding/open-connect/issues/5), [#9 measurements](https://github.com/aeharding/open-connect/issues/9) |
| **4. Services menu and base optimizations** | Let owners disable qualified unused services in a dedicated Settings page | Dependencies and effects are documented, each change is compared against baseline, and controls, restart, regressions and undo are qualified | [#86 Services](https://github.com/aeharding/open-connect/issues/86), [#9 measurements](https://github.com/aeharding/open-connect/issues/9) |
| **5. Native wireless CarPlay — last** | Enable native wireless CarPlay through Open Connect while preserving vehicle identity, then improve long-parked startup | The enable option works without vehicle-fingerprint spoofing; comparable runs identify and improve cold-start lag, with real-car confirmation | [#8 reliability](https://github.com/aeharding/open-connect/issues/8) |

These phases describe release outcomes. Existing GitHub milestones retain their
historical names; they do not override this delivery order. Bench tooling supports
specific release blockers rather than becoming a separate product milestone.

## Phase 1: finish the v74 release

The published development installer still supports exactly **55.00.750B North
America / cmu150_NA**. Current source targets **74.00.324A NA / cmu150_NA**; qualification is in progress.
The verified Mazda package and demonstrated [v74 development access](docs/reverse-engineering.md#owner-key-access-after-the-replacements-v74-upgrade)
make the port possible; they do not qualify the features or a general upgrade
procedure. The owner has confirmed the car matches **74.00.324A NA**; retain the
installer’s exact identity/source checks before writes.
Move support to v74 together once qualified; do not build a v55/v74 support matrix
or reuse old patch offsets.

1. **Establish the stock baseline.** Complete the read-only intake, identify the
   board and actual startup branch, preserve originals/metadata and touch NVRAM,
   and verify stock touchscreen and commander operation. Reproduce the motion
   restriction under a declared condition. See the [v74 porting record](docs/cmu/firmware74.md).
   Get stock wired CarPlay working with a compatible hub and phone before
   projection compatibility checks and timing batches; [#89](https://github.com/aeharding/open-connect/issues/89)
   tracks this fixture. Hardware waits gate only the checks that need them.
2. **Port the two features.** Adapt the startup integration, disclaimer bypass,
   renderer lifecycle, touch setting and Settings pages to exact v74 inputs.
   Resolve native code placement rather than replaying the v55 layout. Preserve
   normal initialization, cleanup, last-app/audio and display-off behavior.
3. **Qualify one CI-built USB bundle.** Exercise install, restart, persistence,
   Settings, update/reinstall and full uninstall. Test conflicting edits,
   interrupted transactions, compatible replacement-USB maintenance and finite
   failed-start recovery. Verify restored originals, NVRAM and loaded code.
   Resolve the earlier Open settings failure in the maintained flow; a backend-only
   uninstall is not a substitute for the UI check. See [#7](https://github.com/aeharding/open-connect/issues/7).
4. **Install on the owner’s matching car.** Bench qualification precedes the first
   installation. The owner will uninstall the existing wireless CarPlay mod first;
   require the exact supported OEM startup/board/service inputs and refuse any
   remaining conflicting edits. Do not add legacy-mod compatibility. Confirm the
   two features and normal controls in the real vehicle,
   document the limits, and publish the supported release and matching owner guide.

The v55 prerelease supplies working installer mechanisms and prior evidence,
not a fresh v74 qualification. See the [installer development guide](docs/installer-development.md).
Keep **Install/update** and **Uninstall** as the two maintenance actions. Preserve
verified originals until restoration succeeds; uninstall removes installed files,
backups and transaction state. See [uninstall behavior](docs/uninstall.md).

## Phase 2: keep developer access small

Use Open Connect’s OEM-style Settings entry. The agreed controls are a **UART
console-login checkbox** and **SSH enable/disable with Import public key**.
Diagnostic logging is separate from interactive login. The private key stays on
the owner’s computer. Importing a public-key file from USB is a proposal; defaults,
the exact import interaction and the stock console-login control still need
qualification. Preserve Mazda’s existing key authorization and normal service
behavior. Initial USB access and recovery must work when Settings is unavailable.

Ship this bounded follow-up before the performance-baseline and Services phases.
Keep ordinary installation and USB recovery independent of developer access.
[#85](https://github.com/aeharding/open-connect/issues/85) owns the details.

## Phases 3–4: baseline first, then Services

Define comparable stock-service and released-Open-Connect configurations before
changes. Record firmware, board, peripherals, enabled features and instrumentation.
Measure startup milestones, a concrete input-to-response operation and CPU, named
memory metrics and I/O over the same workload and startup phase. Separate full
shutdown, supply loss, warm reboot and quick ACC resume; retain failures and the
spread across repeated trials. Check collection overhead. Home appearing and an
input device registering do not by themselves establish usable controls.

Publish methods, individual timings, RAM values, conditions and failures in the
[Performance evidence section](docs/performance.md). Include the Miatafy
comparison there: match milestone definitions and timing origins before claiming
reproduction, and distinguish external reference numbers from our results.
Include usable wired projection in these baselines once the early fixture is
qualified. Miatafy's wireless CarPlay milestone reproduction stays in phase 5;
do not compare a wired result directly with its wireless timing.

Then add a dedicated **Services** page under Open Connect Settings. A proposed
**Base optimizations** on/off setting groups qualified internal changes such as
reduced logging; its contents and default need timing and RAM evidence. Measure
the complete bundle with the same individual service selections. Inspect each
candidate’s consumers, test one reversible change at a time, and compare against
the same baseline. Aha/Pandora/Stitcher, TV and logging policy are candidates,
not a preset purge. Only expose qualified choices; show actual/pending state and
restart requirements, preserve normal OEM behavior and verify uninstall restores
the original selection/configuration. Publish negative results as well as gains;
reduced process counts or RSS alone are not proof of better responsiveness.
Use the [boot configuration architecture](docs/extension-architecture.md) for
service changes. [#86](https://github.com/aeharding/open-connect/issues/86)
owns the menu, and [#9](https://github.com/aeharding/open-connect/issues/9) owns the measurements.

## Phase 5: improve native wireless CarPlay

The owner will remove the existing wireless mod before installing Open Connect.
Implement an Open Connect option to enable Mazda's native wireless CarPlay while
preserving actual vehicle/hardware identity. The rejected fingerprint-spoofing
approach is reference research, not an installer compatibility target. Trace the
narrow firmware capability and startup controls before choosing the mechanism.
The reported long-parked lag still needs a reproducible diagnosis; rejecting the
spoofing approach does not establish its cause. Prefer native wireless CarPlay for
everyday use; wired CarPlay is a useful comparison and fallback.

Measure time to usable projection, early input/audio responsiveness, connection
success and settling, with comparable CPU, RAM and I/O observations. Separate
software reboot, full supply loss, ACC/resume and a real long-parked car start.
Keep failures and timing spread; a faster Home screen or lower idle RSS is not
proof of better CarPlay. Use the [measurement plan](docs/carplay-testing.md) and
[v74 source findings](docs/cmu/wireless-carplay.md). Ship a change only when its
claimed benefit and regressions have been measured.

## Backlog without a fixed slot

**Ghost-touch control — requested.** Extend the normal touchscreen preference to
**Factory behavior / Always enabled / Disabled (ghost touch)**. The disabled mode
needs startup and projection coverage, commander-only navigation, restart
persistence, independent recovery and exact pre-install restoration. Qualify the
earliest effective firmware control; suppression after Home is not total disable.
This is a follow-up after the first release with no fixed slot yet. See
[#87](https://github.com/aeharding/open-connect/issues/87).

**Connected maintenance — proposed.** Explore an explicit switch from wireless
CarPlay to a phone/home hotspot and a reliable return. Concurrent modes are not
required; checks must not silently take over the connection or trigger a restart.
Keep USB as the offline maintenance route. Qualify actual network exposure and
package verification under [#58](https://github.com/aeharding/open-connect/issues/58)
before shipping online updates; [#54](https://github.com/aeharding/open-connect/issues/54)
contains the proposal. This backlog does not delay the agreed five phases.

Useful OEM menu/input conveniences remain candidates. No themes, launcher or
replacement dashboard. Factory-reset behavior remains separate work in
[#56](https://github.com/aeharding/open-connect/issues/56);
do not promise that Mazda’s reset uninstalls Open Connect. Broad firmware/region
support, arbitrary old-package compatibility, general TAU emulation, a web
configurator and universal crash recovery remain deferred.

## Delivery discipline

Keep one authoritative transaction record and one small UI/backend command
contract. Build static installer logic and native assets with Make/shell and
standard compiler/linker tools. Use the existing bench workflow for concrete
qualification work. Every feature needs applicable firmware, evidence and undo;
every merged PR needs independent review and passing checks. Publish original
AGPL-compatible work and sanitized findings; see [THIRD_PARTY.md](THIRD_PARTY.md).

Changing device state and the next concrete bench task stay in
[docs/bench-state.txt](docs/bench-state.txt). Detailed implementation questions
belong in GitHub issues. Update the roadmap after meaningful results or owner
priority changes, without accumulating another progress dashboard.
