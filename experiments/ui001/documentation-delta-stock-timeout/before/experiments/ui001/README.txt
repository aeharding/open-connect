UI001 — REVIEW PACKAGE, NO LIVE UI OR CHILD PROBE AUTHORIZATION
Target55.00.750B/cmu150_NA/root. Sole UART/camera owner t14; coordinator t6.
Package uses only installed /jci/tools/jci-dialog --info --no-cancel --title=...
--text=... . It adds no imaginary dialog timeout, target file or configuration.

CURRENT REVIEW REVISION
See freeze.json for exact current source copies/hashes and final test evidence.
notes/ui001-review.txt R1-R4 motivated the revised startup handling, shared
sleep4 probe, independent target TERM timeout and honest readiness reporting.
Old prepared/review-20261112/ is REJECTED/HISTORICAL, never a live payload.
prepared/review-v2-20261112/ is a rendered review example, not a reusable live ID.
Default prepare/invoke operations are offline. No program in this package
has been run against real UART/camera by the developer.

LIFECYCLE / BOUNDS
Foreground CMU watchdog owns one background native dialog. It holds shell state
only, records fresh $!, direct PPID, /proc/stat field22 start ticks and full NUL
cmdline hex including unique32-hex run title/text. Parsing strips through FINAL
') ' and needs >=20 remaining tokens, matching observed44-field vendor stat.
Before first identity, assignment-only HUP/INT/TERM traps save pending status;
they cannot exit the spawn/$! assignment window or alter $! by starting jobs.
Cleanup can boundedly recover missing identity using direct PPID + stable start
+ exact unique full argv; it never signals a mismatch or unreadable identity.
After readiness, traps enter the same cleanup. Signal guard is rechecked before
ONE TERM. Up to3 one-second grace checks; wait is used only on gone/zombie child.
Every normal/trapped exit emits cleanup result and actual wait rc or honest
unknown; actual early child failure is preserved, zero early/noREADY returns79.
No KILL, Ctrl-C, process-name matching, detached watchdog/state file or target
persistent/RAM file is used. No process identity is a historical reusable PID.

UI inner timer40 one-second sleeps, expected completion about43s plus inspection
cost. Independently wrapped in observed BusyBox grammar:
 timeout -t 47 -s 15 /bin/sh -c BODY
Frozen host runner deadline60 keeps UART through actual END+new prompt.
Probe reuses SAME lifecycle with /bin/sleep4 argv, inner timer1, independent
TERM6s and host15s. Child duration is explicitly4s; a3s proof cannot pass.
Reviewed physical TX lines: UI max180B, probe max179B, including nested quoting,
both <=600B; totals~7KiB over real LF-delimited lines. The sleep4 probe is also
a transport calibration for this longer multiline profile before any modal.

Hard limits: TERM cannot force a TERM-ignoring or uninterruptible child to exit.
Such a case returns bounded cleanup failure; it never claims success/escalates.
Host timeout/close is NOT a target HUP/TERM cleanup mechanism. Independent target
timer is separate; frozen host outcome remains unknown after timeout even if a
later modeled target cleanup was observed. Scheduling, blocked kernel I/O,
SIGKILL or power loss prevent universal wall-time/final-record guarantees. Old
kernel lacks pidfd; immediate identity check has a residual check/signal race.
These limitations require coordinator review, not a human bench operation.

OFFLINE COMMANDS
 hc exec --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/ui001/invoke.py --phase capability
 hc exec --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/ui001/prepare.py --out experiments/ui001/prepared/NEW_UI
 hc exec --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/ui001/invoke.py --phase ui --prepared experiments/ui001/prepared/NEW_UI
 hc run --bg --name ui001-final-tests --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/ui001/run_tests.py
 hc wait ui001-final-tests
Tests preserve exact source bytes BEFORE execution under test-evidence/.../source/.
No installs. Fake Linux proc, accelerated local sleeps, finite fake executable,
and independent local timeout shim are explicitly models, not target evidence.

FUTURE OPERATOR STEPS — ONLY AFTER t6 APPROVES EXACT HASH PROFILE
1. Confirm t14 sole ownership and no other UART/camera helpers. Source hashes
   must match freeze.json and frozen harness30 profile. Re-enumeration, flock,
   passive prompt guard, root+firmware and actual completion remain runner duties.
