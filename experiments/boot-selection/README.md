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

This establishes the early boundary and one-shot fallback. It does **not** prove
crash/watchdog recovery, cold startup, power-loss durability or a usable health
policy. The existing comparison JS stayed installed; “baseline” in this experiment
means the pre-existing bench service configuration, not an entirely stock unit.
There was no third boot after removing the hook.

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
runs/early-selector/result.json, with unchanged raw bundles and initial host
failures. OEM inputs, generated payloads, credentials and captures are not published.
