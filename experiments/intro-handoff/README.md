# Paired disclaimer bypass

This prototype skips native Disclaimer selection using Mazda's existing nine-rule
startup continuation. The paired JavaScript hook disposes the intro player only
after the next screen finishes its transition. It preserves the stock Disclaimer
path, whose displayed callback already owns disposal.

No forced Home destination, delay, CSS mask or heartbeat change is added. The
native and JavaScript halves belong together. This builds private candidates;
it is not an installer and does not open UART, reboot or modify a CMU.

## Build and check from a fresh checkout

Install Python 3.13, Node.js, Clang with ARM support, and llvm-objdump. On Linux,
LLVM supplies the latter two tools; macOS Xcode tools can be found through xcrun.
The host compiler also needs normal C development headers. The full private-input
check has passed with Python 3.13, Apple Clang/LLVM 21.0.0 and Node 26.7.0.
Linux CI covers public entry-point failures; a full Linux private-input build
has not yet been validated.

From the repository root:

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python experiments/intro-handoff/check.py \
  --native-original /private/firmware55/libjciuiasystem.so \
  --system-app /private/firmware55/systemApp.js \
  --base-app /private/firmware55/BaseApp.js \
  --output runs/paired-feature-check
~~~

Replace the three input paths with your privately obtained originals. They need
not be inside this checkout. No historic capture directory, credentials or saved
run profile is required. Missing inputs fail explicitly before output creation;
running test_patch.py alone without inputs reports a skip, not a feature pass.

Only **55.00.750B NA / cmu150_NA** originals with these SHA256 hashes are accepted:

| Input | Source on CMU | SHA256 |
| --- | --- | --- |
| libjciuiasystem.so | /jci/mmui/uia/libjciuiasystem.so | acf24ffd3719a29d2b4eefe80855ef6f164852fe3464858d07ca2d956395d302 |
| systemApp.js | /jci/gui/apps/system/js/systemApp.js | 985cbcbeb1dedf11b76f61ffa1224e43165f80d8eb9c8d5d853d118d2eec3432 |
| BaseApp.js | /jci/gui/framework/js/BaseApp.js | 54c1e498bd430a59dccd3e204661d48864d093e6aa51999a5c35bccaa0801690 |

The build refuses unknown inputs; it does not download or distribute firmware.
BaseApp.js is a test fixture and is never patched. Keep these inputs and generated
full candidates private; see [THIRD_PARTY.md](../../THIRD_PARTY.md).

Tools default to PATH (then xcrun on macOS). Supply --clang /path/to/clang,
--objdump /path/to/llvm-objdump, --host-cc /path/to/cc or --node /path/to/node
when needed. Compiler code generation must fit the verified padding and relocation
contract; arbitrary LLVM releases are not guaranteed to produce identical bytes.

## Results

Use a new output directory for each run. The command builds/checks both halves:

- native/candidate/: patched module, block delta, original and profile.
- native/manifest.json: four exact-base, ELF/PIC and same-C host contract checks.
- js/: candidate.js, original.js, insertion and profile.
- js-check.stdout/stderr: two checks, including the real supplied BaseApp dispatcher.
- result.json: overall PASS/FAIL and source/tool provenance.

Exit 0 means all six feature checks passed. Failure preserves its output and exits
nonzero. Tracked ready/freeze profiles remain unchanged. The native candidate
requires the generated JS companion; neither output is live-authorized.

The host model does not execute ARM instructions or the real native manager.
It does not prove focus arbitration, CMU timing, visual smoothness or recovery.
Live publication still requires a newly qualified profile; historical manifests
remain refused by the current runtime guards. Restoring a native file on disk
does not unload a running modified module.

## Public checks without firmware

CI runs these checks with synthetic data, fake transports and temporary host files:

~~~sh
.venv/bin/python -m unittest discover -s experiments/mapped-publication -v
.venv/bin/python -m unittest discover -s experiments/intro-handoff -p test_boot.py -v
.venv/bin/python -m unittest discover -s experiments/intro-handoff -p test_publication.py -v
~~~

The full private-input feature command above is deliberately separate from CI.
The current implementation and bench findings are summarized in
[reverse-engineering.md](../../docs/reverse-engineering.md#disclaimer-and-intro-handoff).
