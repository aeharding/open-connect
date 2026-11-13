FIRST REAL-FILE WARM ROUNDTRIP — PREPARATION / COORDINATOR REVIEW ONLY
No UART/remount/source write has been executed. Do not hand to t14 until the
coordinator reviews this genuinely new real-file boundary. Existing feature,
core, host engine and copy-transaction sources remain unchanged.

Question: can one observed55.00.750B/cmu150_NA AS-FOUND systemApp.js make a warm
original->frozen candidate->original byte roundtrip, keeping the current frontend
loaded? Startup, invisible disclaimer behavior and health/recovery are not tested.
Only the already frozen initial3500->0 byte recipe is used. No new feature patch.

Review-only generation (no UART; outputs a proposed invocation as DATA):
  hc exec --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B experiments/disclaimer-warm-roundtrip/prepare.py --out experiments/disclaimer-warm-roundtrip/NEW_REVIEW_DIRECTORY
This refuses existing output directories. plan.json and proposed-invocation.json
contain exact argv/deadline/cap; generated command.sh is never executed by prepare.
Do not execute the proposed invocation before coordinator review.

Order and guards
1. Require root55 via existing paced runner plus inner UID0; strict physical root
   /dev/ffx01p1 / relfs ro,noatime and separate rootfs/rw row; canonical/nonlink
   source parents, known device and exact initial inode/bytes/0755/1018:3015/mtime.
2. Create NEW root-owned0700 nonce directory on known rw data_persist; validate
   parents/device/mount/free budgets. Retain verified original+candidate+metadata
   and strict data-only pending intent BEFORE RW. Journal is never sourced/evaled.
3. Run checked no-argument /bin/sync (best-effort only), then request exact
   /bin/busybox mount -i -n -t relfs -o remount,rw,noatime /dev/ffx01p1 /.
   Require both request0 AND exact physical RW row. The rootfs/rw pseudoentry is
   insufficient; BusyBox may return0 after RO fallback. Unsupported-i/-n refuses
   before staging; there is no automatic argv without them or other alternative.
4. Create unique same-parent C and original-rollback stages; validate bytes, count,
   hashes, mode/UID/GID/mtime and captured identities. Revalidate source/intent/RW
   before candidate replacement. Verify full candidate via cmp/readback and record.
5. Record DISABLE intent. On known owned C with valid evidence, restore the verified
   original stage. On O already present, verify/commit disabled WITHOUT rewriting
   O. OTHER or bad/missing backup/journal/stage refuses overwrite and preserves.
6. File restoration and stage cleanup are isolated from RO handling. Stage-refusal
   is captured separately so verified-original sync still runs; even failure of
   restoration or that second sync cannot bypass the paired exact RO request and
   physical-row check after any RW request. Before RW was requested, failures only
   verify unchanged RO; they do not remount an unexpected initial state.
7. Retain original/candidate/journal until review. Remove only full-name nonce-owned
   root stages with matching verified images/identity. END0 requires original,
   complete disabled record, successful cleanup/flush and strict final RO.
   Original bytes+0755+UID1018/GID3015+mtime1433953097 are checked; inode replacement
   is explicitly recorded as initial_id/final_id, not called unchanged metadata.

Known assumptions and limits for review
-i/-n are source-backed and absent from actual installed help. Exact commands fail
closed if unsupported. Existing stock timeout -t8 -s15 nominally bounds mount/sync;
its finite watcher and TERM are not a hard kernel-I/O deadline. SIGKILL, uninterruptible
I/O, power loss or host disconnect cannot guarantee trap completion. Unknown state
preserves evidence and stops; no retries/automatic alternate remount or reboot.
Cleanup signal boundary: _finish resets HUP/INT/TERM to their default action.
A new signal during cleanup, including a repeated signal after one triggered exit,
can terminate the parent before RO. This limited one-trial contract assumes no
injected parent signals/interrupts during cleanup; it does NOT guarantee RO after
such interruption. TERM is not globally ignored and children retain normal timer
signal behavior. The checks exercise uninterrupted cleanup after known failures,
not signal-proof cleanup. Signal/timeout/unknown outcomes preserve evidence and
stop for coordinator reconciliation; there is no automatic follow-up or retry.
A failed RO return remains explicit unresolved state even if O is restored.
Bad control/OTHER may leave C or stages retained with RO attempted; no false restore
success. Single-writer/TOCTOU assumption remains; no atomic compare-and-swap.
mtime is checked at available stat seconds resolution. No inode preservation,
ACL/xattr/full metadata, crash/power-loss durability or root-RelFS recovery promise.
sync0 and readback are runtime/best-effort observations, not durability guarantees.

Provenance: notes/remount-preparation.txt; actual mount-help-output.txt in t14's
copy-transaction record; experiments/disclaimer/freeze.json; prior isolated-copy
primitives. Host checks use confined filesystem/UID/GID/mount/sync contract fakes,
not native mount/sync/chown and not proof of vendor/RelFS semantics. No full-suite
or core test rerun. Current authoritative check/payload references are in result.txt.
