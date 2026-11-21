# First stock / Open Connect wired startup batch

Question: how do the initial Open Connect features and installed runtime change
visible startup milestones and resource pressure on the same stock-service bench?
This is a controlled ACC shutdown, not supply loss, overnight parking or wireless.

Declare five stock-feature starts followed by five candidate starts. Block order
avoids ten installation cycles but cannot separate condition from longer-term
drift. Keep every attempted start and observer failure. An uncertain relay write
stops the batch without resending. Camera/SSH failures are not CMU failures.

Candidate: successful CI run **44874819096**, source **3713f240e21f2e7ac40e24c3f4a2083d08994849**,
version **0.3.0-dev.4**. Artifact ZIP SHA256
`4a501e14c53d7ba2b76a9079b66518dd6cbf4879eb58bf837829b11408650cbe`;
USB ZIP `96e7174c97c0b3f3bc915f8b99dd63942e67f9877b3014c12cd765b4b398aa64`;
package manifest `caca0596c53b678cc587226a362bce48f04652a65dcd359331ef45415dddd48f`.
Select Always enabled / Skip, with UART and SSH product options off. Bench
owner-key access remains unchanged. There are no service or wireless changes.

Use exact **74.00.324A NA/cmu150_NA**, the same wired phone, Ethernet adapter,
FAT SD, camera and receive-only FTDI UART. Keep the phone connected throughout;
its model/iOS is not yet qualified, which limits cross-bench comparisons. No audio
or navigation route runs: the final scene is the CarPlay dashboard, map and
Not Playing. Camera: 1280x720, requested 5 fps, manual exposure readback 105,
gain 32. Do not change supply voltage or send supply commands.

Use the same local stage-1 observer in both conditions: system counters only,
180 seconds, minimum one-second pause, output in RAM. Each start has 30 seconds
ACC-off, camera/UART from before OFF until 120 seconds after ON, and no SSH or
GUI input during startup. Retrieve at 225 seconds, then qualify the kernel/host
clock with `clock_reference` for that exact boot. The first sample and output
size are retained; do not call this whole-kernel resource coverage.

```sh
python -m open_connect.startup_reference --live --condition stock \
  --host my-cmu --bundle runs/comparison/stock-1
python -m open_connect.startup_reference --live --condition open-connect \
  --package THE_VERIFIED_INSTALLED_INSTANCE_MANIFEST_SHA256 \
  --host my-cmu --bundle runs/comparison/open-connect-1
python -m open_connect.clock_reference --live --host my-cmu \
  --expect-boot THE_RETRIEVED_BOOT_UUID --bundle runs/comparison/clock-1
```

Repeat with fresh bundles through five starts per condition. Pin the committed
collector/host revision before the first run; `startup_reference` stores actual
source bytes and refuses modified measurement code. Setup/undo is in
[the reference instructions](STARTUP-REFERENCE.md). Install through normal SD
maintenance between blocks, retain independent recovery, and verify normal
uninstall plus original startup after the candidate block.
The installed package includes an INSTANCE data member. Verify its members match
the pinned public package (excluding INSTANCE), then use the full installed
manifest digest for `--package`; do not use the public USB digest there.

Alternatively `python -m open_connect.startup_batch --live --host my-cmu
--condition stock --bundle runs/comparison/stock` runs the five observers and
per-boot clock queries serially, stopping on the first failure. For the candidate
block supply `--condition open-connect --package` with the digest above. The
preflight also requires the install completion notice to have been dismissed.

Observed correction: the original host source 58ba042 retrieved at 195 seconds.
All five stock traces finished before that. The first candidate trace ran from
uptime 16.01 to 195.98 seconds, and its retrieval arrived before completion.
The original failure and same-boot late retrieval are preserved. Exclude that
attempt from the primary comparison because the premature SSH overlapped the
end of collection; run five candidate starts with the later retrieval. Collector,
hook, sample duration, video/UART windows and common analysis window are unchanged.
Retain each run's actual host revision rather than relabeling the stock evidence.

Measure first Home icons visible and first CarPlay dashboard visible from video,
bracketing each transition between actual decoded frame PTS. Use the retained
AVFoundation input start for the qualified host clock domain and the per-boot
clock bound for kernel-relative intervals. Report the bounds, not camera launch
time or an unjustified single precise timestamp. These are visual milestones;
they do not establish first usable touch or projection. Miatafy's wireless and
touch milestones remain different definitions, not reproduced results.

Report per-run memory counter range and first/last values, including empty
MemAvailable. For comparable CPU and I/O endpoints use the first sample at or
after uptime 20 seconds and last sample ending at or before 170 seconds, retaining
the actual durations. Keep each disk's counters separate, avoiding parent/partition
double counting. Preserve full traces for readiness-relative analysis later.

