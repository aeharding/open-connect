# Mazda CMU bench agent instructions

This is an agent-operated development and research bench. The user will not touch
the bench, press buttons, dismiss dialogs, reposition the camera, or perform wiring
for agent work. Software operation and cleanup belong to the agents. Record an
unavailable physical operation as a dependency; do not assign it to the user.

## Coordination

A retrospective, status question or workflow discussion does not cancel active
authorized work. Address it, then resume unless the user explicitly pauses, stops
or replaces the task.

Working style: a hackathon with trusted teammates. Give agents complete outcome
ownership and room to choose routine implementation details. Coordinate dependencies,
resolve blockers and integrate results; do not act as a per-command approval gate.
Prefer the smallest working demo and fast feedback. Keep documentation concise and
batch it after useful results. Pause for genuinely new risk or an unexpected device
state; retain one UART owner and responsibility for software cleanup.

- The point agent coordinates. Delegate scoped execution and research through
  Herdr's `hc` API/CLI exclusively; do not use native agent-spawn/collaboration
  tools. Run program/file operations through Herdr too.
- Consult `hc --skill` and `hc <command> --help` for exact API/CLI behavior.
- Launch agents interactively with `hc run --bg`, an exact name/scope, and an
  explicit verified parent when caller identity is ambiguous. Codex agents use
  `--no-daemon` so their commands stay in their Herdr context.
- Only the coordinator assigns new agents or additional delegation. Workers
  report results and artifact paths with `hc send <coordinator>`.
- Give one bench operator exclusive UART ownership. Other agents use saved
  evidence and request live work from that owner. Never run a passive logger,
  command helper, terminal program, or second operator on the UART concurrently.
- Assign complete bounded work packages with clear stop conditions. Do not
  repeatedly seek coordinator authorization for routine steps already within
  that task. Pin reviewed code once and avoid full-source audits per command.
- Prioritize a compact live result after relevant tests and one scoped review;
  do batch indexing/documentation afterward. Keep originals, including failures.
- Keep camera access serialized. Use `hc wait` for running Herdr programs/agents.
  Clean up only helper terminals created by the current task after results are saved.

## Bench development priority

The user explicitly wants the best OEM-feeling fix, including native changes when
appropriate. This dedicated test bench exists for experimentation; do not apply
production-car risk aversion as a reason to prefer a timer tweak or visual mask.
Use backups, independent undo and repeatable experiments to support the correct
design. Trusted owners choose routine details and deliver working outcomes.
The current disclaimer goal is to bypass its native startup detour while retaining
OEM initialization, cleanup, focus and resume choices. The measured timer change is
historical learning, not the completed feature. CSS masking and timer tuning are
parked. Current native prototype ownership is t12, focused semantics t13, sole
hardware execution t14. No additional user approval is needed for routine work in
an assigned experiment; bring a concrete new boundary to the coordinator.

The native HOST feature is frozen and its one semantic review completed.
The current complete native bench outcome is assigned to t14 under
notes/native-disclaimer-complete-handoff.txt: after relevant runtime checks and
profile freeze, candidate apply/startup, independent undo and original-confirmation
startup proceed without another per-step permission gate. Preserve actual request
counts and current loaded-vs-disk state; historical JS profiles are not reusable.

## Active native recovery exception

The first native publication wrote exact C but its pairedRO remount returned
EBUSY255; physical root remains RW. No candidate reboot was requested.
This supersedes the historical stockRO baseline below. Follow the complete known
original recovery in notes/native-apply-recovery-handoff.txt: t14 owns explicit
RW-entry known-state undo and one truthful original-only recovery boot if needed,
with exact original/mapping/physicalRO/VERIFY/home closure. Do not boot candidate,
repeat the failed install, assume defaultRO recovery accepts RW, or treat disk
restore as unloading the existing mapped module. Current evidence and retained
identities are at the TOP of notes/afk-session-status.txt.

## Verified reference state

- CMU firmware: 55.00.750B, North America (`cmu150_NA`), Linux 3.0.35 ARMv7l.
  `JCI_SW_NEXT_VER` is separate metadata, not the installed version.
- FTDI FT232R: VID:PID 0403:6001, serial A9048JM0. Last observed port:
  /dev/cu.usbserial-A9048JM0. Re-enumerate identity before acquiring it.
- UART: 115200/8/N/1; all flow control disabled; RTS/DTR requested inactive.
- User and direct root logins were verified. A shell may persist after Mac port
  closure; identify the actual state and uid before sending task commands.
- USB webcam: VID:PID 046d:0825, serial 1AD54210. Herdr capture was verified.
- Preserve USB and SD navigation. AUX is not required.
- The owned test dialog PID18090 was verified, terminated, and visually confirmed
  gone. It is historical evidence, never a PID to reuse for future cleanup.

## Execution and evidence

- Follow the assigned task. The interim task is planning, preservation, tooling,
  and bounded reversible experiments; keep firmware55 as its reference baseline.
- Routine software cleanup within an authorized task needs no repeated user
  confirmation. Agents dismiss their own dialogs and release their resources.
- Match owned-process identity before termination. Never kill all dialog processes.
  Use bounded command/capture lifetimes and preserve failures as well as successes.
- A command echo, shell-shaped prompt, fixed receive window, or launched process
  does not establish success. Record fresh identity, command completion/exit
  status, actual output, and visible evidence where appropriate.
