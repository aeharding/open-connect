Staged DATA delivery — experimental host tool

Default mode is offline: read a local regular single-link file <=16384 bytes,
print the planned DATA upload, open no hardware and write no bundle. The printed
command contains base64 source bytes. It never executes the uploaded content.

  .venv/bin/python -B experiments/staged-delivery/deliver.py stage --source /absolute/local/body.sh

A future separately authorized sole UART operator may add --live, a NEW --bundle
path, --owner, and --solicit-prompt only when the shell is known idle. This task
has NO live trial authority. Cleanup also defaults to a plan:

  .venv/bin/python -B experiments/staged-delivery/deliver.py cleanup --descriptor /absolute/private/bundle/stage.json

Live options, for future operator use only:
  --live --bundle /absolute/new/private/run --owner t14 --solicit-prompt

There is no destination, port or execution override. The only target location is
/tmp/cmu-bench-payload-<fresh random 32hex>/p. Stage requires a canonical root-owned
/tmp with a unique tmpfs mount row, then creates a fresh 0700/root directory and
0600/root regular single-link file. It checks size, target MD5/POSIX cksum, device
and observed inode/mtime/metadata. A completed core END0+prompt plus strict nonce
records produces stage.json. SHA256 is HOST provenance, not a target observation.

Cleanup accepts only the typed observed descriptor. It rechecks canonical paths,
exact file/directory identity, bytes/checksums and absence of unrelated entries,
then removes exactly p and its directory. Refusal, interrupted TX, malformed proof
or timeout preserves remaining target data. There is no retry or automatic cleanup.
A failure can leave an owned partial stage without a valid cleanup descriptor;
preserve the raw bundle for operator review instead of inventing an identity.

The existing FTDI lock, re-enumeration, fresh root55/NA identity, paced64B/20ms TX,
lossless raw events and finite45s per-operation deadline are reused unchanged.
A live invocation has separate bounded prompt/identity/delivery operations, not a
single45s wall-clock budget. No login, recovery keys, sync, mount, installed-file,
UI, service, reboot or power action is provided. It does not grant authority to
execute staged bytes; a separate reviewed short execution entry remains necessary.

Limitations: offline shell fakes model the command contract; they are not BusyBox,
UART, tmpfs, adversarial-root race or power-loss proof. Metadata/path guards have
ordinary check/use race limits. Directory mtime is recorded at second resolution.
Any unexpected or interleaved output fails closed. No new hardware trial was run.

Provenance: the DATA-only staging sequence is derived from saved operator scripts
runs/20261113T073945-0600-t14-modified-startup/prep.data-command.sh and
runs/20261113T065920-0600-t14-copy-knownC-recovery/data-stage.command.sh.
Those historical scripts/evidence and all existing transport/profiles are unchanged.

Offline checks: .venv/bin/python -B experiments/staged-delivery/check.py
Current passing review-only profile: review.json. Exact pre-test source copies,
core dependency pins, stdout/stderr and manifest are in the referenced checks run.
