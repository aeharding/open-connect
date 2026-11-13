Latest host capability: explicit COMPLETE-uninstall (16 checks passed).
Current identity authority: adapter-checks/20261113T093846.327626Z/manifest.json.
Result: complete-recovery-result.txt. Previous10-test and6-test records below
remain historical; final-handoff.json is the prior10-test review list.

Named API on an already owned HOST fixture Engine:
  engine.recover()             # unchanged ABORT to previous stable state
  engine.complete_uninstall()  # explicit COMPLETE of a recorded pending uninstall
COMPLETE accepts only valid uninstall intent and stored images. Already-original
is verified/committed disabled without a target rewrite; known candidate is
restored to stored original then committed disabled. Unknown bytes/mode or bad
journal/backup refuse. An already committed disabled state is a read-only no-op;
no pending enabled state is implicitly uninstalled. Before final commit, another
interruption remains pending and requires a new explicit disposition. Model commit
is not a durability guarantee or selected target/product policy.

Frozen HOST installer model — exploratory, no device installer

Synthetic demo (temporary fixtures only):
  hc exec --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/installer-proof/demo.py
Optional private disclaimer-copy demo:
  hc exec --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/installer-proof/disclaimer_adapter.py
The adapter prints SKIP if the private AS-FOUND installed55 source is absent;
no fetch, alternate base, real target path or device operation is supported.

Focused adapter + engine checks (10 cases, already passed; no rerun queued):
  hc run --bg --name disclaimer-adapter-checks --parent t12 --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/installer-proof/run_adapter_checks.py
  hc wait disclaimer-adapter-checks
Current result and identity authority: adapter-result.txt and
adapter-checks/20261113T085514.871946Z/manifest.json.
Exact pre-test code copies, test transcript and hash-only demo are beside it.

One shared transition stores observed original bytes, persists images+journal
intent before replacement, verifies readback and commits state. Same-state
reapply is a no-op. Explicit recovery aborts to the previous stable image;
uninstall restores stored original. Pending work blocks automatic retry.
Unknown/later bytes or mode changes are conflicts: preserve file+journal, no
fuzzy patch or merge. Unrelated files remain untouched. Unsupported bases,
corrupt images and symlinks refuse. One synthetic feature supports DEMO->READY
reconfiguration. The private adapter imports the frozen pure disclaimer patch
and passes original/candidate images to this same engine; feature logic and all
independent disclaimer pins remain unchanged.

All full OEM copies/stored bytes live only in temporary ignored runs/ directories
and are removed. Retained adapter reports contain metadata, not OEM source.
The private master stays unchanged. Copy mode0755 models observed OEM listing;
bytes+mode restoration is demonstrated on host copies, not the CMU. The engine
profile seam is bounded to100000 bytes; default synthetic read cap stays4096.
Tests exercise real process exit before/after mutation, including stored-original
recovery without the master path, conflicts and unsupported/missing source.

Limits: single writer, no atomic compare-and-swap or ownership/ACL/xattr recovery.
Process-exit/fsync is not power-loss, relfs durability, startup/no-flash, installation
or device recovery proof. No USB entrypoint, network/publication or product policy.
Schema ideas are isolated in schema-proposal.json and are not consumed at runtime.
Historical6-test synthetic proof: result.txt and checks/20261113T084529.289170Z/.
Earlier source bytes: before-resume/ and before-disclaimer-adapter/.
Final sources are frozen; review list and saved evidence: final-handoff.json.
