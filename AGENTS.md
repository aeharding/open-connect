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