2. t6 may authorize exactly ONE bounded sleep4 probe (NO native UI):
 hc run --bg --name ui001-cap --parent t14 --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/ui001/invoke.py --phase capability --live --bundle runs/NEW_CAP --owner t14
 hc wait ui001-cap
 hc read ui001-cap --lines 40
   Need completed core command exit0+END+prompt, closed port, exact sleep4
   identity/start/parent/cmdline, matching TERM_ID, one TERM rc0, actual wait143,
   ready1 and term_exit_verified. invoke validates output size/hash against
   its immutable bundle. Failure/timeout stops here; no automatic retry/probe.
3. Await t6's SEPARATE live-UI decision. Prepare fresh NEW_UI unique run ID,
   review command.sh/plan.json and raw wire bounds; do not reuse review IDs.
4. BEFORE camera: capture existing USB webcam alone, inspect fresh original
   image for known prior UI and no unexplained modal. Stop if framing cannot
   verify title/text/removal. No physical camera adjustment/human dismissal.
 hc run --bg --name ui001-before --parent t14 --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B scripts/bench.py camera --device 'USB Camera VID:1133 PID:2085'
 hc wait ui001-before
   Record exact image path/SHA256, capture metadata/return and visible state.
5. After approved preflight, launch foreground watchdog with UART held:
 hc run --bg --name ui001-active --parent t14 --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/ui001/invoke.py --phase ui --prepared experiments/ui001/prepared/NEW_UI --capability-bundle runs/NEW_CAP --live --bundle runs/NEW_UI_UART --owner t14
   Start DURING camera once, promptly about3-5s after UART launch; same camera
   command with name ui001-during. Camera helpers serialized, no microphone.
   Need actual capture timestamp while dialog visible and <=30s after target
   SPAWN. Use raw UART event timestamps to align afterward, not CMU wall clock.
   Camera worst-case enumeration/capture may miss that window; preserve failure,
   allow watchdog cleanup to finish, and mark visible acceptance unavailable.
6. Wait/read ui001-active to actual completion (~43s; independent TERM47s; host60s).
   invoke requires one READY and valid RESULT/WAIT for lifecycle validation;
   it always says visible_pass=false pending separate inspected camera evidence.
   Capture AFTER with name ui001-after only after during helper and UART task
   finish. Need dialog gone by50s where observable and prior UI visible by90s.
   If capture timing misses a deadline, report that limit rather than infer.
7. Fresh postflight identity/version with new bundle, after known completed END:
 hc run --bg --name ui001-post --parent t14 --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B scripts/cmu-session.py --live --action identify --solicit-prompt --deadline 10 --bundle runs/NEW_UI_POST --owner t14
8. Save originals, image interpretation, exact argv/cmdline/start/PID, statuses,
   bounds, raw streams, source hashes, before/during/after image SHA256 and
   cleanup. Close/reap only task-owned Mac helpers after durable save. No schedule.

PASS / FAILURE
First live modal pass requires correct fresh root/55.00.750B pre/post, unique
READY, legible run title and text during, intended watchdog-expired owned TERM,
verified actual child exit+cleanup, wrapper0 and nonce END0+new prompt, no target
writes/persistent change, no unexpected UI left, and prior UI visible afterward.
Lifecycle-cleaned is distinct from visible UI acceptance; camera evidence cannot
be supplied by old images, a launch, command echo or subprocess exit alone.
Unknown identity, mismatch, ignored TERM, missing frame/READY, early child failure,
missing camera window or host timeout is failed/unknown, never automatic rerun.
There is no safe automatic cleanup of an identity-mismatched process. Save exact
owned identity/evidence for t6; no broad kill or request for manual bench help.

PROVENANCE GAP / PRESERVATION
Initial6/8-test drafts passed their original insufficient tests; t13 reproduced
startup leakage and other blockers. Their original template/probe/prepare/invoke/
test source bytes were not snapshotted before overwrite. Exact initial rendered
command+plan survive prepared/review-20261112/, and original source hashes,
6/8-test logs and review remain. This is PARTIAL retention, not a recoverable
original source revision. No originals were reconstructed. Current final tests
preserve all exact source bytes plus frozen harness/test dependencies. freeze.json
links local notes/capability/launch/cleanup sources with hashes and retrieval date.
