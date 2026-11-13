Mazda CMU bench: Mac preparation

Working directory: /Users/aeharding/mazda-cmu-bench
Python environment: .venv (Python 3.13.7, pySerial 3.5)
Camera tool: existing Homebrew FFmpeg 7.1.1 via AVFoundation

Scope: retain USB and SD navigation; AUX is not needed. The user handles wiring.
The user reported UART wiring complete; two-way UART and both ordinary and root
shell access were verified on November 12. Installed firmware: 55.00.750B, NA.
No relay control or firmware changes are implemented.

Run these commands from this directory; activation is optional:

  .venv/bin/python scripts/bench.py inventory
  .venv/bin/python -m serial.tools.list_ports -v
  .venv/bin/python scripts/bench.py serial
  .venv/bin/python scripts/bench.py camera

Inventory and serial configuration commands do not open a serial port.
The serial command without --open records a plan with a null port by default.

Capture a still from the currently detected USB webcam, with no microphone:

  .venv/bin/python scripts/bench.py camera --device 'USB Camera VID:1133 PID:2085'

The camera command re-enumerates devices and resolves the exact name on each run.
It uses 1280x720, 5 fps, UYVY input, and a two-second exposure warmup.
These mode settings follow the webcam formats observed on this Mac.
macOS camera permission was confirmed authorized at 21:09 CST on November 12.
The USB webcam returned and 1280x720 JPEGs have been captured and inspected.
At 21:38 it confirmed the Mac-launched "Mac Mini connected" information dialog.
Framing changed during the session; inspect each frame before reading fine text.
A timeout or device listing is not a frame.
Inspect a successful JPEG before marking display framing usable.
Camera subprocesses time out after 25 seconds and capture no audio.

AFTER the user verifies the physical UART wiring and the USB adapter is listed:

  .venv/bin/python scripts/bench.py serial --port "$CMU_SERIAL_PORT" --open --seconds 60

Set CMU_SERIAL_PORT to the actual USB serial path from a fresh inventory.
The FTDI is /dev/cu.usbserial-A9048JM0, VID:PID 0403:6001, serial A9048JM0.
At 21:31 a 60-second passive session received 24233 bytes of readable CMU logs.
At 21:32 one Enter produced "cmu login:"; user and root logins then succeeded.
No example port is preconfigured. The script rejects an absent/non-USB port.
This command opens the selected port; all preceding serial examples do not.
It receives only, at 115200/8/N/1, timeout 0.5 seconds, all flow control disabled,
and requests RTS/DTR inactive. Handshake/reset pins remain unconnected.
It does not send a newline, login, break, command, or any other UART data.
Logs are a dated raw .bin, timestamped hex .jsonl, and session metadata .json.
Stop with Ctrl-C or let the requested duration finish.
Receiving bytes does not establish readable output or an interactive console.

Directories:
  inventory/  Device snapshots, camera lists, and unopened serial plans
  logs/       Installation, diagnostics, future UART sessions
  captures/   Successful camera JPEGs, including a visible UART-controlled dialog
  notes/      Observed status and unresolved hardware requirements
  scripts/    Reusable device inventory, logging, and still-capture helper

Software verification used only a temporary pseudo-terminal. It confirmed the
configuration command does not open a port, raw binary input survives logging,
timestamped hex reconstructs the same bytes, and no data is transmitted.
Simulation files were removed with the temporary directory; this is not a CMU test.

An explicit command can now be sent to the existing authenticated UART shell:

  .venv/bin/python scripts/console-command.py --command 'id' --label identity-check

This helper selects the observed FTDI by VID/PID and serial number, requires a
shell prompt, sends the specified command, records RX/TX, and closes the Mac port.
It does not perform login automatically. The CMU shell session can persist across
Mac port closures. The last verified shell is root; confirm with id when resuming.
The Herdr operator cleared the owned information dialog and verified the home
menu through a fresh webcam image. No user dismissal is pending.
The proposed development/research work is in notes/interim-plan.txt; all agent
coordination and control use Herdr, with one assigned UART owner.
No firmware files, account permissions, power wiring, or relay state were changed.
USB Ethernet through the hub is planned for later; SSH and transfers are untested.

Sources checked for software behavior:
  https://pyserial.readthedocs.io/en/latest/tools.html
  https://pyserial.readthedocs.io/en/latest/pyserial_api.html
  https://ffmpeg.org/ffmpeg-devices.html#avfoundation
  https://developer.apple.com/documentation/avfoundation/avcapturedevice/authorizationstatus(for:)

Current observations and next steps: notes/status.txt

Research entry point (derived; updated November 12, 2026):
  research/index.txt          Human entry point: facts, limits, sources and gaps
  research/index.tsv          Canonical searchable catalog with evidence IDs/hashes
  research/context/SUMMARY.txt  Derived handoff and unresolved physical conflicts
  research/SCHEMA.txt         Record formats and safe update rules
  notes/research-preservation-result.txt  Preservation checks and local commit

The current bench is agent-operated; no human button press, dismissal, wiring,
media insertion or camera movement is available. Earlier manual-operation wording
above is historical. The owned test dialog was cleared and visually confirmed
by the prior operator (research F012/D002); no manual OK is pending.
Keep firmware55.00.750B and existing power/accounts/settings/USB/SD/networking.
Raw logs, inventory, captures, runs, copied backups and source snapshots stay local
and outside Git; tracked manifests retain original paths, hashes and provenance.
Local Git is not an independent second copy, complete CMU backup or recovery set.