Measure injected input-to-visible-response separately on the same settled scene
under each condition. Keep its operation/timestamps and sampling method explicit;
the startup batch is passive. Do not infer responsiveness from a dashboard image.

## Analysis and settled input reproduction

The analysis helpers are experimental host code, outside the release package.
They retain the actual collection revisions. Stock collection used `58ba042`;
the matched candidate block used `4a7e4cf`. The later analysis commit does not
replace those identities. The portable response wrapper was checked in after
capture; the original per-condition host scripts remain in the private bundles.
The target input probe is byte-identical in both recordings (SHA256
`b726c1e4a6d116bd0e0985943951f8cdc7cee30f0949b78f99c4f1c08e399ea7`).

`startup_response` records five Right/Left pairs on a settled, idle CarPlay
dashboard, with no audio/navigation route. Wait until kernel uptime is at least
300 seconds. Each key report has press/sync/release/sync; two unmeasured Left
reports establish the dock selection before the ten timed inputs. It records a
60-second system-only SSH trace and a 5 fps camera video, then queries the boot
clock. This SSH sampler is appropriate for the already-running workload; it is
not the startup collector. Reidentify the Virtual Keyboard before writing.

Stage `cmu/bench/startup-response.sh` as data at
`/tmp/oc-dev-response-comparison.sh`, refusing an existing path. Verify its SHA256
before execution; the wrapper checks it again and never retries failed inputs.
Use the bench's existing authenticated SSH alias/configuration; this experiment
does not create access. The UART remains receive-only during startup.

```sh
python -m open_connect.startup_response --live stock BOOT_UUID - \
  runs/comparison my-cmu /path/to/ssh-config
python -m open_connect.startup_response --live open-connect BOOT_UUID \
  INSTALLED_INSTANCE_MANIFEST_SHA256 runs/comparison my-cmu /path/to/ssh-config
```

The same phone must already be visibly foregrounded in CarPlay **before** each
block's first OFF. Confirm it on camera; a D-Bus acknowledgement does not prove
the foreground changed. The accepted recordings return automatically to the
same dashboard after restart, without input during the measurement window.
Two earlier candidate recordings started on Mazda Home; one also had the
premature retrieval described above. A third candidate attempt was cancelled
after discovering this fixture mismatch. All three are retained outside the
five accepted candidate runs, with their original outcomes.

For each startup, use `startup_frames TRIAL START_PTS STEP` to inspect actual
decoded video frames. Record adjacent frames bracketing the completed Home
carousel entrance animation and the first fully visible CarPlay dashboard
(the map may still be loading):

```sh
python -m open_connect.startup_frames runs/comparison/stock/trial-1 54 .2
python -m open_connect.startup_annotate runs/comparison/stock/trial-1 \
  HOME_BEFORE_PTS HOME_FIRST_PTS CARPLAY_BEFORE_PTS CARPLAY_FIRST_PTS
```

These are manual visual annotations, not first-usable-input measurements.
`startup_annotate` verifies adjacency and retains ACC-relative and kernel-clock
bounds. AVFoundation timestamps share the qualified host clock domain, but
sensor/display and relay actuation latency are uncalibrated.

The local bundle layout is `stock/trial-1` through `trial-5`, sibling `clock-1`
through `clock-5`, and the same layout under `open-connect-matched/`. Input
recordings are `response-stock/` and `response-open-connect/`, with
`response-clock-stock/` and `response-clock-open-connect/` beside them. Do not
rename failed runs into accepted slots. To independently parse raw retrieval,
verify saved JSON/CSV against it, and export only numeric fields:

```sh
python -m open_connect.startup_export runs/comparison runs/public-comparison
python -m pip install matplotlib==3.10.9 numpy==2.5.5
python -m open_connect.startup_focus runs/comparison
python -m open_connect.startup_input_export runs/comparison runs/public-comparison
python -m open_connect.startup_plot \
  runs/public-comparison/startup-samples.csv runs/public-comparison/startup-resources.svg
```

The input analysis uses the same fixed camera region (400×35 pixels at 180,425
in a 1280×720 frame) and a count of RGB channels all above 160. At 100 such pixels
the map focus border has visibly appeared; the same threshold applies to both
conditions. Review the actual transition frames before publishing, and reselect
the region if another camera's framing differs. The exported intervals include
input-write duration and clock bounds; negative lower bounds express unresolved
timing, not negative physical latency. No fine-latency claim is supported by 5 fps.

The published CSVs exclude raw files, personal map images, network addresses and
private paths. `startup-runs.csv` includes common-window RAM bounds and CPU;
`startup-io.csv` keeps devices separate, leaving deltas blank when a device is
missing at an endpoint. Do not add whole disks to their partitions. Replot the
public `startup-samples.csv` without any private captures or CMU access.
