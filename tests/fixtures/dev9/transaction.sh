#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# The record is committed before any target is changed. Recovery completes that
# exact transaction, accepting only the prepared before/after state of each target.
# The caller holds the operation lock and supplies the firmware-specific adapters.

settled() { case "$R_PHASE" in active|removed) true;; *) false;; esac; }

dependencies_match() {
    local digest name extra target parent checked_parent= expected= actual snapshot=$1
    snapshot_verify "$1" || return 1
    set --
    while read -r digest name extra; do
        hex "$digest" 64 && test -n "$name" && test -z "$extra" || return 1
        target=$(dependency_path "$name") || return 1
        case "$name" in package-*/*|composed-*/*)
            parent=${target%/*}
            # Immutable package entries share a parent. Validate its ownership
            # once per consecutive group in this check, rather than for every
            # member. Each file still gets its full canonical/symlink check.
            if test "$parent" != "$checked_parent"; then
                private_dir "$parent" || return 1
                checked_parent=$parent
            fi;;
        esac
        file "$target" || return 1
        set -- "$@" "$target"
        expected="$expected$digest *$target
"
    done < "$D/snapshots/$snapshot/dependencies"
    test "$#" -gt 0 || return 0
    actual=$(openssl dgst -sha256 -r "$@") || return 1
    test "$actual" = "${expected%?}"
}

# Ordinary boot only: both the snapshot and this exact package were verified
# under the operation lock. Match its complete package expectations to that
# proof, and independently hash every OEM/composed destination before effects.
boot_dependencies_match() {
    local snapshot=$1 digest name extra scope leaf target parent checked= seen='|' mapping pin key path
    local members='|' member_count=1 package_count=0 manager=0 found expected= actual
    local composed='|' composed_count=0 composed_expected=1 root_count=0 root_expected=0
    while read -r digest name extra; do
        members="$members$name:$digest|"; member_count=$((member_count+1))
    done < "$P/files.sha256"
    members="${members}files.sha256:$R_BACKEND|"
    mapping=$(firmware_dependencies) || return 1
    while read -r pin key path; do
        if test "$key" != autostart; then root_expected=$((root_expected+1)); fi
    done <<PATHS
$mapping
PATHS
    parent=$D/composed/$R_BACKEND
    private_dir "$parent" && file "$parent/files.sha256" || return 1
    checked="|$parent|"
    while read -r digest name extra; do
        hex "$digest" 64 && test -n "$name" && test -z "$extra" || return 1
        case "$name" in .|..|*[!a-zA-Z0-9_.-]*) return 1;; esac
        case "$composed" in *"|$name:"*) return 1;; esac
        composed="$composed$name:$digest|"; composed_expected=$((composed_expected+1))
    done < "$parent/files.sha256"
    for name in uia.so mmui.so mmui.xml system-app.js index-on.html index-off.html \
        sm-normal-on.conf sm-normal-off.conf sm-wcp-on.conf sm-wcp-off.conf autostart; do
        case "$composed" in *"|$name:"*) ;; *) return 1;; esac
    done
    set --
    while read -r digest name extra; do
        hex "$digest" 64 && test -n "$name" && test -z "$extra" || return 1
        scope=${name%%/*}; leaf=${name#*/}
        test "$scope/$leaf" = "$name" || return 1
        case "$leaf" in ''|.|..|*[!a-zA-Z0-9_.-]*) return 1;; esac
        case "$seen" in *"|$name|"*) return 1;; esac
        seen="$seen$name|"
        case "$scope" in
          root)
            found=0; target=
            while read -r pin key path; do
                if test "$key" = "$leaf" && test "$key" != autostart; then
                    target=$path; found=$((found+1))
                fi
            done <<PATHS
$mapping
PATHS
            test "$found" = 1 && file "$target" || return 1
            root_count=$((root_count+1))
            if test "$leaf" = manager.so; then native_dependency_guard "$digest" || return 1; manager=$((manager+1)); fi;;
          package-*|composed-*)
            if test "$scope" = "package-$R_BACKEND"; then parent=$P
            elif test "$scope" = "composed-$R_BACKEND"; then parent=$D/composed/$R_BACKEND
            else return 1; fi
            case "$checked" in *"|$parent|"*) ;;
                *) private_dir "$parent" || return 1; checked="$checked|$parent|";; esac
            target=$parent/$leaf
            test -f "$target" && test ! -L "$target" || return 1
            if test "$scope" = "package-$R_BACKEND"; then
                case "$members" in *"|$leaf:$digest|"*) ;; *) return 1;; esac
                package_count=$((package_count+1)); continue
            fi
            if test "$leaf" != files.sha256; then
                case "$composed" in *"|$leaf:$digest|"*) ;; *) return 1;; esac
            fi
            composed_count=$((composed_count+1));;
          *) return 1;;
        esac
        set -- "$@" "$target"
        expected="$expected$digest *$target
