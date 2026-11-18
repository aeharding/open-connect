"""Host CLI. Imports operation modules only after the user selects one."""

import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("""usage: oc {bench,uart,feature,usb} [options]

  bench   setup, status or teardown of the runtime development profile
  uart    low-level receive, identity, command or exact-file transfer
  feature build, prepare, trial, status or disable a developer feature
  usb     build-preview: package the USB launch experiment (no feature writes)

Device operations default to a dry run. feature build writes local files only.
Use oc COMMAND --help for options.
Runs on the host computer; installing this package changes nothing on the CMU.""")
        return 0
    command = argv.pop(0)
    if command == "bench":
        from .bench import main as run
    elif command == "uart":
        from .uart import main as run
    elif command == "feature":
        from .feature import main as run
    elif command == "usb":
        from .usb import main as run
    else:
        print(f"Unknown command: {command}. Choose bench, uart, feature or usb.", file=sys.stderr)
        return 2
    return run(argv)
