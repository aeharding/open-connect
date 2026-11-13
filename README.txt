Mazda Open Connect

Open Connect is an open-source project to improve Mazda Connect reliability and
responsiveness while preserving the OEM feel. This repository includes feature
experiments, reverse-engineering findings and the development bench tools.

Latest feature: native disclaimer bypass with renderer-completed intro cleanup.
The recorded black startup gap is gone; a brief dim fade remains. Both-file undo
and restored-stock boot passed. See notes/native-intro-handoff-result.txt; current
installed state is in notes/afk-session-status.txt. Exact firmware55 bench work.

Progress dashboard: https://chatgpt.com/space/page_72594960d3f08191911f2944d96c7eee
Portable source: dashboard/index.html (snapshot data: dashboard/status.json).


The primary agent operates the development bench directly through Herdr hc.
The user performs no manual bench or UI steps. Read STEERING.md, then AGENTS.md.
Current status: notes/status.txt and notes/afk-session-status.txt.
Research: research/index.txt (human entry) and research/index.tsv (catalog).
Latest frontend result: notes/browser-navigation-finding.txt (failed browser return,
separate recovery and stock heartbeat source; native extension lead).
Firmware shipping-window checklist: notes/firmware-readiness.txt (exact planned
v73 package/region/path open; stock55 unchanged).
Native status overlay: notes/native-status-overlay-observation.txt (visible/owned
cleanup/home+root55 PASS; crowded body retained as limitation).
Plan: notes/interim-plan.txt; source evidence remains in ignored local storage.

VERIFIED BASELINE
Mac mini M2 Pro, macOS26.5.2/arm64; Python3.13.7, pySerial3.5, FFmpeg7.1.1.
CMU55.00.750B, North America/cmu150_NA, Linux3.0.35 ARMv7l, BusyBox1.19.2.
UART0403:6001/A9048JM0,115200 8N1, all flow control off, RTS/DTR inactive.
Re-enumerate the actual adapter/path before opening; last path is
/dev/cu.usbserial-A9048JM0. User/root logins and native UI control were observed.
Preserve USB and SD. AUX is not required.

ACTIVE HOST TOOLS
cmu_bench/session.py + files.py and scripts/cmu-session.py are the reviewed runner.
They provide a descriptor-held lock, fresh root/firmware checks, lossless RX/TX,
nonce-framed completion with actual exit status, finite deadlines, and verified
small-file capture. Default invocation is a dry run and does not enumerate/open
a port, transmit, or create files.

Examples below run through Herdr from this folder:
  hc exec --cwd /Users/aeharding/open-connect .venv/bin/python -B scripts/cmu-session.py --action command --command id
  hc exec --cwd /Users/aeharding/open-connect .venv/bin/python -B scripts/cmu-session.py --action export --path /etc/version --checksum md5 --encoder base64
  hc run --bg --name cmu-tests --cwd /Users/aeharding/open-connect .venv/bin/python -B tests/run_offline.py
  hc wait cmu-tests
  hc read cmu-tests --lines 80

Live tasks belong ONLY to the assigned hardware operator. The operator selects
a new private runs/ bundle, explicit --live, actual --owner, an appropriate
--deadline (SPACE before the value), and --solicit-prompt only after establishing
a known idle shell. Read notes/tooling-development-result.txt and
examples/operator-ready-exception-fix.json for the tested profile and templates.
No automatic login, recovery control keys, reset/BREAK, or uncertain-action retry.
Exit0 is success,1 failed/preflight/file rejection,2 unknown delivery/execution,
3 a completed remote command with nonzero status. Inspect the manifest.

EXACT SMALL-FILE TRANSFER
Allowlist: /etc/version and /jci/version.ini, regular nonsymlink files <=16KiB.
Fresh source pre/post byte count, MD5 and POSIX cksum must match the decoded host
bytes; the host also records SHA256 for provenance. CMU sha256sum is absent.
MD5/CRC transfer checks do not establish authenticity, atomic snapshots or restore.
BusyBox timeout syntax is '-t SECONDS', not GNU positional seconds.
Every physical command line is capped at600 bytes including wrapping/quoting.
The old console editing cap was observed at1022 input characters. A documented
source-backed recovery cleared one specific unfinished quoted input; it is not
an automatic recovery recipe for arbitrary prompts.

Accepted live captures (fresh root, actual command exit0+prompt, no retries):
  runs/20261112T225632-0600-t14-harness-pilot/etc-version.exact.bin
  runs/20261112T225632-0600-t14-harness-version/jci-version.ini.exact.bin
Sizes31 and13304 bytes; verified metadata and hashes are in each manifest and
notes/exact-file-capture-observation.txt. The old inventory version.ini extraction
remains unchanged as a historical metadata reference with unrelated trailing text.

CAMERA AND LEGACY HELPERS
scripts/bench.py retains device inventory, receive-only logging and webcam still
capture. Camera uses exact currently enumerated USB name, video only, no audio:
  hc exec --cwd /Users/aeharding/open-connect .venv/bin/python scripts/bench.py camera --device 'USB Camera VID:1133 PID:2085'
Capture success needs actual image inspection; framing/glare limit some readings.
scripts/console-command.py is preserved for historical evidence. Its fixed read
window and initial CR do not provide robust command completion or general recovery.
Use the new runner for new live command/file work. Never run it concurrently with
a logger, screen/cu, or another UART owner. The advisory lock does not govern
older tools that do not honor it.

STORAGE AND RESEARCH
Git contains code, instructions, decisions, source/evidence manifests and small
sanitized fixtures. Original logs/,captures/,inventory/,runs/,source snapshots,
backups, credentials and environments remain local/ignored. No remote is configured.
Original evidence stays immutable; new findings cite exact paths and hashes.
A Git commit/local working directory is not a second raw-evidence copy or a
complete device backup/recovery set.

Recent observations:
  notes/afk-baseline-observation.txt — storage/process inventory and input failure
  notes/console-recovery-research.txt — primary-source diagnosis and narrow recovery
  notes/console-recovery-observation.txt — actual recovery and fresh identity
  notes/afk-baseline-followup.txt — modules/interfaces/SSH listener/D-Bus names
  notes/ui001-prerequisites-observation.txt — process/signal capability observations
  notes/tooling-review.txt + notes/tooling-review-resolution.txt — review and fix
Experimental UI001 is under experiments/ui001/. It remains unapproved for live
execution until its lifecycle fixes, exact capability probe, review and evidence
requirements are satisfied. The operator owns software cleanup; no manual dialog
dismissal is assigned to the user.
