# Startup research probes

The supported disclaimer workflow has moved to
[host tooling](../../tooling/README.md). Use the
[developer guide](../../docs/disclaimer-development.md) to build, try and disable it.

This directory keeps three open research questions:

- **Attempt budget:** budget.py and budget.sh.in reserve a finite number of starts.
  Confirmation does not refund an attempt. Renewal is explicit; automatic ACC
  renewal remains unimplemented.
- **Combined configuration:** compose.py tests service policy, logging, native
  and JS changes together using OEM launch configuration.
- **Private file views:** namespace.c and the probe templates investigate mount
  isolation and its consequences for later mounts and shutdown.

## Offline checks

Install the host package from the checkout, plus Clang:

~~~sh
python -m unittest discover -s experiments/boot-selection -v
python experiments/boot-selection/build_namespace.py --output runs/namespace-build
~~~

The maintained selector, flush, readiness and workflow tests now live in tests/
and run with tests/run_offline.py.

## Private builds

compose.py requires the exact private OEM inputs; budget.py takes its output.
Use their --help output for arguments. Generated files must stay under runs/.
These commands build artifacts; they do not install or activate them.

[Startup findings and diagrams](../../docs/reverse-engineering.md#startup-selection-and-reset-evidence)
describe the actual bench results and remaining limits. Earlier commands and
completed prototypes remain in Git history; private result bundles are unchanged.
