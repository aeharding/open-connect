ISOLATED CMU COPY TRANSACTION EXPERIMENT
Firmware55.00.750B/cmu150_NA, November13 2026.

This prototype tests one recovery window using full-size file copies on writable
data_persist. It never installs the feature or writes the real /jci source.
A single data-only control file holds recorded state and pending intent.

Phase STOP:
- Guard the actual source, writable volume, new nonce directory and copied images.
- Construct the already-frozen disclaimer candidate; record enabled, then DISABLE.
- Restore the original COPY, verify it, leave intent pending and deliberately exit73.
Phase COMPLETE:
- Require saved evidence of the exact intended phase1/root55/END73+normal prompt.
- Recheck directory, journal, stored images and restored active file identity.
- Commit disabled/no-pending by replacing only the control file; never rewrite
  the already-original active image. Verify unchanged identity and clean owned files.

prepare.py generates requests without opening UART:
  .venv/bin/python -B experiments/target-copy-transaction/prepare.py \
    --phase stop --nonce <fresh-32-lowercase-hex> --out <new-prepared-directory>
  .venv/bin/python -B experiments/target-copy-transaction/prepare.py \
    --phase complete --phase1-bundle <verified-stop-bundle> \
    --phase1-prepared <stop-prepared-directory> --out <new-prepared-directory>

The experiment borrows its checked guards and full-copy recipe from the private
passed command runs/20261113T034954-0600-t14-full-file-copy/command.sh, bound to
that run's plan hash. This bench-local reference must exist; it is not a portable
USB installer dependency or a distributed OEM source image.
The sole bench operator uses the existing paced runner and unique run bundles.
UNKNOWN, wrong exit, conflict or malformed evidence refuses the second phase.
No automatic recovery/retry or journal execution through source/eval.

Focused offline check command (no UART):
  .venv/bin/python -B experiments/target-copy-transaction/check.py
Saved four-check authority:
  checks/20261113T100248.158737Z/manifest.json
Host tests use a logical UID/GID/device shim; they do not prove BusyBox equivalence.
Original test/source snapshots stay local; the manifest identifies exact sources.
The live two-phase result is recorded separately in result.txt.

Limits: intentional process exit on isolated copies, normal writable-volume runtime.
No root-RelFS install, sync/power-loss/crash recovery, startup/no-flash, factory
authenticity, USB architecture or product recovery-policy claim. The independent
feature freeze and shared host Engine.recover/complete_uninstall are unchanged.
