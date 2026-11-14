# Boot selection experiments

**Firmware 55.00.750B NA. Bench prototype, not an installer.**

The normal branch of /usr/bin/autostart runs a small selector before normal-mode
setup, the Logger and Service Manager. It consumes one trial record and checks
file/directory fsync before choosing a fixed service configuration. Missing,
changed or spent control keeps Mazda's original configuration.

The parent invokes the selector directly with a five-second timeout and redirects
output. It does not wait on a pipe that a surviving descendant could hold open.
The original one-shot selector has no rearming or health policy. The finite-budget
adaptation below adds explicit confirmation/renewal; neither changes Mazda's watchdog.

## Result

Two actual warm boots passed on 2026-11-13:

1. An exact copy of Mazda's sm.conf was selected; the running SM command line
   confirmed its path, and the record was spent.
2. With no intervention between boots, the spent record selected /jci/sm/sm.conf.

Fresh root access, read-only root, unchanged existing JS/native images and Home
were verified. Independent undo restored autostart's original bytes, inode,
metadata and link count after the second boot.

Follow-up bench adaptations exercised an MMUI process crash and a trial-only
frontend infinite loop. Both triggered Mazda's watchdog reset and returned to
the baseline configuration; the JS result used the saved crash archive and a
fresh postboot check after live serial logging missed a marker. The original
observer failure remains preserved.

