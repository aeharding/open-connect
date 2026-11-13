Independent OEM55 disclaimer first pass — HOST ONLY, uninstalled

Question: can the existing startup disclaimer auto-dismiss promptly while all
stock templates, native event routing and GuiFramework heartbeat remain intact?
Scope: installed55.00.750B/cmu150_NA, exact systemApp.js SHA256
985cbcbeb1dedf11b76f61ffa1224e43165f80d8eb9c8d5d853d118d2eec3432 only.
No prior third-party bypass implementation read before this freeze.

Design derived from the acquired OEM file
systemApp.js281-302 maps Disclaimer to Dialog3Tmplt/Dialog3Ctrl, WarningTitle,
DisclaimerText, one Agree button (Global.Yes), displayed and teardown callbacks.
State553-567 supports timer reset, remaining time and interruption/resume.
_displayedDisclaimer1968-1989 disposes the intro video, resets initial time3500ms,
and queues _disclaimerTimedout. Selection1991-2002 sends common Global.Yes.
Timeout2004-2031 sends system Timeout only for current Disclaimer, then uses an
existing3500ms retry. Teardown2033-2045 subtracts elapsed time and cancels timer.
The independent candidate changes only the display-entry assignment3500 ->0.
Keep retry3500: no zero-delay retry storm. Keep native Timeout, not synthetic Agree.
No HTML/CSS, application removal, Navigate, heartbeat or settings changes.
This queues dismissal AFTER the displayed callback. Rendering/flash is possible;
this is not a proven invisible bypass. Native MMUI selection of Disclaimer at
startup and its event/transition latency remain unverified. No startup was run.

Host use (programs through hc)
  hc exec --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/disclaimer/patch.py
  hc run --bg --parent t12 --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/disclaimer/run_checks.py
Default prints a read-only plan. To generate ORIGINAL/CANDIDATE/DIFF/plan artifacts,
pass --output-dir runs/NEW_PRIVATE_DIRECTORY. Existing output directories refused.
No live/device installer is implemented. Full OEM/candidate bytes stay only in
ignored private runs/backups. Track authored logic/tests/hash metadata/docs only.
Tests use the actual private source with independent Node timer/event stubs;
no claim that Node models Opera, rendering, MMUI, complete boot or heartbeat runtime.

Proposed install/rollback procedure — NOT executed or yet authorized
1. Exclusive operator obtains fresh root55 identity; reread target pre/post
   length+MD5+POSIXCRC, verify exact base SHA via host export. Preserve originals
   independently before writes. Current path is on reported read-only relfs.
2. Authorize and separately validate filesystem-write/atomic replacement/access
   recovery procedure before any target write; no remount/install command provided
   by this host prototype. Stage only the hash-bound candidate; expected existing
   metadata0755 uid1018 gid3015 is source listing evidence, recheck at install.
3. Recheck current base immediately before replacement; conflict on any later
   bytes/metadata. Record before/after journal and keep exact original. Replace
   only this one file, preserve ownership/mode, export and verify candidate bytes.
4. A separately authorized startup trial must record Disclaimer behavior, native
   focus/home/heartbeat health and fresh identity; quick/cold paths remain open.
5. Uninstall only when current bytes equal this exact candidate. Restore preserved
   original94058B and metadata, export/check exact original SHA. Unknown/later
   edits are conflicts, never blindly overwritten. Interrupted/unknown write state
   requires readback classification (original/candidate/other), no automatic retry.
6. Actual live rollback, filesystem durability/atomicity and restart/access recovery
   are missing validation; host rollback(candidate, original) proves bytes only.

This prototype chooses one bench candidate, not an all-firmware policy, manifest
standard, public release or disclaimer-behavior recommendation for road use.
Third-party retrospective comparison may start only AFTER freeze.json hashes exist.
