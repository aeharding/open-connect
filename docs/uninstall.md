# Uninstall and its single undo checkpoint

Status: agreed product behavior, 2026-11-13. Plan only; not implemented.
Scope: one feature, one exact supported firmware. Tracking: [#7](https://github.com/aeharding/open-connect/issues/7).

## User contract

Uninstall restores the verified files saved before the first Open Connect install.
Unknown edits to those files do not automatically block uninstall: preserve their
current contents first, explain that later modifications to these files will be
removed, then let the user proceed with uninstall.

For an uninstall with conflicts, retain one checkpoint and offer **Undo this
uninstall**. It restores the immediately preceding files and Open Connect
installation state, including those other edits. It does not merge mods or
promise that the preceding modified state was healthy.

If relevant files or installation state change after uninstall, undo stops and
preserves everything. No force restore, merge, second conflict workflow or recursive
recovery layer. This is the user's explicit boundary.

Normal product actions remain Install/update and Uninstall. Undo this uninstall
is available only for a retained eligible conflict-uninstall checkpoint.

## Three states, not a merge engine

- **Original:** as-found files and metadata saved before our first installation.
  Preserve these across update/reinstall. They may already contain other mods;
  they are not authenticated factory images.
- **Before uninstall:** the actual current managed files, presence/absence,
  relevant metadata and Open Connect installation/configuration records.
  Snapshot the entire set uninstall will change, not only the conflicting file.
- **After uninstall:** the actual verified result for that same set, including
  installed/disabled records and removed or retained owned files.

These are bounded snapshots of this feature's managed paths, not the whole CMU.
Unrelated user files and continuously changing logs are outside the transaction.
Keep the original backup lineage separate from the undo checkpoint.

## Uninstall sequence

1. Validate the supported firmware/region, original backups, parsed installation
   record and expected canonical file paths. Classify known installed, already
   original, missing and unknown-content states. Do not execute checkpoint data.
2. Plan the complete affected set. Verify storage capacity, capture before-uninstall
   bytes/presence/metadata and installation state, and verify the checkpoint before
   replacing or deleting anything. A failed snapshot means no target changes.
3. For conflicts, explain: “These files changed after installation. Uninstall will
   save their current versions and restore the pre-install versions.” Show affected
   paths and let the user continue or cancel within Uninstall.
4. Revalidate the just-captured state before mutation. Restore originals and remove
   only recorded owned additions. Record intent/progress and verify each result.
   Do not overwrite unrelated paths or silently rebaseline original backups.
5. Record actual after-uninstall state and checkpoint eligibility. Keep inert
   checkpoint data and required original backups so a compatible replacement USB
   package can find them. Do not require the original installation stick.

Already-original files need no rewrite. A missing managed file can be restored
from a valid original when its canonical parent and other guards hold.
Unknown *contents* are different from a firmware mismatch, corrupt backup,
untrusted installation record or a symlink/path substitution. Those structural
problems stop automatic mutation with a specific explanation.

## Undo this uninstall

1. Find the single checkpoint for this device/install lineage using a current
   compatible USB package. Verify its contents, original-backup lineage, firmware,
   path safety and completed-uninstall record.
2. Compare the whole affected set against the recorded after-uninstall state:
   content or absence, relevant attributes and installation/configuration records.
   Ignore expected boot-time volatility such as access times and running PIDs.
   A newer install/update invalidates eligibility.
3. If anything relevant differs, **stop without modifying files**. Keep the
   checkpoint for manual diagnosis. Do not offer an overwrite or merge fallback.
4. Otherwise restore the before-uninstall snapshot as one journaled operation,
   including the installation state. Keep original backups unchanged. Verify
   readback and report “Previous modified installation restored,” not “stock” or
   “known-good feature.”
5. Mark this undo consumed. Do not build a chain of redo/undo checkpoints.

Serializing our own operations does not prevent another writer. Recheck before
each replacement; a mismatch during execution stops further writes and records
partial progress rather than claiming success. Existing interruption handling may
resume only from known recorded states; it cannot bypass an unknown-edit refusal.
Do not claim multi-file atomicity or power-loss durability from host tests.

## Loaded files and retained data

Reuse the proven mapped-file hold/replacement/RO procedure. Restoring disk files
does not unload a native library or cached frontend. Where startup is required,
verify the resulting loaded state before declaring the operation fully complete.
Do not remove holds or executable recovery dependencies while they are still needed.

The checkpoint must outlive uninstall and USB replacement. Retain it until undo
is consumed or it is explicitly discarded; a later install/update invalidates
automatic undo and must not silently reuse or overwrite that checkpoint.
Exact storage layout and cleanup implementation remain small implementation choices.
A CMU that cannot execute USB maintenance is outside this USB undo capability.

## Focused validation before release

| Case | Required result |
| --- | --- |
| Known installed files | Restore originals and verify resulting state |
| Unknown edits in a managed file | Verified complete checkpoint, explicit conflict notice, original restoration |
| Edit existed before first install | Restore that as-found baseline; no factory claim |
| Missing managed file | Restore only with valid original and safe path; snapshot absence for undo |
| Conflict uninstall followed by unchanged state | Undo restores all captured files/records, original backups unchanged |
| Post-uninstall edit, missing file, changed attributes or new install | Undo refuses without writes; checkpoint retained |
| Bad backup/checkpoint, wrong firmware or redirected path | Refuse automatic mutation; preserve evidence |
| Snapshot failure or insufficient space | No uninstall writes |
| Interruption between writes | Honest pending state; resume only known transitions; no unknown-state override |
| Native/frontend replacement | Check disk and loaded state separately; retain/release holds at the correct time |
| Fresh compatible replacement USB | Discover checkpoint and perform the same guarded undo |

Implementation should extend the existing snapshot/journal/undo pieces for this
one feature. No general diff-merging engine, backup browser or new installer framework.