"
    done < "$D/snapshots/$snapshot/dependencies"
    test "$package_count" = "$member_count" && test "$manager" = 1 &&
        test "$root_count" = "$root_expected" && test "$composed_count" = "$composed_expected" &&
        test "$#" -gt 0 || return 1
    actual=$(openssl dgst -sha256 -r "$@") || return 1
    test "$actual" = "${expected%?}"
}

dependencies_pair_match() {
    dependencies_match "$1" || return 1
    # Settings and uninstall keep the same dependency bytes. Check them once.
    if cmp -s "$D/snapshots/$1/dependencies" "$D/snapshots/$2/dependencies"; then
        snapshot_verify "$2"
    else
        dependencies_match "$2"
    fi
}

targets_match() {
    snapshot_read "$1" && targets_match_loaded "$1" || return 1
    if test "$S_ACCESS" = true; then access_login_check; fi
}

# Current snapshot fields and bytes were verified by the caller. The boot path
# checks baseline login lifetime separately while those baseline fields are live.
targets_match_loaded() {
    file "$AUTOSTART" &&
        test "$(sha "$AUTOSTART")" = "$(sha "$D/snapshots/$1/autostart")" &&
        test "$(stat -c '%a:%u:%g' "$AUTOSTART")" = "$S_META" &&
        test "$(nvram_read)" = "$S_NVRAM" || return 1
    if test "$S_ACCESS" = true; then access_files_match_loaded "$1" || return 1; fi
    if test "${S_SELECTOR_RECORDED:-false}" = true; then selector_matches_loaded || return 1; fi
}

state_capture() (
    set -eu
    local deps result
    deps=$(mktemp "$D/.dependencies-XXXXXX") || fail checkpoint_create_failed
    dependencies_capture "$1" > "$deps" || fail checkpoint_dependencies_failed
    result=$(snapshot_create "$AUTOSTART" "$1" "$2" "$3" "$(nvram_read)" "$(stat -c '%a:%u:%g' "$AUTOSTART")" "$deps" "${4:--}" "${5--}" "${6--}" "${7--}") || fail checkpoint_failed
    rm "$deps"
    printf '%s\n' "$result"
)

uninstall_owned() (
    # Legacy Undo could adopt external edits into the current snapshot. Check
    # the saved before-state too: recovery may already have restored a target.
    local current_mode current_touch current_nvram snapshot=$1
    snapshot_read "$snapshot" || return 1
    hex "$S_PACKAGE" 64 && file "$D/composed/$S_PACKAGE/autostart" &&
        test "$(sha "$D/snapshots/$snapshot/autostart")" = "$(sha "$D/composed/$S_PACKAGE/autostart")" || return 1
    current_mode=$S_META; current_touch=$S_TOUCH; current_nvram=$S_NVRAM
    snapshot_read "$R_BASE" || return 1
    test "$current_mode" = "$S_META" || return 1
    # Exhausted startup recovery may restore the baseline while touch remains
    # selected. Otherwise, only our enabled-touch value belongs to this package.
    test "$current_nvram" = "$S_NVRAM" || test "$current_touch:$current_nvram" = 1:disable
)

transaction_prepare() {
    # phase, before, after; preserve originals until restoration is verified.
    settled || fail operation_pending
    snapshot_read "$2" && snapshot_read "$3" || fail invalid_plan
    targets_match "$2" && dependencies_pair_match "$2" "$3" || fail state_changed
    R_PHASE=$1; R_BEFORE=$2; R_AFTER=$3
    record_write
    PREPARED_REV=$R_REV
}

