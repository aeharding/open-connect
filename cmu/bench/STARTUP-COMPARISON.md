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
GUI input during startup. Retrieve at 195 seconds, then qualify the kernel/host
clock with `clock_reference` for that exact boot. The first sample and output
size are retained; do not call this whole-kernel resource coverage.

```sh
python -m open_connect.startup_reference --live --condition stock \
  --host my-cmu --bundle runs/comparison/stock-1
python -m open_connect.startup_reference --live --condition open-connect \
  --package caca0596c53b678cc587226a362bce48f04652a65dcd359331ef45415dddd48f \
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
