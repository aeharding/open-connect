# Build a Mazda Connect test bench

Start here to connect **power, a display and UART** to a first-generation CMU.
Our development firmware is **55.00.750B North America**.
Once the hardware works, use [CLI operations](cli.md).

## Parts

- First-generation CMU, matching display, display data cable and power harnesses.
  Buy mating pigtails with the unit if possible; bare modules need connector terminals.
- Regulated 12 V DC supply, fused power wiring and an ACC switch.
- USB-to-TTL UART adapter, with documented 3.3 V signal levels, and three signal wires.
  The [MazdaTweaks serial guide](https://mazdatweaks.com/serial/) uses a CP2102 adapter.
- Computer with USB and Python 3; a multimeter for checking power and ground.

A commander, webcam and network adapter can come later. No TAU or speakers are
needed for our silent Entertainment UI tests.

## 1. Wire power and the display

Disconnect power while wiring. Use the pin labels in the
[connector drawing](https://mzdonline.wordpress.com/2018/07/13/power-up-junkyard-cmu/#:~:text=Wiring%20diagram);
the mating harness view is mirrored relative to the CMU socket. Do not identify
pins by wire color alone.

| CMU power connector | Connect to |
| --- | --- |
| **2R — B+** | Fused +12 V |
| **2Q — ACC** | +12 V through the ACC switch |
| **2C / 2D / 2L — ground** | Supply negative, following the matching harness |

Keep B+ powered when switching ACC off. Give the display its matching power
connection **as well as** the CMU-to-display data cable; the data connection alone
is not the complete display wiring.

~~~text
12 V supply + ── fuse ──┬────────── CMU 2R (B+)
                       ├── switch ─ CMU 2Q (ACC)
                       └────────── matching display power harness

Supply negative ────────────────── CMU / display ground
                                         │
Computer ── USB UART adapter ── GND ──────┘
                     RX ◀───────── CMU 2S (TX)
                     TX ─────────▶ CMU 2T (RX)

CMU ───────── matching display data cable ───────── Display
~~~

This is a logical wiring diagram, not a connector-face drawing. The published
[bench build](https://mzdonline.wordpress.com/2018/07/13/power-up-junkyard-cmu/)
includes connector photographs and display-power details; it used a 12 V, 10 A
supply. That is a supply rating, not a claim that the CMU draws 10 A.
Use the wiring diagram for your actual CMU/display variant before applying power.
The [hardware reference](https://github.com/silverchris/mazda-cmu-documentation/blob/gh-pages/hardware.md#connectors)
also lists the connector signals.

## 2. Connect UART: three wires

| USB UART adapter | CMU |
| --- | --- |
| **RX / RXD** | **2S — CMU TX** |
| **TX / TXD** | **2T — CMU RX** |
| **GND** | Common CMU/supply ground |

TX and RX cross: each transmitter connects to the other device's receiver.
Leave the adapter's **VCC/5V/3V3 power lead disconnected**, along with RTS, CTS and
DTR. The 12 V supply powers the CMU; USB powers the adapter. Keep 12 V away from
the UART pins.

Use the [UART connector photos](https://mazdatweaks.com/serial/) to locate 2S/2T.
Use a TTL UART adapter, not a conventional RS-232 cable. Check the adapter's
signal-voltage specification; a power-output label alone does not establish it.

Our bench uses an FTDI FT232R adapter. CP2102 is another documented wiring option;
Open Connect's current automated runner is pinned to our particular FTDI device.
A different adapter can be used with a serial terminal, but needs runner
configuration before using the automated CLI.

## 3. Read the first boot

From the repository on the host computer:

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m serial.tools.list_ports -v
~~~

Find the adapter's port. On our Mac it is /dev/cu.usbserial-A9048JM0; yours
will differ. Open it with **115200 baud, 8 data bits, no parity, 1 stop bit,
no flow control**:

~~~sh
.venv/bin/python -m serial.tools.miniterm --rts 0 --dtr 0 --eol CR /dev/cu.usbserial-A9048JM0 115200
~~~

Turn on power and ACC. You should see readable boot logs and the display boot.
Let startup finish without typing into the bootloader. Exit miniterm with
**Ctrl+]** before running another tool; only one program should own UART.

Receiving logs proves the receive connection. Interactive shell access is a
separate firmware-dependent step: wiring UART does not automatically unlock every
firmware. The automated CLI currently expects an established idle root shell on
our exact supported firmware; it does not perform login or unlock the CMU.

## If it does not work

| Symptom | First checks |
| --- | --- |
| No display or boot logs | B+, ACC, ground and supply output |
| Boot logs but black display | Display power and matching data cable |
| No serial output but display boots | Correct port, adapter RX to 2S, common ground |
| Garbled serial output | 115200/8N1, signal levels and ground |
| Logs work but typing does not | Adapter TX to 2T; firmware/login state |
| Port busy | Close the other serial terminal or Open Connect operation |

## Next

- [Operate the bench with the CLI](cli.md): status, setup and teardown of
  the silent-audio development profile.
- Networking is optional. UART works without it. SSH transport is
  [planned in #15](https://github.com/aeharding/open-connect/issues/15);
  connecting Ethernet alone does not provide a configured SSH service.

The pinout above comes from the linked first-generation CMU references; it is not
a newly measured pinout of every model. Our recorded bench evidence verifies
115200/8N1 communication and software operation.