transaction_reconcile() {
    settled && return
    local before_hash after_hash before_mode after_mode before_nv after_nv actual_hash actual_mode actual_nv phase
    phase=$R_PHASE
    # An old prerelease could prepare a conflicted uninstall with a promise to
    # retain Undo. Do not turn that operation into deletion of its saved edits.
    if test "$phase" = uninstall; then
        test "$R_BEFORE" = "$R_CURRENT" || fail state_changed
        uninstall_owned "$R_BEFORE" || fail state_changed
    fi
    snapshot_read "$R_BEFORE" || fail invalid_before
    before_hash=$(sha "$D/snapshots/$R_BEFORE/autostart"); before_mode=$S_META; before_nv=$S_NVRAM
    snapshot_read "$R_AFTER" || fail invalid_after
    after_hash=$(sha "$D/snapshots/$R_AFTER/autostart"); after_mode=$S_META; after_nv=$S_NVRAM
    # A fresh process recovering a pending record must verify both sets again.
    # The immediate caller just did this before committing the same record.
    if test "${PREPARED_REV:-}" != "$R_REV"; then
        dependencies_pair_match "$R_BEFORE" "$R_AFTER" || fail dependencies_changed
    fi
    file "$AUTOSTART" || fail startup_changed
    actual_hash=$(sha "$AUTOSTART"); actual_mode=$(stat -c '%a:%u:%g' "$AUTOSTART"); actual_nv=$(nvram_read) || fail nvram_unreadable
    case "$actual_hash:$actual_mode" in "$before_hash:$before_mode"|"$after_hash:$after_mode") ;; *) fail startup_changed;; esac
    case "$actual_nv" in "$before_nv"|"$after_nv") ;; *) fail nvram_changed;; esac
    if test ! -e "$D/snapshots/$R_BEFORE/access" && test ! -e "$D/snapshots/$R_AFTER/access"; then :
    else access_pair_check "$R_BEFORE" "$R_AFTER" || fail access_changed; fi
    selector_pair=false
    if ! absent "$D/snapshots/$R_BEFORE/selector" || ! absent "$D/snapshots/$R_AFTER/selector"; then
        selector_pair_check "$R_BEFORE" "$R_AFTER" || fail selector_changed
        selector_pair=true
    fi
    # Install the recovery entry before changing NVRAM. Remove it last on
    # uninstall. Re-committing a matching NVRAM value repairs an interrupted commit.
    if test "$phase" != uninstall; then
        if test "$selector_pair" = true; then selector_apply "$R_BEFORE" "$R_AFTER" || fail selector_apply_failed; fi
        startup_publish "$D/snapshots/$R_AFTER/autostart" "$after_mode" "$actual_hash" "$actual_mode"
    fi
    if test -e "$D/snapshots/$R_AFTER/access"; then
        access_pair_apply "$R_BEFORE" "$R_AFTER" || fail access_apply_failed
    fi
    nvram_change "$actual_nv" "$after_nv" || fail nvram_commit_failed
    if test "$phase" = uninstall; then
        startup_publish "$D/snapshots/$R_AFTER/autostart" "$after_mode" "$actual_hash" "$actual_mode"
        if test -e "$D/snapshots/$R_AFTER/access"; then access_hold_cleanup || fail access_cleanup_failed; fi
        if test "$selector_pair" = true; then selector_apply "$R_BEFORE" "$R_AFTER" || fail selector_remove_failed; fi
    fi
    if test "$selector_pair" = true; then
        selector_pair_check "$R_AFTER" "$R_AFTER" || fail selector_verification_failed
    fi
    targets_match "$R_AFTER" && dependencies_match "$R_AFTER" || fail final_verification_failed
    # Only packages with the native-selector capability produce a sealed plan.
    # Current installed dev.8 and interrupted older transactions stay valid.
    if test "$phase" != uninstall && test "$S_PACKAGE" != - &&
        ! absent "$D/packages/$S_PACKAGE/boot-select"; then
        R_AFTER=$(boot_snapshot_seal "$R_AFTER") || fail boot_snapshot_failed
        snapshot_read "$R_AFTER" || fail invalid_boot_snapshot
    fi
    R_CURRENT=$R_AFTER
    case "$phase" in
        uninstall) R_PHASE=removed; R_NOTICE=removed; R_BUDGET=0;;
        install) R_PHASE=active; R_NOTICE=installed; R_BUDGET=3;;
        set) R_PHASE=active; R_NOTICE=restart; R_BUDGET=3;;
        apply) R_PHASE=active;;
    esac
    R_BEFORE=-; R_AFTER=-
    if test "$phase" != apply; then R_OFF=-; R_BOOT=-; fi
    record_write
}

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
