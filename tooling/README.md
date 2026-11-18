# Bench tooling and release build

`oc` is a host-side CLI for bench instrumentation: UART access, the development
profile, controlled feature trials, observation and recovery. `open_connect/` is
its Python package. Installing that package installs tools on your computer,
not on the CMU. See [CLI usage](../docs/cli.md).

`oc` is **not** a release builder, USB packager, owner-facing installer or CMU
runtime. Do not add product build or installation commands to it. Bench commands
may stage and undo test changes; they do not provide the owner's install/uninstall
backend.

Release builds belong to the root [Makefile](../Makefile), invoked with
`make release`. The [packaging script](package-usb.sh) copies static files from
[cmu/](../cmu/README.md) and writes checksum data. The USB loader, installer UI
and install/uninstall backend belong in `cmu/` and run on the head unit. The
release must work without `oc`, host Python, SSH or a connected computer.

The current bundle validates USB entry and dialog cleanup only. Connecting the
install/uninstall backend remains unfinished; it is not an installable feature
release yet.

- feature.py: bench prepare, trial, status and disable operations. Its module
  entry prepares and inspects private bench fixtures, outside the `oc` CLI.
- firmware55/: private bench fixture preparation and validation for the supported firmware.
- device/: staging, file publication, startup observation and independent disable.
- session.py, uart.py, files.py: serial transport and exact-file operations.
- bench.py: the runtime development profile.

Target source and shell templates live in cmu/; maintained tests live in tests/.
The installed package must match the checkout supplied to a feature operation.

Make/LLVM compiles the native assets using standard tools. The public build uses
neither the Python package nor private OEM files.
