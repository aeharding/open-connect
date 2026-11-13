# Bench profile result — 2026-11-13

**Setup → repeat setup → teardown → status → setup passed on the CMU.**
Final profile is intentionally on: silent Entertainment override enabled and owned.
Fresh root55/NA, physical root RO guard and completed commands were recorded;
each CLI invocation closed its UART port. No camera, file patch, reboot or startup
hook was used. Existing Snap JS/product state was unchanged.

Current public surface: `scripts/oc bench setup|status|teardown`.
It manages the whole current profile; individual helper activation is internal.

## Evidence and checks

Private evidence (not redistributed):
- `runs/bench-profile/lifecycle-result.json` and the five referenced bundles:
  live-setup, live-setup-repeat, live-teardown, live-after-teardown, live-ready.
- `runs/bench-profile/host-20261113T220207Z/manifest.json`: 11 focused checks passed.
  Earlier malformed-reply handling failure is retained in host-20261113T220005Z.
- `runs/bench-profile/dryrun-fix-20261113T220349Z/manifest.json`: two focused CLI
  checks passed after clarifying preview output.
- `runs/bench-profile/owner-fix-20261113T220515Z/manifest.json`: two focused CLI
  checks passed after making the owner label automatic.
The last changes affect CLI output/default labeling, not the checked audio logic.

## Command-only agent exercise

Fresh ephemeral agents ran outside the project with only the exact command:
- Original dry-run: agent incorrectly described setup/state-file creation.
  Actual result had no port/file effect. Output was changed to explicitly say
  dry_run_not_executed, executed=false, state_written=false.
- Fresh corrected dry-run: accurately reported no setup or state write (~13s).
- First live status attempt: refused before opening a device because the launcher
  did not supply the optional owner environment. This exposed CLI friction;
  owner now has an automatic process-label fallback.
- Corrected live status: fresh agent accurately reported inactive/audio-disabled
  state (~14s). Primary checked the actual manifest/root identity/completion and
  closed port before performing mutations.

Agent wall time is not CMU command latency. Agent exit 0 alone did not establish
command success; original failures and mistaken narration are preserved.
Private prompt/result/transcript records: runs/bench-profile/cold-*/.

## Limits

No persistent startup or SSH transport yet. Reboot/service replacement invalidates
the old runtime binding. Existing TAU experiment established visible navigation;
this lifecycle test verified API/native state, not sound or new visual behavior.
Teardown restores only the owned runtime override, not all user settings.
