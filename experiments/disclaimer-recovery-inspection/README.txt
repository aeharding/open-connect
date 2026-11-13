STANDALONE RETAINED-JOURNAL INSPECTOR — default VERIFY

Completed: ONE fresh-process live VERIFY of the restored original on stock55.
It parsed the retained WARM1 journal as DATA, verified O/C images and metadata,
recognized current source inode9457 rather than historical initial1606, and
reported disabled/no-pending/noop/writes0. Physical rootRO and core completion
were verified. No warm payload repeat, mount/sync or source/journal write.
Delivery's separately authorized DATA staging created an owned tmpfs script only.

Prepare a review-only standalone VERIFY (does not open UART):
  hc exec --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/disclaimer-recovery-inspection/prepare.py --out experiments/disclaimer-recovery-inspection/NEW_VERIFY
Default mode is VERIFY. Long programs are delivered as verified base64 DATA to
fresh owned root0700 tmpfs/script0600, then a short canonical/metadata/hash guard
runs /bin/sh with stdin/dev/null through the existing paced/fresh-root55 runner.
Do not paste long executable UART text. No retry or additional live run is queued.
Exact accepted payload/checksums and bounds are in the saved ready-VERIFY/plan.json.

Strict checks
- Existing WARM1 exact12-field/order/schema/nonce/state/intent/goal; canonical IDs,
  one bounded LF record, exact byte/hash/count checks. Never source/eval journal.
- Canonical/nonlink parents, retained root0700 directory identity, regular single-
  link journal0600root and original/candidate0755/1018:3015 with exact size/MD5/CRC,
  recorded identities and mtimes. Directory nlink5 was observed, not assumed2.
- Current O must match a recorded original identity (restored ostage or initial),
  frozen bytes, metadata and direct cmp. VERIFY accepts only disabled/no-pending
  completed-O state; C/OTHER/pending/inconsistency refuses and preserves everything.
- Journal identity/hash rechecked before END; single-writer/TOCTOU limits remain.
Firmware/root55/NA gate is the unchanged core Session preflight plus innerUID0.

Future-review capability ONLY
--mode RESTORE_ORIGINAL produces a SEPARATE body, not included in VERIFY and not
staged/executed on CMU. Host copies/fakes exercise known C+valid intent -> stored O,
metadata/intent checks, disabled journal commit and subsequent fresh VERIFY.
It requires an already-verified RW root; it does NOT remount, sync or own RO return.
A separately reviewed outer write/flush/RO/failure contract would be needed before
any target use. This is not a ready live recovery writer or selected product policy.
Unknown/conflicting bytes, metadata, images or intent refuse. Current live C/restore
has NO authority. Frozen feature/core/host engine/warm package are unchanged.

Evidence and precise limits: result.txt. Six focused host checks include real bytes/
modes/inodes with logical UID/GID/device fakes, not BusyBox/RelFS equivalence. C/OTHER
refusals and mutation are HOST-tested only, not live-injected. No startup/reboot,
SIGKILL/power-loss/durability/USB/all-firmware/full metadata recovery claim.
