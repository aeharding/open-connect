"""Host CLI. Imports operation modules only after the user selects one."""

import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("""usage: oc {bench,uart,feature} [options]

  bench   setup, status or teardown of the runtime development profile
  uart    low-level receive, identity, command or exact-file transfer
  feature prepare, trial, status or disable a controlled bench feature

Device operations default to a dry run. Release builds use make release.
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
    else:
        print(f"Unknown command: {command}. Choose bench, uart or feature.", file=sys.stderr)
        return 2
    return run(argv)
