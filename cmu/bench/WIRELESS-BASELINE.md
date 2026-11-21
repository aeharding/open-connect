# Wireless startup baseline

Use one Base-off pilot, then five Wireless-on/Base-off starts and five
Wireless-on/Base-on starts of the same final dev.8 CI artifact. Keep the pilot
and one unmeasured setup start between blocks separate. Keep every attempt,
association miss, observation cutoff and recorder failure in acquisition order.
Sequential blocks cannot separate Base from a step change in conditions.

Pin firmware74.00.324A NA, iPhone8,4/iOS15.8.8, the existing Bluetooth pairing,
Mazda Wi-Fi Apple CarPlay mode, phone USB on Mac, CMU Ethernet/reference SD,
Allow/Skip1, Pandora1, UART/SSH0, supply12.02V/2A and existing manual camera settings.
Begin from the idle dashboard without route or playback. No GUI input or SSH
polling during primary startup observations. Wi-Fi station count is an outcome;
zero stations does not discard the attempt. Applied policy and USB carrier must
still match the declared condition.

Reuse the existing exact-content stage-1 observer and independent restore.
Capture camera and receive-only UART before30-second ACC-off. Record video until
ACC+210seconds with a260-second total FFmpeg cap. Keep the existing local
180-second collector and ACC+225-second retrieval initially. Check actual final
camera frames and resource-sample bounds against projection+120seconds on the
pilot before batching; extend collection/watchdog/fetch together only if needed.

```sh
python -m open_connect.startup_reference --live --host my-cmu \
  --condition open-connect --package INSTALLED_INSTANCE_MANIFEST_SHA \
  --pandora 1 --base 0 --wireless 1 --bundle runs/wireless/pilot
python -m open_connect.startup_batch --live --host my-cmu \
  --condition open-connect --package INSTALLED_INSTANCE_MANIFEST_SHA \
  --pandora 1 --base 0 --wireless 1 --bundle runs/wireless/base-off
# Apply Base1 and complete one separate unmeasured setup start before this block.
python -m open_connect.startup_batch --live --host my-cmu \
  --condition open-connect --package INSTALLED_INSTANCE_MANIFEST_SHA \
  --pandora 1 --base 1 --wireless 1 --bundle runs/wireless/base-on
```

Record exact CI/source/ZIP, installed instance and collector/analysis revisions.
Annotate Home and first complete visible projection from adjacent decoded frames;
visibility does not establish usable input or audio. Keep black intervals and
reconnection misses explicit. Retain the existing common uptime20–170second
RAM/CPU/I/O window and inspect raw samples for projection-relative settling.
Early unsampled resources remain unknown. Use the seven-exchange per-boot clock
mapping and retain uncertainty and all individual results.

Do not rerun wired controls, pool old trials or claim Miatafy reproduction unless
milestones and conditions match. No new input harness is needed: primary runs
stay passive, and software-input responsiveness, physical input, audio and
overnight-car behavior remain separate qualifications. Restore the original
stage-1 script after collection and retain the independent undo. Publish numeric
exports and authored tooling only, never raw UART/video, OEM files or access data.

Extract named native UART events from completed trials without adding collection:

```sh
python -m open_connect.startup_wireless runs/wireless/base-off/trial-{1,2,3,4,5} \
  > runs/wireless/base-off-events.csv
```

This exports only numeric timestamps, fixed event names and trial metadata.
Repeated observations remain separate; missing records have empty times. A
missing or duplicated new-boot syslog marker prevents timestamp attribution.
The native logger's origin is separate from camera/ACC and mapped kernel time.
DHCP startup is not an AP-readiness measurement, and a session event does not
prove visible projection, input or audio. UART buffering/drops and the internal
Miatafy profiler's different triggers remain explicit comparison limits.
