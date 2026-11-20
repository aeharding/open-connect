# Bench tooling and release build

`oc` is a host-side CLI for bench instrumentation: UART access, the development
profile, observation and file recovery. `open_connect/` is
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

The [installer development guide](../docs/installer-development.md) describes the standalone installer and
its current qualification limits.

- device/: finite video capture, bounded data staging and generic file publication.
- elf.py: read-only ARM ELF metadata inspection for private host checks.
- session.py, uart.py, files.py: serial transport and exact-file operations.
- bench.py: the runtime development profile.

Target source lives in cmu/; maintained tests live in tests/. The optional
private validation entry is tests/check_firmware.py. The obsolete v55 one-shot
builder, selector and Home supervisor are retained in Git history.

Make/LLVM compiles the native assets using standard tools. The public build uses
neither the Python package nor private OEM files.
