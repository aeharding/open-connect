Native BENCH STATUS overlay (dry-run by default)
Review: hc exec --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/status-overlay/overlay.py --seconds 12
Live operator: hc run --bg --parent t14 --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/status-overlay/overlay.py --seconds 12 --live --bundle runs/NEW_STATUS --owner t14
Fresh run ID generated automatically; --run-id can pin an explicitly reviewed run.
Default single-line body: 55.00.750B | UART root | 2 files (32 ASCII characters).
Live trial title/ID was legible; newline bytes reached argv intact but body looked
crowded on one line, so only the future default was shortened. No repeat was run.
--seconds integer10..15; optional --title<=24 ASCII, --text<=160 ASCII/3 lines.
Uses original UI001 template and paced core unchanged: exact owned PID/start/PPID/
fullNUL argv, TERM only and verified wait/reap; stock frontend stays loaded.
No Navigate, Refresh, Terminate, heartbeat calls or target files/settings.
Capture appearance promptly and removal on completion. Stop on uncertainty; no retry.
Current default/hash profile: profile.json. Original live profile: ready.json.
Focused4-test lifecycle snapshots and1-test default check: checks/.
Remote TERM timeout seconds+7;3s grace; host deadline35. Known stock timer/PID limits
remain those of reviewed lifecycle. No new capability probe or coordinator gate.
