# Installed Base optimizations comparison

Compare five Base-on starts, then five Base-off starts on the same pinned
Open Connect CI package, with Allow/Skip selected, UART/SSH off and Pandora on.
This reverses the earlier bare Info-then-Warn block order. It does not pool those
earlier controls or turn their mechanism checks into installed-bundle evidence.

Keep the same phone/Ethernet/reference SD, supply, camera/manual exposure, idle
daytime wired dashboard, no route/audio and30-second ACC-off. Set each choice
through the maintained UI/backend, then complete a separate unmeasured setup
restart before the block. These flags assert the already-applied condition; they
never change a preference. Per-run pre/postflight require saved/applied choices,
actual native MMUI logging, physical Info original and the exact RAM-file policy
to agree. The Base-off case requires no global RAM override, rather than writing
an Info override. The older bare-logging data-choice file must be absent.

Use the original AE collector-only bench hook matching the existing profile.
The product supplies the logging resource. No experiment hook writes it, and no
second profile/daemon is installed. Keep the controller's original stage-1 inode,
exact data manifest and independent restore. Use STARTUP-COMPARISON.md for that
profile setup/undo; restore the original stage-1 before final uninstall, restart
and independently verify original19 files/metadata/mappings, absent product and
RAM logging/observer output, actual native Info and rootRO. Byte restoration alone
does not restore cached logging policy.

```sh
python -m open_connect.startup_batch --live --host my-cmu \
  --condition open-connect --package INSTALLED_INSTANCE_MANIFEST_SHA \
  --pandora 1 --base 1 --bundle runs/base/base-on
python -m open_connect.startup_batch --live --host my-cmu \
  --condition open-connect --package INSTALLED_INSTANCE_MANIFEST_SHA \
  --pandora 1 --base 0 --bundle runs/base/base-off
python -m open_connect.startup_export runs/base runs/base-public --base-optimizations
python -m open_connect.startup_plot runs/base-public/startup-samples.csv \
  runs/base-public/startup-resources.svg
```

Use the actual installed instance ID, not the public USB manifest hash. Record
the CI source/version/ZIP, package, collector and capture/analysis revisions.
Capture UART/camera before ACC-off, local180-second system counters with1-second
minimum pause, no SSH/UI during startup, fetch225seconds afterON, then seven
per-boot clock exchanges. Annotate completed Home entrance and first complete
visible wired dashboard using adjacent decoded frames. Visibility is not usable
input/audio readiness; include frame sensitivity and uncalibrated latency.

Export reparses raw trace framing/digests, checks saved JSON/CSV, recomputes clocks
against raw replies and validates annotation PTS/arithmetic. Review the actual
video milestones. Report all attempts, failures, spreads and regressions, CPU and
named RAM/I/O over actual endpoints in uptime20–170seconds; retain the early
sampling gap. Don't sum device/partition counters or infer missing values. Phone/
iOS unrecorded, sequential order/drift, single-bench and wired-versus-wireless
limits remain explicit. Publish only reviewed numeric data, never OEM inputs,
credentials, raw videos/UART/process memory or personal map images.
