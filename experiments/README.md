# Prototype mods and bench trials

These are development experiments, **not an installer or the host Python package**.
Nothing here is deployed by pip install or by importing open_connect.

## Start with the relevant prototype

| Directory | What it contains | Deployment boundary |
| --- | --- | --- |
| [disclaimer-native](disclaimer-native/) | ARM C bypass and host ELF patch builder | native.c is compiled into a CMU library candidate; Python stays on the host |
| [intro-handoff](intro-handoff/) | Paired GUI completion hook and host trial runner | Generated JavaScript modifies systemApp.js; Python stays on the host |
| [mapped-publication](mapped-publication/) | Library apply/undo with hardlink holds | Host orchestrator sends guarded shell payloads |
| [staged-delivery](staged-delivery/) | Checked payload transfer | Transfers data; does not execute it |
| [tau-bypass](tau-bypass/) | Earlier Audio Manager investigation | Maintained helper is now src/open_connect/bench.py |

All other directories are earlier prototypes or supporting trial machinery.
They remain here because some of the later trials still import them. They are
not independent supported products. Consolidate a shared helper when working
on its actual consumer; do not copy another experiment to make a new framework.

## Running checks

Read the directory's instructions first. The mapped-publication suite and
intro-handoff boot/publication checks run from a public checkout and are in CI;
their READMEs give exact commands. Other checks require private exact OEM files,
Node.js or an ARM toolchain. A public checkout contains no captured firmware or
run records.

Saved ready/freeze/check manifests describe the source at the time of that trial.
Repository reorganization changes source paths and hashes; these old live profiles
are historical and must not be replayed as current authorization. Fresh target
identity, current checked code and independent undo remain necessary for live work.

Current limitations: several prototype inputs are still tied to local capture
paths, and shared publication/startup code crosses experiment directories. These
are unfinished extraction work, not a stable public mod API.
