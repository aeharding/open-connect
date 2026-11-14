# One-shot boot selection experiment

**Firmware 55.00.750B NA. Bench prototype, not an installer.**

The normal branch of /usr/bin/autostart runs a small selector before normal-mode
setup, the Logger and Service Manager. It consumes one trial record and checks
file/directory fsync before choosing a fixed service configuration. Missing,
changed or spent control keeps Mazda's original configuration.

The parent invokes the selector directly with a five-second timeout and redirects
output. It does not wait on a pipe that a surviving descendant could hold open.
There is no rearming, health policy, optional feature or watchdog modification.

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
