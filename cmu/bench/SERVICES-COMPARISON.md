# First service choice: Pandora

Question: on the same Open Connect build, does not starting Mazda's built-in
Pandora improve controlled ACC startup or resource pressure, while retaining the
wired dashboard and the checked non-Pandora services? This is not a wireless,
overnight, physical-input or audio qualification.

Candidate: CI 44893957634, source
`c98c9ce4f048255805813a9485eedff8bbdd9816`, version 0.3.0-dev.6.
USB ZIP SHA256 `02a50685b55f1a52e51178e0fcaa27b4ea898cf0c0554936edfce1e4e6fd7381`;
public manifest `ff3032883f80a7e8aa7fc8fcc74ce75f1e346ec4248082b7f7f170132675817d`.
Use its actual installed INSTANCE manifest for `--package`.

Declare five starts with Pandora on, then five with it off, on the same installed
build. Select each through Services and finish a setup restart before its primary
block; the existing observer requires the selected snapshot already applied.
Keep the original five stock controls separate: these are ten new Open Connect
starts, not relabeled stock trials. Sequential order/drift remain limitations.
Retain every attempted run and distinguish observer/condition issues from CMU faults.

Follow [the existing startup comparison](STARTUP-COMPARISON.md): exact74.00.324A NA,
Allow/Skip, UART/SSH product options off, same connected wired phone/Ethernet/SD,
idle map/Not Playing dashboard, no route or audio, same camera manual settings,
30 seconds ACC-off, no supply commands, video/UART before OFF through120s afterON,
180-second local system-only resource collection with minimum pause1s, retrieval
after225s then the per-boot clock bound. Restore the exactcaca0596 reference SD
payload before the first timing OFF. No SSH or UI input during measured startup.
Phone model/iOS remain unrecorded; carry that limitation forward.

```sh
python -m open_connect.startup_batch --live --host my-cmu \
  --condition open-connect --package INSTALLED_INSTANCE_SHA256 --pandora 1 \
  --bundle runs/service-comparison/pandora-on
python -m open_connect.startup_batch --live --host my-cmu \
  --condition open-connect --package INSTALLED_INSTANCE_SHA256 --pandora 0 \
  --bundle runs/service-comparison/pandora-off
```

The assertion flag does not change settings. Pre/postflight bind actual status,
native SM autorun/state/PID and boot-local Pandora start records to the requested
choice. Enabled requires a running process and one start; disabled requires no
start record or active process. The collector/hook/sampling bytes are unchanged.
Commit the measurement source before the first run; do not rewrite older manifests.

Annotate the same completed Home and first fully visible dashboard milestones
between adjacent actual decoded frame timestamps. They are visual readiness,
not first usable touch/audio. Analyze CPU and separate-device I/O over uptime
20–170s, retain actual endpoints, report named RAM counters and all per-run spread.
Do not treat RSS as freed RAM or infer performance from process counts.

```sh
python -m open_connect.startup_export runs/service-comparison \
  runs/service-public --services
python -m open_connect.startup_plot runs/service-public/startup-samples.csv \
  runs/service-public/startup-resources.svg
```

The service exporter independently reparses the raw trace/clock and native
pre/postflight records, and emits `pandora-on`/`pandora-off` numeric cohorts.
Use the original focus/input helpers for any separately declared settled input
workload; do not claim finer latency than their 5fps observations support.
Keep raw captures, OEM files, logs and personal map imagery private. Verify normal
setting restoration, reinstall/uninstall and original startup before closing the
candidate. Record unchanged recovered originals and loaded code independently.
