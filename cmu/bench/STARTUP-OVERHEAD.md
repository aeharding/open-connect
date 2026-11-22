# Startup overhead candidate

The owner's target is no measurable added startup delay versus stock. This
candidate keeps verification and RAM staging synchronous while removing repeated
checks and fixed waiting. It is not qualified by source changes or host tests.

The hook holds one operation lock from bootstrap through selection. It hashes
the complete private package before sourcing its selector. The ordinary active
path verifies baseline/current snapshots, their physical targets and dependencies
before any listener or feature effect. Its exact package dependency rows reuse
the same locked source proof; OEM and composed paths are independently hashed.
Copies into the private RAM session are independently verified. Recovery,
pending work, different feature/backend IDs and NVRAM transitions retain their
full transaction checks. Standalone selection remains available to the older
embedded hook during update. No persistent verification cache is introduced.

The listener must own the loopback LISTEN socket and match its PID, birth time,
BusyBox executable and API argument before publication. Readiness has a one-second
bound with short paced retries. Boot leaves an existing USB runtime in control.
The copied session stays alive for in-flight requests. Budget renewal, original
login inode/hold, NVRAM, root mounts and stock fallback remain part of verification.

Run `python tests/run_offline.py`. Linux additionally exercises real flock,
`/proc`, BusyBox tcpsvd and first-client readiness. Set `OC_TEST_BUSYBOX` to a
compatible BusyBox containing tcpsvd when the distribution omits that applet;
CI supplies a pinned upstream image. These tests also cover corrupt RAM copies,
failed bind and signals before publication. The modern Linux fixture adapts only
the target BusyBox 1.19.2 timeout syntax and isolated physical paths.

Build with `make release OUT=runs/startup-overhead-build`. For the first live
comparison, retain the unchanged compiled members of dev.8 CI44951500558/source
`764d76e0` if the local compiler differs. Package the authored static delta through
the existing Make/shell build. Record actual source, bundle, public/private
manifest and compiled-member provenance. Do not label a local assembly CI-built.

The first pilot retains the current fixture: Wireless1/Base1/Pandora1,
Allow/Skip1, product UART/SSH0, paired iPhone8,4/iOS15.8.8 with USB on the Mac,
Ethernet/reference SD, receive-only UART, fixed exposure105/gain32 and 12.02V/2A.
Keep idle projection without a route or playing audio. Exclude the BDS, Wi-Fi
Aha-edge and Android Auto trial policies. Update once through maintained
maintenance and exclude its setup restart from the comparison.

Use frozen capture `ab8993a5` for one passive 30-second ACC-off start, pinning the
new installed instance. Keep all attempts and failures. Analyze with `4da76e1`,
clock-map the actual boot and review adjacent Home/CarPlay frames. Do not inject
input or connect SSH during primary collection. After capture, retrieve
`/tmp/open-connect/startup-times`: phase names and `/proc/uptime` values for hook
entry, source verification, targets/dependencies, session readiness, budget
commit, feature copy and selector exit. Their order follows the executed path;
standalone recovery has its own verification stamp. They are diagnostic data,
not startup authority. Keep clock and phase resolution limits explicit.

Compare the early collector sample, visible Home/dashboard, matched CPU/RAM/I/O,
API/Settings readiness and loaded feature identities with the sealed same-config
dev.8 control. Phase times locate remaining work; they cannot establish usable
input/audio or stock parity. A matched stock comparison is still required before
claiming no measurable added delay. Repeat when a pilot gives a concrete reason.

Independent undo uses the pinned dev.8 CI bundle through maintained maintenance,
then a fresh ACC boot. Verify exact control bytes, retained selections and
baseline, loaded originals, native wireless return and physical root read-only.
Existing bench SSH recovery and stage-1 restore remain independent. Keep OEM
files, generated private compositions, phone identifiers and raw captures private.