Two separate full supply cuts preserved consumed records: one in normal runtime,
and one during a three-second pause after early commit but before services.
The early cut returned to OEM SM configuration. Neither interrupted rename/fsync;
the first early observer refused before any power command and is preserved.
These are one actual cut per power case, not a persistent retry policy
or general durability guarantee. See [the findings](../../docs/reverse-engineering.md#startup-selection-and-reset-evidence).

The existing comparison JS stayed installed; “baseline” means the pre-existing
bench configuration, not an entirely stock unit. Independent undo removed every
trial hook; there was no additional boot after removing each hook.

## Reproduce the code

~~~sh
python -m unittest discover -s experiments/boot-selection -v
python experiments/boot-selection/build_flush.py --output runs/selector-build
python experiments/boot-selection/prototype.py \
  --original /private/firmware/usr/bin/autostart \
  --config /private/firmware/jci/sm/sm.conf \
  --flush runs/selector-build/flush-arm \
  --directory /tmp/mnt/data_persist/oc-boot-0123456789abcdef0123456789abcdef \
  --output runs/selector-payload
~~~

The build needs clang and ld.lld. Original inputs are exact-hash checked; generated
OEM-containing files belong in ignored runs/. Rendering opens no device.
selector.sh.in and flush.c run on the CMU; Python builds/checks on the host.
probe-bind.sh.in and probe-flush.sh.in are confined filesystem capability probes.

The host checks exercise real shell/file operations with OS shims, including
corrupt input, failed flushes and a timeout with a surviving descendant.
They do not emulate ARM or RelFS. On the actual CMU, the 1,120-byte ARM helper
returned success for file and directory fsync before the reboot experiment.

A timeout cannot guarantee progress through uninterruptible kernel filesystem
I/O. Successful fsync alone is not proof against every power failure.

Private evidence: runs/boot-selector-flush/result.json and
runs/early-selector/result.json, runs/native-fault-trial/result.json,
runs/js-hang-trial-v2/result.json, runs/power-cut-trial/result.json and
runs/early-power-cut/result.json, with
unchanged raw bundles and failed attempts. OEM inputs, generated payloads, credentials and captures are not published.

## Private configuration-view probe

`namespace.c` unshares the mount namespace, makes its mounts recursively private,
then executes one absolute program with its arguments and environment preserved.
A failed isolation step never executes that program.

`probe-namespace.sh.in` exercised the actual ARM helper on firmware55: the child
saw a read-only `Warn` settings view while the parent simultaneously saw original
`Info`. Exiting the child removed the view without explicit unmount. Original
identity/hash and physical root RO were checked before, during and after;
scratch and staged deliveries were removed. No reboot or service change occurred.

~~~sh
python -m unittest discover -s experiments/boot-selection -p test_namespace.py -v
python experiments/boot-selection/build_namespace.py --output runs/namespace-build
~~~

The four host checks cover call ordering, isolation failures and preserved exec
arguments/environment. They do not emulate Linux mounts. The probe template needs
a fresh nonce and a checked DATA-delivery guard before execution.

Whole-service startup is still unqualified: private propagation changes how later
USB/resource mounts and shutdown processes see mounts. This is not a root-code
sandbox or a decision to adopt namespace isolation for the product.
Private evidence: `runs/combined-startup/namespace-result.json`.

## OEM logging environment probe

The exact firmware55 `libjcicommon.so` reads settings files before environment
variables. `log-query.c` queries its current level and native acceptance filter
from a disposable process; it does not hook a Mazda service.

Three actual fresh processes gave `Info → Warn → Info` when only the middle one
received `COMMON_LOG_LEVEL=Warn`. Its filter admitted Warn and rejected Info.
Each process sampled twice, two seconds apart. Persistent settings and root RO
were unchanged; the temporary library was removed. This is not a performance
claim or a complete service-inheritance test.

To build with an explicitly supplied private original:

~~~sh
clang --target=armv7-none-eabi -march=armv7-a -marm -mfloat-abi=hard -mfpu=vfpv3 \
  -Os -fPIC -ffreestanding -fno-stack-protector -fno-unwind-tables \
  -fvisibility=hidden -c experiments/boot-selection/log-query.c -o /private/output/query.o
ld.lld -shared -z defs --build-id=none -soname oc-log-query.so \
  /private/output/query.o -L/private/firmware/jci/lib -ljcicommon -o /private/output/query.so
~~~

The bench input was `libjcicommon.so` SHA256
`0f3bf19fa890332ef2196531eebed3ce6e166cf805cc1edc1e53f98a873effbf`.
Use a verified DATA delivery and only preload the result into a disposable utility,
never into an existing service. Private evidence: `runs/combined-startup/log-query-result.json`.

## Composed startup

One actual selected/baseline pair passed on firmware55:

- Stitcher did not auto-start, then ran in baseline.
- SM/MMUI inherited Warn; the native filter rejected Info. Baseline had no
  override and native Info messages returned.
- A copied MMUI plugin loaded and invoked our own module. Baseline had neither
  that mapping nor its marker.
- A copied index retained the OEM resource base and ran our JS marker. Baseline
  used the original Opera entry path with no marker.

Both reached Home. The original autostart was independently restored and holds
cleaned; prepared data remained inactive. The prior local comparison JS remained
the bench baseline. This proves composition and code entry, not a shipping feature
or a performance improvement. One timing/resource sample pair is insufficient.

Build from explicitly supplied private originals and the ARM flush helper:

~~~sh
python experiments/boot-selection/compose.py \
  --original /private/firmware/usr/bin/autostart \
  --config /private/firmware/jci/sm/sm.conf \
  --plugin /private/firmware/jci/mmui/svcjcimmui.so \
  --index /private/firmware/jci/gui/index.html \
  --common /private/firmware/jci/lib/libjcicommon.so \
  --flush runs/flush-build/flush-arm \
  --directory '/tmp/mnt/data_persist/oc-boot-<fresh-32-hex-nonce>' \
  --output runs/composed-payload
~~~

Supply a fresh 32-digit hexadecimal nonce and a new output directory.
This builds only; it does not install or reboot. Every extra generation file is
checked before the selector consumes and flushes its record. Only successful
selection changes the service configuration and exports the logging override.
The public checks exercise that ordering and reject changed dependencies.

Private actual evidence: `runs/composed-generation/result.json`, including both
closed observer/video bundles, fresh identities, original-file undo and cleanup.
The initial host timeout/partial-input refusal remains separately recorded;
it happened before publication and was reconciled before completing preparation.

## Finite attempt budget

`budget.py` adapts a fresh composed payload. `budget.sh.in` is the target policy;
the original one-shot files remain unchanged.

~~~sh
python experiments/boot-selection/budget.py \
  --source runs/composed-payload --output runs/budget-payload --attempts 2
~~~

This builds only. Two is an experiment parameter, not a production default.

- Default `STATUS` reads only. The startup hook explicitly calls `SELECT`.
- A new generation gets one startup until `CONFIRM`; confirmation never refunds
  the reserved attempt. Every selected boot spends an attempt before effects.
- `RENEW` is explicit maintenance for a confirmed generation. It requires the
  generation, expected epoch and current boot, increments the epoch and prevents
  another selection in that same boot. There is no ACC listener or automatic renewal.
- Mutations use one exclusive lock, exact records and checked file/directory
  flushes. An interrupted mutation can leave a lock requiring administrative
  recovery. The checksum detects content changes, not rollback to an old valid record.

Eight host checks cover real shell/file operations, competing calls, stale
commands, failed flushes, changed dependencies and late-fault exhaustion.

The actual three-boot test on firmware55 passed: first selection used one attempt;
explicit confirmation kept that charge; the second selection reached Home with
both attempts spent. One identity-checked MMUI SIGSEGV then caused Mazda's reset,
and the exhausted record selected baseline with all four effects omitted.
Independent undo restored original autostart and removed its holds.

This is one external process fault after readiness, not an optional-code defect
or interrupted-write durability test. Renewal has host coverage only. No supply
commands were used; the existing comparison JS remained installed.
Private evidence: `runs/attempt-budget/result.json`, three closed video/observer
bundles, confirmation and independent undo. A host import refusal before opening
UART is preserved separately.


## Select the paired disclaimer feature

One corrected bench trial ran the native bypass and JS cleanup together:
`IntroAnimation → HomeScreen`, then intro disposal. The following baseline boot
omitted both selected components without restoring feature files. Independent
autostart undo/hold cleanup closed the trial. This is selection evidence, not a
new performance or no-flash claim. Private evidence: `runs/selected-feature-v2/result.json`.
The first trial's path-truncation failure and explicit baseline recovery remain
separate in `runs/selected-feature/result.json`.

`feature.py` builds this one-shot configuration for the independently
implemented [native/JS handoff](../intro-handoff/README.md). First run that
experiment's `check.py` with private originals to produce a passing pair directory.

The selected MMUI plugin reads a generated XML file that points its system UIA
at `uia.so`. A selected GUI index routes only `systemApp.js` to its companion.
Other apps and resources keep their OEM paths. Neither installed feature file
is replaced; the only root integration is the existing early selector.

~~~sh
python experiments/boot-selection/feature.py \
  --original /private/firmware/usr/bin/autostart \
  --config /private/firmware/jci/sm/sm.conf \
  --flush runs/selector-build/flush-arm \
  --plugin /private/firmware/jci/mmui/svcjcimmui.so \
  --mmui-xml /private/firmware/jci/mmui/mmui_config.xml \
  --index /private/firmware/jci/gui/index.html \
  --pair runs/paired-feature-check \
  --directory /tmp/mnt/data_persist/oc-boot-0123456789abcdef0123456789abcdef \
  --output runs/selected-feature-payload
~~~

Use a fresh nonce for a real installation. This command only builds files; it
does not install or reboot. The copied plugin changes its configuration filename
and the containing ELF segment size, without adding executable instructions.
Mazda's `libpath` and `lib` fields each accept 49 bytes; splitting the generation
parent and relative `oc-boot-<nonce>/uia.so` path avoids truncation.

Public checks run with the normal test command above. To also test exact OEM
loader fields and the real GUI dispatcher, set `OC_FEATURE_INPUTS` to a private
JSON file containing absolute paths named `plugin`, `mmui_xml`, `index`,
`utility`, `framework` and `pair`. The last three are the original
`Utility.js`, `GuiFramework.js` and the passing pair directory. Missing private
inputs are reported as skipped checks.
