# Open Connect architecture

Revised proposal, 2026-11-13. Tracking: [#25](https://github.com/aeharding/open-connect/issues/25).
This replaces the disclaimer-centered runtime plan. The product scope comes from
the user; the design below is a recommendation, not a proven boot mechanism.
Only the existing native loader probe has been host-built. No selector, automatic
safe mode or optional runtime has been installed.

## Product scope

Improve the existing Mazda experience without replacing its appearance. The
scope is comparable to Miatafy/ScreenTune's non-customization features, not just
a disclaimer plugin. Feature families belong in the architecture now; implementing
all of them in the first release does not.

| Feature family | Likely integration, subject to Mazda source validation |
| --- | --- |
| Disclaimer bypass and smoother intro handoff | Native context decisions plus renderer/resource completion, or a simpler validated OEM path |
| Optional startup-animation skip | Intro process/surface lifecycle; independent of disclaimer selection |
| Aha, Pandora, Stitcher, TV/CD/DVD and other unused services | Startup graph, shared helpers and corresponding menu/source registrations |
| Optional SiriusXM, DAB, voice or navigation changes | Same mechanism, with vehicle capabilities and retained consumers explicitly checked |
| Reduced logging | Logger startup configuration or a verified nonpersistent API setting; keep minimal recovery diagnostics |
| Screen caching and other performance tuning | Process arguments/configuration or targeted code; measure benefit and memory tradeoffs |
| Message-ordering/reliability fixes | GUI/native protocol behavior, potentially before normal UI readiness |
| Menu/list looping, scroll timing and interface beeps | Existing controls/configuration or narrowly scoped GUI/audio behavior |
| Touch availability, Android Auto touch, ghost-touch disable | Actual input/projection components; contradictory selections rejected |
| Camera warning text | Camera/UI integration without altering camera availability |
| Wireless CarPlay startup/reconnect and unwanted radio fallback | Network, projection and audio lifecycle; not automatically an MMUI-only feature |
| Silent Entertainment and diagnostics for the bench | Separate development selection using OEM APIs; excluded from customer/performance baselines |

Miatafy's [feature list](https://miatafy.com/screentune/whats-possible/),
[service options](https://miatafy.com/screentune/features/mazda-services/),
[configuration](https://miatafy.com/screentune/configure/) and
[message-ordering description](https://miatafy.com/screentune/bugfixes/) establish
the comparison scope, not correctness or measured benefit on our firmware.
OEM appearance permits removing dead entries for disabled services; it does not
mean themes, replacement dashboards, gauges or a new launcher. Those are outside
the current baseline. Similar scope does not authorize copying proprietary or
incompatibly licensed implementations.

## Central decision: select a complete boot configuration

A feature is a user-visible behavior, not necessarily a library. One immutable
configuration contains the chosen features, their settings, firmware identity
and all resolved artifacts. Call this a generation. Select it once per boot,
before any affected OEM consumer runs. All participating processes use that same
selection; changing desired state while running affects a later boot.

The architecture needs three responsibilities:

1. **Build/install tooling:** compose selected changes from verified originals,
   validate dependencies/conflicts, stage one complete generation, preserve
   originals and independent recovery. Existing Python tooling owns this work.
2. **Small trusted startup selector:** choose baseline or one generation, record
   the attempt before effects, and arrange the required early file/configuration
   views. It must run before the earliest component we intend to change.
3. **Firmware adapters and feature code:** apply the selected behavior at the
   actual service, native or GUI lifecycle point. Only components that need
   ongoing behavior remain resident.

This is not a new init system or replacement service manager. Mazda still owns
startup and service supervision. The selector is not an MMUI plugin: MMUI starts
too late to select its own startup prerequisites. The current loader experiment
is one possible adapter, not the foundation of whole-system safe mode.

Do not build a plugin marketplace, arbitrary boot-script runner, generic
dependency solver or new message bus. A small explicit set of supported features
can be composed deterministically with straightforward validation.

## Making configuration changes disappear in safe mode

Prefer changes whose effects are reconstructed for each boot, with original OEM
files retained underneath. In priority order:

- Pass a generated configuration through an existing supported launch argument.
- Where a consumer requires a fixed path, investigate a temporary file view
  established before its first read, such as a narrowly scoped bind mount.
- Use guarded in-memory/native/JS hooks when the behavior requires code.
- Use an OEM API only after establishing whether it persists state and which
  later OEM policy can overwrite it.

A generated file may be configuration, patched JS or an exact-base patched native
library. Small code edits do not automatically need a dynamic plugin loader.
Owned native/JS modules remain useful for substantial independent feature logic.

**These mechanisms are candidates, not established CMU capabilities.** In
particular, an early selector, the required mount behavior/visibility, storage
availability and cold-start ordering remain unproved. No OverlayFS, alternate
boot slot, modern init facility or global preload is assumed.

The off path must omit all optional file views, startup actions and code loading.
A broken optional generation should therefore not require rewriting a damaged
sm.conf before the next normal start. Minimal integration patches still execute;
baseline means no Open Connect feature effects, not byte-identical factory state.

Persistent OEM edits or database mutations cannot be smuggled into this contract:
skipping a script does not reverse its previous write. A feature must either be
made boot-scoped or have a proven restoration path before its earliest consumer.
Until then it does not qualify for the unified safe-mode guarantee. Firmware
updates remain separate maintenance, not a reversible feature selection.

Selection of a generation can be atomic; execution of many effects is not.
Prepare and validate before launching consumers. A partial activation must be
unwound and verified before claiming baseline. If it cannot be unwound, report
incomplete activation and use independent recovery; never call a mixed state
stock. Do not delay essential OEM services indefinitely while waiting for ours.

## Feature composition and dependencies

Build each resulting file once from a verified baseline and the complete selected
feature set, rather than stacking patches over the last installation. Record
exact inputs and outputs. Conflicting transformations must be explicitly combined
and tested or refused. Git-style patches are source recipes, not fuzzy on-device
merge instructions. OEM-derived outputs stay private.

Each feature needs only a small concrete contract: supported firmware/hardware,
touched files or APIs, activation point, dependencies/conflicts, persistent effects,
verification and disable behavior. Features sharing a file do not each own a
separate backup/restore cycle.

Service disabling is one coordinated feature change: service graph, remaining
consumers, shared helpers, and visible source/menu state. Saved FW55 sm.conf
lines 67–74 make stage_wifi and stage_vr depend on blm_ira_aha; start_wifi then
depends on stage_wifi (526–528). Removing Aha alone is not a complete plan.
This establishes a dependency to resolve, not proof of a particular runtime
failure. Keep shared helpers when a remaining consumer needs them. Unknown
hardware capability is not permission to disable its service.

A paired native/renderer feature requires matching readiness before its own
decision point; that is not a universal prerequisite for unrelated configuration
features. Existing Mazda messages may carry readiness, but the global boot
decision and recovery must not depend on the GUI or on a message-ordering feature
whose activation they are trying to authorize.

## Disable, trial and failure semantics

Keep four concepts distinct:

| Operation | Meaning |
| --- | --- |
| Disable one feature | Build/select a new complete configuration without it; verify after restart |
| Disable Open Connect / safe mode | Select baseline for the next boot across services, files and code |
| Undo an update | Explicitly select a retained compatible generation |
| Uninstall | Restore pre-install integration files and remove owned deployment state using the existing conflict/undo contract |

Retain baseline, the active confirmed generation and at most one candidate/
previous generation as needed for the current transaction. Keep loaded artifacts
until their processes exit; disk restoration does not unload code. No hot-unload
or live multi-process configuration switch is promised.

**First experiment: one attempt.** Staging a candidate does not select it.
An explicit trial is consumed and recorded before the first optional effect.
An interrupted/unconfirmed trial selects baseline on the next boot. Readiness
reports are evidence, not permission to retry or promote themselves. Confirmation
must bind the exact generation and attempt. A process respawn must not consume
another trial or silently pick a different generation; preserve the boot decision
outside managed processes. Their restart behavior needs its own qualification.

**Proposed persistent mode:** before each enabled startup, record an incomplete
attempt. Mark it healthy only after a defined system/feature startup check.
A previous incomplete or explicitly failed attempt selects baseline and remains
disabled until deliberately changed. Explicit off always wins. A late success
from an old boot/attempt cannot override off or a newer configuration.

This detects failure before that health checkpoint, not every later defect.
A crash after success may be invisible unless an independent observer records it;
a power cut before success may produce a false fallback. No reliable classifier
has been established for this CMU. An always-running crash supervisor is not
assumed necessary or sufficient. Define this product tradeoff and qualify
warm/cold/ACC behavior before persistent mode ships; do not advertise universal
automatic recovery.

Health must include retained service readiness, GUI/native consistency and the
enabled features' relevant behavior. A PID, delay, home screenshot or module's
own success flag is insufficient alone. Diagnostics must survive the logging
reduction feature. Failure falls back to the entire baseline initially; automatic
per-feature blame/bisection is deferred.

The trusted selector and its state storage are the recovery boundary. Missing or
invalid optional inputs choose baseline. Record consumption before effects;
verify persistence with the actual filesystem and interruption experiments.
Rename/sync success is not proof against power loss. If the selector, kernel,
baseline or its storage fails, optional-feature safe mode cannot rescue it.

Independent recovery must not require MMUI, networking or any service users can
disable. UART is demonstrated bench access; an early USB/key safe-mode request
is a desired future mechanism, not something already available. First deployment
must have independent original-file undo. No firmware downgrade/brick-proof claim.

## Precedents and what we borrow

- [Magisk](https://topjohnwu.github.io/Magisk/guides.html): disabled modules omit
  their file mounts and startup scripts, with different startup stages for
  different work. This is closer to the full feature scope than a UI plugin
  loader. Android's implementation and facilities cannot be assumed on Mazda.
- [NixOS generations](https://nixos.org/manual/nixos/stable/#sec-rollback):
  complete retained configurations make rollback understandable. Borrow that
  model, not Nix, a new package manager or a whole-OS rebuild.
- [RAUC boot confirmation](https://rauc.readthedocs.io/en/latest/using.html#marking-a-boot-as-successful-or-failed):
  a successful installation is distinct from a successful boot; health is
  system-specific. We are not proposing RAUC or repartitioning the CMU.
- [Miatafy's installer description](https://miatafy.com/screentune/how-it-works/):
  it resolves a full configuration and preserves first-install backups. It does
  not establish the next-boot, no-restoration safe-mode contract proposed here.
- [NickelHook](https://github.com/pgaskin/NickelHook/blob/bcd90ba94d90d22562fb64ef2920ed3323c1dae5/nh.c)
  and [BepInEx](https://github.com/BepInEx/BepInEx/blob/master/BepInEx.Core/Bootstrap/BaseChainloader.cs):
  useful loader/feature separation, but not sufficient for early service policy.

## Loader-probe findings

The existing [native probe](../experiments/optional-loader/README.md) adds a
104-byte optional load at the end of mmuiLoadUias in svcjcimmui.so. Host checks
passed; no runtime installation occurred. Missing library/symbol returns to the
OEM path, but constructors execute before dlopen returns and crashes/hangs are
not caught. It does not provide whole-startup selection or attempt persistence.

The saved GUI index has an optional /data/integration/developer_mode_GuiConfig.js
slot before framework initialization. Its parent is mode 0777. It is a candidate
adapter with an installation/ownership boundary, not a proven safe feature loader.
The existing developer script was absent at observation.

## Native/renderer readiness boundary

The saved GUI WebSocket event path delivers the complete JSON object to a native
per-UIA callback. A strict System callback adapter is a candidate for paired
readiness without another daemon. Callback timing/concurrency, pointer lifetime,
renderer readiness and attempt delivery remain unproved. No callback replacement
or new GUI event was exercised. See [Mazda findings](reverse-engineering.md#optional-extension-loading)
for exact source/provenance; do not make this transport the early selector.

## Next proof and implementation order

1. Trace the actual launch boundary before the service manager reads its graph
   and before other intended consumers. Establish where control/artifacts are
   available then. A service listed inside sm.conf is not automatically early
   enough to choose that file.
2. Prove a no-change generation and baseline selection at that boundary, including
   missing/corrupt state, partial setup, consumed trials and a fresh baseline boot.
   Test any required file-view primitive separately before using OEM paths.
3. Exercise three representative feature shapes: one service configuration
   change, one logging/configuration setting, and the existing paired bypass.
   They can be separate trials; they must share selection/recovery semantics.
4. Verify global off restores original service startup, configuration reads and
   optional-code absence without rewriting managed OEM files. Verify retained
   user settings, disabled-feature menus and independent uninstall.
5. Only then port more features, define production health confirmation and move
   the single required firmware baseline. Measure overhead as well as benefit.

If no practical pre-consumer selector/view is available, stop claiming this
architecture is established. Reconsider the integration patch or explicitly
choose a restore-based installer with weaker fallback; do not silently substitute
one. Do not redesign init or adopt a full overlay framework without evidence.

Repository direction stays tooling/ for host builders/CLI/tests and
cmu/{bootstrap,adapters,features} for target control and feature artifacts/recipes.
Firmware-specific offsets, service names and lifecycle contracts belong in
adapters. Create only components needed by these proofs. No layout migration,
new runtime code or hardware change is part of this architecture revision.
