# Mazda Open Connect

Improve first-generation Mazda Connect while keeping Mazda's look, controls and
everyday behavior. This site documents the project, the development bench and
what we have learned about the CMU.

**Development project, not an end-user installer.** Our supported bench firmware
is **55.00.750B North America (cmu150_NA)**. Findings and patches for that build
are not automatically valid on other firmware.

## Where to start

| You want to… | Start here |
| --- | --- |
| Connect a CMU on a desk | [Power, display and UART wiring](bench-setup.md) |
| Work with a connected bench | [Host CLI and bench profile](cli.md) |
| Develop a feature or fix | [Development guide](development.md) |
| Understand Mazda's software | [CMU system overview](cmu/index.md) and [findings](reverse-engineering.md) |
| Understand the proposed extension layer | [Architecture](extension-architecture.md) |
| Add or correct documentation | [Editing this site](documentation.md) |

## What exists today

The host tools provide UART operations and a runtime bench profile for silent
Entertainment UI testing. Prototype disclaimer changes have been tested and
undone on the bench. An early one-shot selector has also returned to baseline
after controlled native and JavaScript faults. See the
[startup recovery findings](reverse-engineering.md#startup-selection-and-reset-evidence)
for the diagrams, actual results and remaining limits. Persistent retry policy
and a general installer are still development work.

Installing the Python package installs host tools only; it does not deploy
anything to the CMU. Start with the CLI's dry run before using a connected device.

The [roadmap](https://github.com/aeharding/open-connect/blob/main/PLAN.md)
describes the next outcomes. [Issues](https://github.com/aeharding/open-connect/issues)
and [pull requests](https://github.com/aeharding/open-connect/pulls) track the work.

## Read the evidence in context

Reverse-engineering notes distinguish observed behavior, conclusions from source
or disassembly, and proposed designs. A successful software reboot is not a cold
vehicle start, and restoring a native library on disk does not unload its code.

Original project code and documentation are
[AGPL-3.0-or-later](https://github.com/aeharding/open-connect/blob/main/LICENSE).
OEM firmware, raw captures and credentials are not distributed. See the
[third-party boundaries](https://github.com/aeharding/open-connect/blob/main/THIRD_PARTY.md).
