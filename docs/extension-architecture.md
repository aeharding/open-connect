# Open Connect extension architecture

Research and proposed implementation plan, 2026-11-13.
Tracking: [#25](https://github.com/aeharding/open-connect/issues/25).
The native loading probe is host-built; no runtime disable mechanism is implemented
or installed yet. See [the probe findings](#loader-probe-findings).
Scope: one feature on 55.00.750B NA, then extract shared pieces when needed.

## Goal and boundary

Keep Mazda's software running, with small integration points that can load our
separate feature code. Disabling Open Connect should require changing only our
owned control state and restarting, without restoring OEM files or remounting root.

**Disabled means optional code is not loaded on the next verified startup.**
The installed bootstrap still executes its small stock-path decision. It is
not literally an untouched system. A broken bootstrap, linker path or OEM patch
can fail before that decision; independent original-file restoration remains
necessary. Disable complements [Uninstall](uninstall.md), not replaces it.

There is no promise of safe hot-unload. Deleting a file or changing configuration
does not remove loaded native code, callbacks or JavaScript side effects.
Report requested state separately from observed state; a disable request is not
complete until a fresh startup proves the optional code was skipped.

## Repository layout

Use execution boundaries as the top-level distinction:

~~~text
tooling/                 Host Python package, oc CLI, builders and tests
cmu/                    Code that executes on the Mazda unit
  bootstrap/            Small load/skip decision and stock delegation
  adapters/             Exact-firmware APIs, hooks and compatibility checks
  features/
    disclaimer/         The paired native and renderer feature
docs/                   Setup, architecture and findings
experiments/            Unfinished prototypes and trial machinery
~~~

The existing Python package moves together to tooling/src/open_connect, with
its tests and packaging configuration under tooling. The installed command stays
oc; open_connect remains the Python import name. The bootstrap is the minimal
always-present boundary; a feature is optional behavior; an adapter contains
Mazda-specific knowledge. Runtime is a description, not another catch-all folder.

This is the agreed layout direction, not an instruction to create empty folders.
Move the host package in one reviewed PR, updating installation, CI and links.
Introduce cmu components with the first loader experiment. Keep a feature's native
and JS pieces together even though they execute in different processes. Do not
create one framework for each language.

Other projects separate concrete components similarly: [Magisk](https://github.com/topjohnwu/Magisk)
uses app/native/tools, [Magic Lantern](https://github.com/reticulatedpines/magiclantern_simplified)
uses src/platform/modules, and [BepInEx](https://github.com/BepInEx/BepInEx) separates
preloader/core/runtimes. These are precedents, not structures to copy wholesale.

## What the precedents actually establish

| Project | Observed mechanism | Lesson and limit |
| --- | --- | --- |
| [NickelHook source](https://github.com/pgaskin/NickelHook/blob/bcd90ba94d90d22562fb64ef2920ed3323c1dae5/nh.c#L366) | During initialization it renames its loaded library to a failsafe name, retains the mapping, and later restores the name. Initialization errors attempt hook restoration. | Keep a failed extension out of the next startup. Its rename/timer mechanism is not proof of health or of RelFS durability. |
| [NickelHook loading](https://github.com/pgaskin/NickelHook/blob/bcd90ba94d90d22562fb64ef2920ed3323c1dae5/nhplugin.h) | Uses a Qt image-plugin entry point. | An existing loader can reduce OEM changes; this particular entry point does not transfer to Mazda by assumption. |
| [Magic Lantern modules](https://github.com/reticulatedpines/magiclantern_simplified/blob/142472e95054d73640f50789ac0fd66325499d82/src/module.c#L2054) | Writes a load marker, skips loading if it remains, and removes it during clean shutdown. | A previous incomplete session can suppress the next attempt. Normal power cuts can look like failures; Mazda shutdown behavior must be established before adopting this policy. |
| [Magisk lifecycle](https://topjohnwu.github.io/Magisk/details.html#magisk-booting-process) and [module flags](https://topjohnwu.github.io/Magisk/guides.html#magisk-modules) | Separates boot stages, module disable/removal and boot-completion tracking. | Separate desired state from successful activation. Android init/property/mount facilities are not established CMU capabilities. |

Linux loads shared-library constructors before dlopen returns. Therefore a flag
checked inside optional library initialization cannot protect against every
loader/constructor failure. The external decision must precede loading. This also
explains why catching an init error cannot catch arbitrary native crashes or hangs.
See [dlopen](https://man7.org/linux/man-pages/man3/dlopen.3.html).

## Mazda evidence and unresolved integration

These are observations from exact saved files, not new device tests:

- GuiFramework.js _addAppFiles, lines 1860–1908, calls utility.loadScript.
  _initApp, lines 1274–1286, constructs the app and calls appInit synchronously.
  systemApp.js builds its context table in appInit. This identifies real lifecycle
  boundaries, not a proven optional-script loader or missing-file fallback.
- The saved svcjcimmui.so mmui_ProcessEntry calls dlopen at 0x1ee4/0x20d8 and
  dlsym at 0x2298/0x25a4. mmui_config.xml identifies the System UIA and its entry API.
  UIA entries also participate in application/context setup. Adding an entry is
  not yet a demonstrated harmless extension route.
- libjciuiasystem.so's inspected imports include access, but not dlopen/dlsym.
  Its current injected stub is not already a general optional-library loader.
- The paired bypass depends on renderer completion cleanup. Native activation
  without the matching JS hook is not an acceptable degraded mode.
- Earlier bench work proved persistent storage across a normal reboot and exposed
  mapped-file/RO constraints. It did not establish storage availability at the
  proposed early load point, arbitrary crash recovery or cold-power durability.

Exact source identities: GuiFramework SHA256 ff733276cdbd39cfdf764aba23c2c427039b560db13c10d370f7351b1279cba4;
systemApp 985cbcbeb1dedf11b76f61ffa1224e43165f80d8eb9c8d5d853d118d2eec3432;
svcjcimmui 2c2c0494817b13a38c36a8276a39899b4096efc217e82568fe3842f8b34bb025;
mmui_config c94446b8c6e5bde79607514d3eb41036a3f56914d2d3f418605110bc250be0d0;
native System acf24ffd3719a29d2b4eefe80855ef6f164852fe3464858d07ca2d956395d302.
Full files and disassembly remain private; findings are summarized in
[reverse-engineering.md](reverse-engineering.md).

Investigate loading routes in this order:

1. Existing Mazda loading/launch mechanisms with a proven optional, failure-tolerant
   contract. Trace exact service startup plus GUI document/Utility imports and
   their failure paths; acquire only missing reference-derived files.
2. A small explicit bootstrap patch if the existing route cannot provide the
   required stock fallback. Optional code must not become a mandatory ELF dependency.
3. Process-specific launch injection only if its scope, dependencies and inherited
   environment are proven. Do not use global /etc/ld.so.preload: it affects every
   dynamically linked program ([loader documentation](https://man7.org/linux/man-pages/man8/ld.so.8.html)).
   Do not replace init, redesign boot or assume overlays are supported.

The native prototype uses a small explicit post-load hook; the renderer candidate
uses Mazda's existing developer-script slot. Neither is bench-qualified.

## Loader-probe findings

Fresh read-only captures established these FW55-specific boundaries:

- index.html:33 loads ../../data/integration/developer_mode_GuiConfig.js
  before Utility/BaseApp/GuiFramework and framework.init(). This resolves to
  **/data/integration/**, not /jci/data. The file is currently absent; normal GUI
  startup already works without it. This is a candidate bootstrap slot, not a
  proven optional-feature loader. Its parent is mode 0777; installation must
  account for that access boundary and refuse an existing unowned script.
- Utility.js:66–94 appends a script and handles onload only. It provides no
  built-in onerror or fallback. Removing a node does not undo evaluation.
- sm.conf:145–169 launches MMUI and Opera through separate dependency sets, with
  no explicit ordering edge between them. Script presence is not readiness.
- Current /data resolves through /mnt/data to /tmp/mnt/data on writable
  /dev/ffx01p4 RelFS. data_persist is a different mount. Current availability
  does not establish loader-time availability after cold boot.
- Native mmuiLoadUias builds application/context priority records before invoking
  entry loaders (0x2e08–0x2f50). Its directory mode is not a neutral plugin registry.
  Missing-library failure returns through 0x2204–0x220c/0x28ac; successful loading
  still says nothing about feature health.

The [native probe](../experiments/optional-loader/README.md) hooks the final zero
return at 0x31ac, after OEM application loading and before ServiceInit's
GUIIFM_Internal_AppsLoadingFinish call at 0x1914. It uses existing loader imports,
fits the 200-byte gap after the RX segment, and adds no mandatory dependency.
Host build: 104-byte stub, unchanged 22952-byte module length, original epilogue
retained. Missing bootstrap/symbol delegates normally; crashes/hangs do not.

This is a loading probe only. The control record, consumed trial, component hashes,
paired readiness and disable experiment below remain unfinished. No native or JS
bootstrap has been installed. Hardware validation must distinguish entry execution
from mapping, then prove the off path on a fresh startup.

New exact-source SHA256 identities:
index.html b0e116b941f29078ced19b864a1b888cf76d8bc3e4974af081efca4693e5c420;
Utility.js eff9e63497fbd0f90d5dc9e2d9403c93fc6171cc71f70319462686a423fea791;
sm.conf 52dac9b051ab02a07afdc7bdfac56402420f8230901b5a55a76a7e9c44fb2e08.
Private capture/derivation: runs/runtime-boundary-research; size, checksum and
identity matched before and after each export. No OEM writes or reboot occurred.

## Proposed activation contract

The bootstrap has a small fixed interface, no mod discovery, network access,
feature logic or configuration framework. It validates a bounded, non-executable
control record and one explicit feature bundle. Missing, invalid, unreadable or
unsupported state takes the stock path. No searching for a substitute version.

Check permission/path ownership, firmware adapter, component hashes and interface
version before activation. Use immutable versioned feature files so updates do
not overwrite mapped libraries. Do not delete old mapped versions while in use.

The disabled path must decide before loading optional native libraries or
evaluating optional JS. A successful dlopen is not successful feature activation.
Avoid custom native constructor work and JS top-level mutations; use explicit
initialization that can decline before changing OEM state. If a callback already
caused side effects, do not blindly call the original again after an exception.

Latch one configuration/bundle generation for the whole startup. The native and
renderer components must both be ready for that generation before the native
bypass can activate. If readiness is absent at the existing decision point, keep
stock behavior for that startup; no late activation or new wait in Mazda's path.
The transport and timing for that agreement remain an implementation question.
File presence alone cannot establish renderer readiness.

### First experiment: off or one attempt

Start with explicit off and a one-shot trial, rather than persistent autoload.
One owner consumes a trial request and records the attempt before optional code
executes; native and JS components share the same attempt decision. Do not consume
separate requests independently. A service respawn must not silently retry it.

If attempt-state storage cannot be verified, skip loading. A failed attempt stays
disabled until explicitly rearmed. A health report records the outcome; it does
not re-enable a consumed trial. This avoids needing a trustworthy shutdown hook
for the first experiment. RelFS write ordering and power-loss persistence still
require proof; a successful sync is not that proof.

Persistent autoload comes later. It needs a defined health boundary and crash
policy: process alive, a timer, a warm reboot or a camera home frame alone is
insufficient. A marker cleared at startup would miss later crashes; a marker kept
until shutdown can classify normal power removal as failure. Do not claim that
tradeoff is already resolved or use the OEM watchdog as a success signal.

## Disable, recovery and uninstall

| Situation | Expected behavior |
| --- | --- |
| Off before startup | Bootstrap delegates to stock; optional native/JS code not loaded |
| Disable while running | Save next-startup off; report still active/restart required |
| Missing/invalid module or mismatched pair before activation | Stock path; no partial feature activation |
| Optional code crashes or hangs | No in-process recovery guarantee; consumed trial blocks another attempt once the independently reachable restart path runs |
| Bootstrap/loader/OEM patch is broken | Off switch may be unreachable; restore originals using independent recovery |
| Uninstall | Restore pre-install files; existing conflict snapshot/one-undo contract remains |

The control write and recovery command must not depend on the optional runtime
or its UI. UART is the demonstrated bench access; SSH and USB recovery reachability
must be established separately. Do not promise a magic USB file can rescue a CMU
that never reaches its USB handler. The first implementation has no new CMU menu.

## Delivery sequence and acceptance

1. **Loader proof:** finish the narrow source trace, choose one route and document
   load order, accessible control storage, permissions and error handling.
2. **No-op boundary:** host-test off/missing/corrupt/wrong-version inputs, partial
   init, paired readiness, late load, repeated callbacks and consumed attempts.
   Check original delegation exactly once. Use actual Linux loader fixtures for
   dependency/constructor failures; a host fake alone does not prove ARM/Opera.
3. **Bench boundary:** install the bootstrap with existing backups/undo. Demonstrate
   an enabled no-op startup, then off plus restart with identical OEM-file hashes,
   optional native mappings absent and evidence that optional JS was neither loaded
   nor evaluated. Verify stock startup/access and no root remount for disabling.
   Demonstrate an interrupted trial skips the next attempt through independent recovery. No automatic boot/retry loop.
4. **One feature:** move the existing paired bypass into owned modules, keeping
   its behavior and guards. Verify one enabled startup, disabled stock startup and
   full uninstall/original startup. Measure startup cost and visible behavior.
5. **Then reuse:** add another feature only when useful; extract shared helpers
   then. Assess persistent autoload and any broader firmware change separately.

Text patches remain useful to install the bootstrap/adapters; native changes need
exact-base recipes. Most feature logic lives in our own files. Future selections
compose from verified originals, with explicit dependencies/conflicts. No fuzzy
merges, hot-unload, general event bus, third-party plugin marketplace or new scripting
engine is needed for this first boundary.
