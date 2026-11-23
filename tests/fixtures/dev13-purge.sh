# SPDX-License-Identifier: AGPL-3.0-or-later
# Exact authored dev.13 purge body from 24d3931; regression fixture only.
uninstall_cleanup() {
    # The caller holds the operation lock and runs from its verified RAM copy.
    private_dir "$D" || fail invalid_state_directory
    case "$P" in "$D"|"$D"/*) fail cleanup_requires_ram;; esac
    test "$(root_mode)" = ro,noatime || fail root_mount_changed
    # Do not cross a mounted filesystem while removing the owned state tree.
    cleanup_mount_guard || fail cleanup_mount_present
    if absent "$D/record"; then
        # A cut after the final unlink can leave only the empty directory.
        rmdir "$D" || fail invalid_cleanup_state
        flush d "${D%/*}"
        return
    fi
    record_read || fail invalid_record
    case "$R_PHASE" in
        removed)
            targets_match "$R_CURRENT" && dependencies_match "$R_CURRENT" || fail state_changed
            startup_staging_guard || fail startup_stage_changed
            R_PHASE=purge
            record_write;;
        purge) ;; # Restoration was durably verified before this phase began.
        *) fail not_removed;;
    esac
    # Keep the authoritative record until every other entry is gone. USB
    # recovery can resume partial cleanup without snapshots already deleted.
    local path
    for path in "$D"/* "$D"/.[!.]* "$D"/..?*; do
        absent "$path" && continue
        test "${path##*/}" != record || continue
        rm -rf "$path" || fail cleanup_failed
    done
    flush d "$D"
    rm "$D/record" || fail cleanup_failed
    flush d "$D"
    rmdir "$D" || fail cleanup_failed
    flush d "${D%/*}"
}
