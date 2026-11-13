Native Intro-only bypass — host build component

Start with ../intro-handoff/README.md for the complete paired feature and its
single build/check command. This native.c is the deferred-intro variant: it
requires the JavaScript completion hook. Do not install the native half alone.

How it works
The wrapper intercepts System's UIAHLP_ProcessContextEvent call only for the
verified IntroAnimation/ShowDisclaimer path. A per-call table view reuses the
stock nine-rule continuation, preserving predicates, granted/denied actions,
focus flags and destinations. Other events/contexts retain stock behavior.
The original Intro exit hook runs once; quick-logo cleanup follows actual exit.
Intro disposal is deferred to the renderer's completed-transition callback.
There is no forced Home destination, visual mask or timer tuning.

Build separately (usually use the paired command instead):
  .venv/bin/python experiments/disclaimer-native/check.py \
    --original /private/firmware55/libjciuiasystem.so \
    --output runs/native-check
    --original /private/firmware55/libjciuiasystem.so \
    --output runs/native-check

Inputs and tools are explicit. --clang, --objdump and --host-cc override PATH
discovery; macOS also supports xcrun. Clang must support armv7-none-eabi;
llvm-objdump must disassemble ARM. The host C compiler builds a native executable.
Linux uses its normal headers; macOS obtains the SDK through xcrun.

The exact original must be 454142 bytes, SHA256:
acf24ffd3719a29d2b4eefe80855ef6f164852fe3464858d07ca2d956395d302
Supported firmware: 55.00.750B NA/cmu150_NA only. Unknown bytes refuse.

Output and checks
Each new output directory contains compiler output, pre-test sources, exact-base
candidate, 12KiB block delta, profile, host contract executable and manifest.
host-ready.json is written ONLY inside that output directory; tracked historical
profiles are never refreshed. build.py accepts the same --original/--output plus
--clang/--objdump for build-only use.

The stub must fit the existing 1024-byte zero RX padding. The builder resolves
ARM CALL/JUMP24/REL32 relocations, extends the original RX LOAD within that padding,
and retains the 454142-byte module length. Compiler version and commands are
recorded. Different compiler versions are not promised byte-identical output;
unexpected relocation forms, excess size or changes outside the delta refuse.

Four checks cover exact-base refusal/delta/undo, relocation math at three load
bases, segment boundaries and an executed host build of the same C wrapper.
The private OEM table fixture is generated from the supplied original, never
published. The fake manager does not execute real predicates, focus arbitration,
sentinel handling, timing or ARM code. This is host qualification, not CMU proof.

Generated full OEM/candidate files stay under ignored runs/ or backups/.
Profiles record the required UIA manager hash but this build does not read or
verify a running CMU. Native replacement needs mapped-inode holds, independent
undo, fresh live dependency checks and restored-original startup verification.
Historical freeze/ready files are prior evidence, not live execution authority.