- Distinguish physical commander operation from synthetic input, USB enumeration
  from usable media, and received logs from observed boot or recovery.
- The existing extracted inventory/20261112T2135-cmu-version.ini is a metadata
  reference containing unrelated trailing console output, not a byte-exact backup.
  Preserve it unchanged. Verify new file captures using remote/host size and
  checksum before treating them as backups.
- Preserve original raw evidence. Keep credentials/private raw captures out of
  versioned fixtures; use provenance-linked sanitized derivatives.
- Stage long programs that can alter installed CMU files as data in a fresh
  root-owned tmpfs directory. Verify target byte count, MD5/POSIX CRC, canonical
  routes and file/directory identity before a short guarded entry executes them.
  Keep the staged body and entry linked to the reviewed source/test profile.
- This BusyBox grep lacks -x. Reuse the verified Session identity parser for
  exact root/firmware/flavor checks and use capabilities observed on this binary.
- The first warm systemApp.js roundtrip restored AS-FOUND bytes,0755,UID1018,
  GID3015 and mtime1433953097, with new inode9457 (historical1606). Root physical
  RelFS was verified RO afterward. Historical one-shot payloads retain old inode
  guards; record fresh identities for new approved work.
- The first modified startup trial then restored current ORIGINAL source identity
  64785:9456:1433953097:94058:755:1018:3015:1, exact AS-FOUND hashes and checked
  metadata, root55/home and physical RO. Inode9457 is now historical. Current
  retained startup recovery is cmu-bench-startup-388ae4f695d2b19f0945f2d8428fca7e
  under data_persist (dir57/O60/C61/code63), disabled/none. Do not reuse old
  one-shot packages or infer identity from inode alone. See
  notes/modified-disclaimer-startup-observation.txt for the complete outcome.
- One modified warm boot shortened the still-visible warning to0.402-1.005s
  from4.223-4.625s stock; this is not a complete visual bypass or USB release.
  The original observer UNKNOWN from a logger-prefixed META field is preserved;
  saved complete fields and fresh persistent VERIFY reconciled the result.
  Independent undo restored disk O, but no new O startup was performed; the
  running frontend was loaded from C. Corrected future tooling must preserve
  strict field/identity checks and the executed source/profile history.
- A separate restored-stock confirmation then booted ORIGINAL O9456 unchanged:
  automated observer/all6coreops passed, freshroot55/physicalRO/newbootID/lower
  uptime and retainedreadonlyVERIFY before/after O/disablednone/writes0. The
  running frontend is now original, not cachedC. Stock-length warning returned
  3.821-4.425s (overlaps earlier4.223-4.625s; no exact equality claim). See
  notes/restored-stock-startup-observation.txt. That one-boot profile is spent.
- Every experiment records its question, applicable hardware/firmware, exact
  commands/code revision, before/after evidence, result, interpretation and cleanup.
- No recurring/background schedule is implied by the development plan.

## Context and durable records

Start with README.txt, notes/afk-session-status.txt (current), notes/status.txt,
and notes/interim-plan.txt. Prefer scripts/cmu-session.py for new live commands;
the legacy fixed-window helper remains historical. The current runner limits
physical input lines to600 bytes and has validated exact-file exports. Default TX
is paced64-byte chunks with20ms RX gaps; one7KiB calibration passed. The old
UI driver pins require explicit integration before new live UI work. BusyBox
requires timeout -t SECONDS and provides MD5/cksum but no sha256sum. The specialized
operator, baseline, and development/research plans in notes/ provide supporting detail.
As implementation proceeds, keep a searchable research index linking sources,
findings, hypotheses, decisions and immutable run evidence. Source records include
exact URL/reference, retrieval date, hash/revision, relevant page/section, scope,
conflicts and superseded status. Update the index and handoff at the end of each task.

## User progress dashboard

The user's first sync point is the private Page recorded in dashboard/publication.json.
Keep dashboard/status.json, its embedded HTML data and the remote snapshot aligned
after meaningful milestones, with an honest timestamp. Batch this after useful
results; do not gate bench progress on publishing. No live telemetry or new schedule
is implied. Keep raw logs and private identifiers local. Read the Pages write-page
skill for cloud updates and preserve the Page URL.

## Frontend lifecycle lesson

The stock GuiFramework schedules native guiManager.javascriptHeartbeat every1s.
Whole-page data navigation rendered but lost that producer, triggered a heartbeat
fault/Opera exit and failed its timed return; root55/home were separately restored.
Current experiments keep the stock document/framework loaded and use owned native
overlays. Do not repeat that navigation branch or spoof/disable its heartbeat.
USBhub/Ethernet+USBACCrelay remain in shipping; the user-planned v73 upgrade is
deferred. Preserve55 while doing useful software/tooling/preservation work.

## First product feature

The user selected startup disclaimer bypass as the first real feature. Derive
the first implementation from actual OEM55 sources only; freeze independent
source/design/patch/tests before consulting Miatify/Miatafy or other bypass code.
Comparison afterward must not rewrite the independent record. Keep full OEM
originals private/ignored; track our logic, synthetic tests, hashes and findings.
No CMU modification is implied by a host-only prototype. Preserve firmware/base
hash guard, exact original rollback and the stock frontend heartbeat lifecycle.
Product goals and open choices are in notes/product-direction.txt.
