Native Intro-only disclaimer bypass — HOST prototype

The candidate bypasses native Disclaimer selection on the observed normal Intro
startup path. It keeps systemApp.js/GuiFramework/heartbeat unchanged. This is not
a mask, timer patch, universal firmware feature or live success claim.

Trusted passing packet: host-ready.json -> private manifest and candidate/profile.
Do not rebuild or substitute a candidate during the operator handoff. Reproduction:
  .venv/bin/python -B experiments/disclaimer-native/check.py
This creates a NEW private runs directory, compiles ARM code with installed Xcode,
builds the exact-base candidate, then runs the host contract/ELF checks. No install,
UART/camera access or native ARM execution is provided by these programs.

Implementation
- Redirect only System's existing call to UIAHLP_ProcessContextEvent at ELFVA7ed4
  through the new PIC wrapper. Its six actual arguments and return are forwarded.
- Eligible only for exact runtime machine/current-context/table identity, event1470,
  Intro1021, logo-state2 and focused appSystem1. Other calls use the stock machine.
- Factor the stock introend cleanup WITHOUT its SetAppContext portion. Clear the
  original state only on system()0; failure logs actual status and uses stock flow.
- A bounded per-call table view copies203cells/22headers. It substitutes stock
  A194's nine-rule cell only in this call, leaving its conditions, granted/denied
  actions, NULL/default behavior, successor/context/focus flags unchanged.
- Only the local Intro exit pointer changes. When the manager actually calls it,
  it invokes the original pending-warning hook once, then the stock quicktranlogo
  service stop with actual result logging (success100). No unconditional quickstop.
- Shared native tables, all other events/contexts, QuickStart and cold-start paths
  remain stock. No repeated event injection, direct GUI context write or timer.

ELF packaging
The924B compiled text/strings occupy the existing1024B zero RX padding at
VA/file48c00..49000. The first executable LOAD is extended within that padding;
its flags and other segments are unchanged. Only the original BL and LOAD lengths
change outside the stub. File size stays454142. R_ARM_CALL/JUMP24/REL32 are resolved
from compiler relocations; no guessed instructions, new dynamic dependency or
loader/config change. The original module has no unwind sections; new no-exception
C does not add unwind metadata. A12KiB delta holds full4KiB blocks[0,7,72]; the
profile gives exact source/delta/candidate count+MD5+POSIXCRC+SHA and dd block recipe.

Guards/undo
Only AS-FOUND55.00.750B/cmu150_NA nativeO SHAacf24ffd3719a29d2b4eefe80855ef6f164852fe3464858d07ca2d956395d302.
Exact UIA manager dependency hash is pinned in the profile. Unknown bases refuse.
Pure rollback returns retained O only when current matches the reviewed candidate;
unknown/later bytes refuse. Full OEM/native/candidate bytes stay under private
runs/backups, never in this distributable source directory.

Validation and limits
Four unittest cases passed, including an executed host build of the SAME C wrapper.
Its fixture uses the exact captured A80/A194 words. It verifies wrapper/table
preservation, all row selections, NULL/default delegation, grant/deny alternatives,
nofocus/unsupported pre-mutation fallback, cleanup failure status, six arguments,
return value and one old exit. It does NOT execute native predicates, real focus
arbitration, sentinel-1001 behavior or manager timing. The row0 fake simplifies
sentinel handling; this is not proof of actual nofocus/hook behavior.
ARM branch/relative relocations are checked at three load bases, plus exact-base,
delta reconstruction, same-length segments and conflict-refusing rollback. There
is no installed ARM emulator or actual CMU execution in this result.

Per-call clones rely on synchronous manager consumption: t13 found no retained
machine/cell/header store in the focused direct paths, with opaque-callback limits.
Clones add about3.3KiB of bounded ARM stack. Intro cleanup before later focus denial
is intentional (stock Dispose also precedes Timeout arbitration); denied paths do
not run the quickstop/exit hook or establish transition success. Pending-warning
hook timing changes when the intermediate screen is removed and needs bench check.
Cleanup failures remain failures in logs; successful compilation is not UI health.

Runtime package ownership
T14 owns the NEW native retention/VERIFY/UNDO/apply/two-startup observer under
experiments/native-disclaimer-runtime/. Existing JS recovery profiles cannot be
repointed. Independent native O/C/control/recovery must be verified before native
publication. Planned closure is ONE C boot, exact undo+RO, ONE fresh O confirmation;
disk undo does not unload a still-mapped C module. No live publication authority
comes from host-ready.json/freeze.json. Follow the checked complete runtime handoff.

History
The first check built the same candidate but host assert.h was unavailable without
an explicit Mac SDK root. Failed evidence is retained; adding-isysroot changed
only the host harness. The corrected run passed; native.c/build.py/candidate bytes
were unchanged. Existing first-feature/JS/core/executed profiles remain untouched.
