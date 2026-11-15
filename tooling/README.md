# Host tooling

open_connect/ is the Python package behind oc. Nothing in it is deployed to
the CMU by installing the package.

- feature.py: public build, inspect, prepare, trial, status and disable commands.
- firmware55/: builders for the one supported firmware.
- device/: staging, file publication, startup observation and independent disable.
- session.py, uart.py, files.py: serial transport and exact-file operations.
- bench.py: the runtime development profile.

Target source and shell templates live in cmu/; maintained tests live in tests/.
The installed package must match the checkout supplied to a feature operation.
