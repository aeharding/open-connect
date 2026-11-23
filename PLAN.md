# Open Connect — roadmap

Updated 2026-11-23. [STEERING.md](STEERING.md) defines product intent; GitHub
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

The owner chose the five phases below. Manual bench checks and first-car
validation are deferred by the owner; continue Developer options development
now without treating those checks as prerequisites for further development.
This does not qualify or publish the v74 release. Later candidates remain backlog
with no fixed delivery slot. Each performance claim needs comparable measurements.

Developer options are implemented and bench-checked in the v74 development
candidate; see [#103](https://github.com/aeharding/open-connect/pull/103) and the
[access findings](docs/reverse-engineering.md#developer-access-and-login-script-lifetime-on-v74).
The first five-run-per-condition [startup/RAM comparison](docs/startup-comparison.md)
found later Home and wired CarPlay with the pinned development candidate, higher
CPU, and similar free RAM. Grouping repeated dependency-parent checks then
[recovered about 1.2 seconds to Home and 2.2 seconds to the dashboard](docs/startup-verification.md),
with no useful CPU/RAM gain; stock remains faster. That narrow change is integrated.
The first [Services control](docs/services.md) now selects Pandora startup policy.
[Five starts enabled and five disabled](docs/pandora-comparison.md) found about
3.2 MiB higher minimum MemFree with it off and no resolved wired-dashboard gain.
It remains optional and defaults on. A separate [native logging comparison](docs/logging-comparison.md)
found about 3.2 seconds earlier visible wired CarPlay and 8.7 MiB higher minimum
MemFree with a narrow Warn prefilter; ending free RAM differed by only 1.4 MiB.
The [installed Base preset](docs/base-comparison.md) now has a separate five-on/
five-off comparison on one dev.7 CI bundle: about 3.8 seconds earlier visible wired
CarPlay, 9.9 MiB higher minimum MemFree and 2.58 MiB higher ending free RAM. Pandora
and the initial features were fixed. The optional preset defaults off as an
implementation choice; fresh install, same-version reinstall, legacy upgrade,
controls, restart and uninstall have software bench checks. Block order and one
unit still limit attribution. Reproducible source, individual results and the
installed candidate's early resource gap are retained. Native wireless enablement
now has [installed dev.8 bench checks](docs/cmu/wireless-carplay.md#installed-development-candidate):
projection, repeated-start reconnection, controls, retained settings and uninstall
without changing vehicle/hardware identity. Physical input/audio, vehicle behavior,
long-parked timing and the Miatafy wireless milestone remain unqualified.
The [wireless baseline](docs/wireless-comparison.md) now retains five starts per
Base setting, including one Base-on watchdog restart and incomplete Ethernet
retrievals. Initial visible projection, resource denominators and comparison
limits are explicit; early usable input/audio and long-parked behavior remain
unqualified. Next expand Services and optimization research beyond Miatafy's
documented changes before deep long-parked lag work.
The owner requested this broader research; candidate selection and
defaults still require dependency, benefit and restoration evidence.
Immediate priority: recover Open Connect's own pre-Service-Manager overhead
toward the owner's bar of no measurable delay against stock. The
[verification pilot](docs/startup-overhead.md) provides a single-start improvement
and phase data, with residual work and comparison limits explicit. The dev.9
native selector now selects a verified settled snapshot, stages synchronous
checked RAM features and gives Service Manager ownership of Settings staging;
the full shell path handles mismatches and recovery. Its single working pilot
reached Home at 26.20–26.41 s and wireless projection at 52.01–52.22 s, both
about 2.22 s earlier than the preceding pilot. Compatible Uninstall independently
restored the as-found stock paths and removed the helper and product state.
The selector still recorded 0.56 s; the no-added-delay target remains open.
Preserve durable budget
barriers, original restoration and independent USB undo. Use phase timings and
matched visible milestones to guide remaining work. Wireless results alone do
not qualify stock parity. The subsequent [Services pilots](docs/service-pilots.md)
parked voice deferral and selected the four DAB/TV/Stitcher leaves for Base.
The [complete dev.10 preset](docs/services-comparison.md) has two starts per setting,
with Android Auto and Pandora held on; controls and restoration have their own
qualification evidence. Active optional services remain individual choices.

The subsequent [matched stock/dev.12 comparison](docs/stock-startup-comparison.md)
retains four stock attempts (three complete traces) and three complete active
starts, with Base/Wireless off and stock Services. Median native SM `stage_1`
started 0.085 s later, within its 0.10 s margin, but the fully spaced Home
midpoint estimate was about 0.40 s later. Its +0.196..+0.598 s frame bounds
straddle the +0.20 s margin; Home parity was not established. CPU was 0.83 percentage points
higher and minimum MemFree 3.11 MiB lower. The overlapped selector, reduced RAM
closure and delayed CPU1 Settings worker reduce overhead; they do not establish
parity. A Base-on warm restart confirmed overlap and Warn without qualifying
matched Base-on performance. Keep [#9](https://github.com/aeharding/open-connect/issues/9)
open and require an explicit owner decision on the remaining tradeoff, preserving
durable attempt-record flushes, recovery and independent restoration.

The subsequent [dev.12/dev.13 wireless-startup comparison](docs/wireless-startup-speed.md)
retains three starts per version: median visible Maps was 2.21 s earlier, Home
change was unresolved, and CPU busy increased 1.16 percentage points. Measured
own-RAM components were unchanged; total memory differences were within the
spread. The owner accepted this specific tradeoff. Keep #9 and long-parked #8
open; this does not qualify a production release.

The [dev.13/dev.14 Base startup comparison](docs/base-startup-tuning.md) now
retains three starts per version, including the slow control. Median Maps moved
47.09→44.67 s, Home 24.97→24.70 s and shared-window flash reads 86.85→52.17 MiB.
CPU's median was 0.67 percentage points lower, with overlapping ranges. Own tmpfs
grew 12 KiB; higher MemFree mostly reflects a smaller file cache. Fresh Base-off
behavior and compatible dev.13-media Uninstall restored the as-found stock state.
The owner explicitly accepted this candidate's +12 KiB allocated tmpfs, including
+4 KiB with Base off, in [PR #128](https://github.com/aeharding/open-connect/pull/128#issuecomment-7103096499).
#9 remains open. The [dev.15 Services expansion](docs/services-expansion.md) adds
configurable SiriusXM (default on), DVD (default off), Base Aha/offboard trimming
and applied Audio Sources visibility. Its three-start cohorts used 4 KiB less
own tmpfs, with nearly unchanged CPU and later median Maps (+1.407 s). The owner
accepted that candidate-specific timing tradeoff; no speedup/parity is claimed.
Independent dev.14-media removal restored stock. The test-only mid-uninstall
page reload loaded OEM System code, then an unexplained reboot limited its
qualification; retain that failure in the evidence.
Omitting unused MMUI/voice modules remains a separate follow-up: qualify their
actual loader paths and retained destinations before removing those modules.

The deferred phase-1 manual and first-car checks remain separate.

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

Current source targets exactly **74.00.324A NA / cmu150_NA**; release
qualification is in progress. A qualified download is not published yet.
The verified Mazda package and demonstrated [v74 development access](docs/reverse-engineering.md#owner-key-access-after-the-replacements-v74-upgrade)
make the port possible; they do not qualify the features or a general upgrade
procedure. The owner has confirmed the car matches **74.00.324A NA**; retain the
installer’s exact identity/source checks before writes.
Maintain one exact baseline; do not add a firmware matrix or reuse unchecked patch offsets.

1. **Establish the stock baseline.** Complete the read-only intake, identify the
   board and actual startup branch, preserve originals/metadata and touch NVRAM,
   and verify stock touchscreen and commander operation. Reproduce the motion
   restriction under a declared condition. See the [v74 porting record](docs/cmu/firmware74.md).
   Get stock wired CarPlay working with a compatible hub and phone before
   projection compatibility checks and timing batches; [#89](https://github.com/aeharding/open-connect/issues/89)
   tracks this fixture. Hardware waits gate only the checks that need them.
2. **Port the two features.** Adapt the startup integration, disclaimer bypass,
   renderer lifecycle, touch setting and Settings pages to exact v74 inputs.
   Use the exact native code placement for this image. Preserve
   normal initialization, cleanup, last-app/audio and display-off behavior.
3. **Qualify one CI-built USB bundle.** Exercise install, restart, persistence,
   Settings, update/reinstall and full uninstall. Test conflicting edits,
   interrupted transactions, maintenance from freshly prepared media and
   finite failed-start recovery. Use the existing SD bench path for maintenance;
   retain the separate USB-insertion evidence. No spare stick is required.
   Verify restored originals, NVRAM and loaded code.
   Resolve the earlier Open settings failure in the maintained flow; a backend-only
   uninstall is not a substitute for the UI check. See [#7](https://github.com/aeharding/open-connect/issues/7).
4. **Install on the owner’s matching car.** Bench qualification precedes the first
   installation. The owner will uninstall the existing wireless CarPlay mod first;
   require the exact supported OEM startup/board/service inputs and refuse any
   remaining conflicting edits. Do not add legacy-mod compatibility. Confirm the
   two features and normal controls in the real vehicle,
   document the limits, and publish the supported release and matching owner guide.

See the [installer development guide](docs/installer-development.md) for current
artifact identities, passed checks and remaining qualification limits.
Keep **Install/update** and **Uninstall** as the two maintenance actions. Preserve
verified originals until restoration succeeds; uninstall removes installed files,
backups and transaction state. See [uninstall behavior](docs/uninstall.md).

## Phase 2: keep developer access small

Use Open Connect’s OEM-style Settings entry. The controls are **UART** and
**SSH** checkboxes with **Import public key**.
Diagnostic logging is separate from interactive login. The private key stays on
the owner’s computer. Both owner-access options default off. Enabling UART gives
a password-free root shell over the physical serial connection, with a short
confirmation. Import a fixed public-key file from maintenance USB; qualify the
complete flow and firmware behavior. Preserve Mazda’s existing key authorization and normal service
behavior. Initial USB access and recovery must work when Settings is unavailable.

Proceed with this bounded follow-up now; deferred manual bench and first-car
validation do not block its development. Deliver it before the performance-baseline
and Services phases.
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

Then add a dedicated **Services** page under Open Connect Settings. The development
candidate's **Base optimizations** choice groups native Warn filtering and the four
measured DAB/TV/Stitcher leaves, and defaults off. Further contents and default
changes need their own timing and RAM evidence. Measure
the complete bundle with the same individual service selections. Inspect each
candidate’s consumers, test one reversible change at a time, and compare against
the same baseline. Aha/Pandora/Stitcher, TV and logging policy are candidates,
not a preset purge. Only expose qualified choices; show actual/pending state and
restart requirements, preserve normal OEM behavior and verify uninstall restores
the original selection/configuration. Publish negative results as well as gains;
reduced process counts or RSS alone are not proof of better responsiveness.
Consider the restoration and shared-resource requirements in the
[architecture research](docs/extension-architecture.md) when selecting service
changes; the proposed plugin framework is not a prerequisite. [#86](https://github.com/aeharding/open-connect/issues/86)
owns the menu, and [#9](https://github.com/aeharding/open-connect/issues/9) owns the measurements.

Continue this phase after the native wireless baseline: inspect the actual service
graph and startup/background CPU, RAM and I/O for additional candidates, including
work not documented by Miatafy. Research may overlap measurement collection. Add
qualified individual controls or measured Base contents, retaining negative results
and checking normal behavior and undo. Complete this broader Services pass before
deep long-parked wireless lag work; the initial Pandora control is not its endpoint.

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

**Plugin architecture — research requested.** The retrospective proposes
core-owned hooks and typed resources for layering and conflicts, with built-in
features dogfooding the same contract as independent packages. See the
[proposal and acceptance cases](docs/extension-architecture.md). Package scope,
executable/trust boundaries and implementation timing remain decisions; this
research does not add a phase or authorize a marketplace build.

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
