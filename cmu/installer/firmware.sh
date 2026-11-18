#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Compose private launch files from this unit's verified originals. All code
# fragments and native replacement bytes are authored/compiled in the package.

original_files() {
    cat <<'ORIGINALS'
b91b2c5a5b7d036860321da730ad571dbae9164d2632946f6566238c3cd42e31 autostart /usr/bin/autostart
52dac9b051ab02a07afdc7bdfac56402420f8230901b5a55a76a7e9c44fb2e08 sm.conf /jci/sm/sm.conf
2c2c0494817b13a38c36a8276a39899b4096efc217e82568fe3842f8b34bb025 mmui.so /jci/mmui/svcjcimmui.so
c94446b8c6e5bde79607514d3eb41036a3f56914d2d3f418605110bc250be0d0 mmui.xml /jci/mmui/mmui_config.xml
acf24ffd3719a29d2b4eefe80855ef6f164852fe3464858d07ca2d956395d302 uia.so /jci/mmui/uia/libjciuiasystem.so
b0e116b941f29078ced19b864a1b888cf76d8bc3e4974af081efca4693e5c420 index.html /jci/gui/index.html
985cbcbeb1dedf11b76f61ffa1224e43165f80d8eb9c8d5d853d118d2eec3432 system-app.js /jci/gui/apps/system/js/systemApp.js
54c1e498bd430a59dccd3e204661d48864d093e6aa51999a5c35bccaa0801690 base-app.js /jci/gui/framework/js/BaseApp.js
ORIGINALS
}

firmware_dependencies() {
    original_files
    printf '%s\n' '0c32ab6dc6833d287d363c3ff63998450cce97121ace994930276c4adb28474b manager.so /jci/lib/libjciuiamgr.so'
}

firmware_guard() {
    test "$(id -u)" = 0 || fail root_required
    awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_55.00.750\""{v++}
         $0=="JCI_SW_VER_PATCH=\"B\""{p++}
         $0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++}
         END{exit !(v==1&&p==1&&f==1)}' /jci/version.ini || fail unsupported_firmware
    test "$(md5sum < /jci/gui/framework/js/GuiFramework.js)" = 'e90530cdb9b05922bdcaade8757ea1f9  -' || fail unsupported_framework
    test "$(md5sum < /jci/lvds/lvds_service)" = '6bb6b50fb459f3a152b6528efbf5a95c  -' || fail unsupported_display
    awk '$1=="/dev/mmcblk0p2"&&$2=="/tmp/mnt/data_persist"&&$3=="relfs"{
        n++;split($4,a,",");for(i in a)if(a[i]=="rw")rw++} END{exit !(n==1&&rw==1)}' /proc/mounts || fail persistence_unavailable
    for path in /tmp /tmp/mnt /tmp/mnt/data_persist; do directory "$path" || fail invalid_persistence_path; done
}

native_guard() {
    test "$(md5sum < /jci/lib/libjciuiamgr.so)" = '8ce49f8bc9833c48a3a89e5c4c683ddc  -' || fail unsupported_manager
}

originals_verify() {
    local digest name target
    private_dir "$D/originals" || return 1
    original_files | while read -r digest name target; do
        file "$D/originals/$name" && test "$(sha "$D/originals/$name")" = "$digest" || exit 1
    done
}

originals_save() {
    local work
    if ! absent "$D/originals"; then originals_verify || fail originals_changed; return; fi
    work=$(mktemp -d "$D/.originals-XXXXXX") || fail backup_create_failed
    original_files | while read -r digest name target; do
        file "$target" && test "$(sha "$target")" = "$digest" || fail unsupported_original
        cp "$target" "$work/$name" && chmod 600 "$work/$name" || fail backup_copy_failed
        test "$(sha "$work/$name")" = "$digest" || fail backup_verification_failed
        flush f "$work/$name"
    done || fail backup_failed
    flush d "$work"
    mv "$work" "$D/originals" || fail backup_publish_failed
    flush d "$D"
    originals_verify || fail originals_changed
}

compose() (
    set -eu
    # $1 is the public package's content ID. Original bytes stay on this unit.
    local package=$D/packages/$1 work name digest
    hex "$1" 64 && verify_manifest "$package" && originals_verify || fail compose_inputs_invalid
    if ! absent "$D/composed/$1"; then verify_manifest "$D/composed/$1" || fail composed_files_changed; return; fi
    work=$(mktemp -d "$D/composed/.new-XXXXXX") || fail compose_create_failed
    cp "$D/originals/uia.so" "$work/uia.so" || fail compose_copy_failed
    dd if="$package/native.bin" of="$work/uia.so" bs=1 seek=297984 conv=notrunc 2>/dev/null || fail compose_patch_failed
    dd if="$package/branch.bin" of="$work/uia.so" bs=1 seek=32468 conv=notrunc 2>/dev/null || fail compose_patch_failed
    dd if="$package/sizes.bin" of="$work/uia.so" bs=1 seek=68 conv=notrunc 2>/dev/null || fail compose_patch_failed
    cp "$D/originals/mmui.so" "$work/mmui.so" || fail compose_copy_failed
    dd if="$package/mmui-path.bin" of="$work/mmui.so" bs=1 seek=16184 conv=notrunc 2>/dev/null || fail compose_patch_failed
    dd if="$package/mmui-sizes.bin" of="$work/mmui.so" bs=1 seek=68 conv=notrunc 2>/dev/null || fail compose_patch_failed
    dd if="$package/mmui-length.bin" of="$work/mmui.so" bs=1 seek=10860 conv=notrunc 2>/dev/null || fail compose_patch_failed
    dd if="$package/mmui-pointer.bin" of="$work/mmui.so" bs=1 seek=12796 conv=notrunc 2>/dev/null || fail compose_patch_failed
    sed 's@name="system" libpath="/jci/mmui/uia/" lib="libjciuiasystem.so"@name="system" libpath="/tmp/open-connect/feature/" lib="uia.so"@' \
        "$D/originals/mmui.xml" > "$work/mmui.xml" || fail compose_xml_failed
    # The supported original has CRLF line endings. Insert authored JS bytes.
    dd if="$D/originals/system-app.js" bs=1 count=16132 2>/dev/null > "$work/system-app.js" || fail compose_javascript_failed
    sed 's/$/\r/' "$package/intro.js" > "$work/intro" || fail compose_javascript_failed
    test "$(wc -c < "$work/intro")" -eq 602 || fail javascript_fragment_changed
    head -c 600 "$work/intro" >> "$work/system-app.js" || fail compose_javascript_failed
    rm "$work/intro" || fail compose_cleanup_failed
    dd if="$D/originals/system-app.js" bs=1 skip=16132 2>/dev/null >> "$work/system-app.js" || fail compose_javascript_failed
    test "$(sha "$work/system-app.js")" = 28413b8bbdfc21bf1e63dd8c4a25f8229f688f6a3f6d62c3ad651c039f00f3cc || fail javascript_composition_failed
    for setting in on off; do
        awk -v route="$package/system-route.js" -v selected="$setting" '
            /<head>/{print;print "        <base href=\"file:///jci/gui/\" />";print "        <meta name=\"open-connect-token\" content=\"@TOKEN@\" />";next}
            /var utility = new Utility\(\);/{print;if(selected=="on"){while((r=getline line < route)>0)print line;if(r<0)exit 1;close(route)};next}
            /<\/body>/{print "        <script src=\"file:///tmp/open-connect/runtime/runtime.js\" type=\"text/javascript\"></script>"}
            {print}
        ' "$D/originals/index.html" > "$work/index-$setting.html" || fail compose_index_failed
        sed 's@args="-u /jci/gui/index.html"@args="-u /tmp/open-connect/feature/index.html"@' "$D/originals/sm.conf" > "$work/sm-$setting.conf" || fail compose_config_failed
    done
    sed 's@name="jciMMUI" path="/jci/mmui/svcjcimmui.so"@name="jciMMUI" path="/tmp/open-connect/feature/mmui.so"@' \
        "$work/sm-on.conf" > "$work/sm-on.next" || fail compose_config_failed
    mv "$work/sm-on.next" "$work/sm-on.conf" || fail compose_config_failed
    awk -v hook="$package/startup-hook.sh" '
        {print}
        $0=="        echo $MESSAGE_NORMALMODE" {while((r=getline line < hook)>0)print line;if(r<0)exit 1;close(hook);n++}
        END{if(n!=1)exit 1}
    ' "$D/originals/autostart" > "$work/autostart" || fail startup_anchor_missing
    sh -n "$work/autostart" || fail startup_syntax
    for name in autostart uia.so mmui.so mmui.xml system-app.js index-on.html index-off.html sm-on.conf sm-off.conf; do
        chmod 600 "$work/$name" || fail compose_mode_failed
        digest=$(sha "$work/$name") && hex "$digest" 64 || fail compose_hash_failed
        printf '%s  %s\n' "$digest" "$name" || fail compose_manifest_failed
        flush f "$work/$name"
    done > "$work/files.sha256" || fail compose_manifest_failed
    chmod 600 "$work/files.sha256" || fail compose_mode_failed
    flush f "$work/files.sha256"; flush d "$work"
    mv "$work" "$D/composed/$1" || fail compose_publish_failed
    flush d "$D/composed"
)

root_mode() {
    awk '$1=="/dev/ffx01p1"&&$2=="/"&&$3=="relfs"{n++;m=$4}
         END{if(n!=1)exit 1;print m}' /proc/mounts
}
cleanup_mount_guard() {
    awk -v dir="$D" '$2==dir || index($2,dir "/")==1 {exit 1}' /proc/mounts
}
startup_staging_guard() {
    local path
    # Random staging names from an older release are not evidence of ownership.
    # Refuse cleanup rather than erase unknown files or report complete removal.
    for path in /usr/bin/.open-connect-*; do absent "$path" || return 1; done
}
remount() {
    timeout -t 8 -s TERM /bin/busybox mount -i -n -t relfs -o "remount,$1,noatime" /dev/ffx01p1 / &&
        test "$(root_mode)" = "$1,noatime"
}
startup_publish() (
    set -eu
    local source=$1 mode=$2 expected=$3 expected_mode=$4 work identity=
    hex "$R_REV" 32 && file "$source" || fail invalid_startup_plan
    # The durable pending revision names this exact staging file across retries.
    work=/usr/bin/.open-connect-$R_REV
    case "$(root_mode)" in ro,noatime|rw,noatime) ;; *) fail root_mount_changed;; esac
    stage_matches() {
        local size prefix
        file "$work" || return 1
        size=$(stat -c %s "$work") || return 1
        test "$size" -le "$(stat -c %s "$source")" || return 1
        prefix=$(head -c "$size" "$source" | openssl dgst -sha256) || return 1
        test "$(sha "$work")" = "${prefix##* }"
    }
    # An already-written target still needs the directory flush and read-only
    # restoration if a preceding process was killed between those steps.
    finish() {
        local result=$?
        trap - EXIT HUP INT TERM
        if ! absent "$work" && test -n "$identity"; then
            if test "$(stat -c '%d:%i' "$work")" = "$identity" && stage_matches; then
                remount rw && rm "$work" && "$P/flush" d /usr/bin || result=1
            else result=1; fi
        fi
        remount ro || result=1
        exit "$result"
    }
    trap finish EXIT
    trap 'exit 1' HUP INT TERM
    file "$AUTOSTART" && test "$(sha "$AUTOSTART")" = "$expected" &&
        test "$(stat -c '%a:%u:%g' "$AUTOSTART")" = "$expected_mode" || fail startup_changed
    if ! absent "$work"; then
        stage_matches || fail startup_stage_changed
        identity=$(stat -c '%d:%i' "$work") || fail startup_stage_changed
    fi
    if test "$expected" != "$(sha "$source")" || test "$expected_mode" != "$mode"; then
        remount rw || fail remount_failed
        if absent "$work"; then
            (set -C; : > "$work") || fail startup_stage_failed
            identity=$(stat -c '%d:%i' "$work") || fail startup_stage_failed
        fi
        metadata "$mode" || fail invalid_startup_metadata
        cp "$source" "$work" && chown "$S_UID:$S_GID" "$work" && chmod "$S_MODE" "$work" || fail startup_copy_failed
        test "$(sha "$work")" = "$(sha "$source")" || fail startup_copy_changed
        flush f "$work"
        file "$AUTOSTART" && test "$(sha "$AUTOSTART")" = "$expected" &&
            test "$(stat -c '%a:%u:%g' "$AUTOSTART")" = "$expected_mode" || fail startup_changed
        mv -f "$work" "$AUTOSTART" || fail startup_rename_failed
    fi
    flush f "$AUTOSTART"
    flush d /usr/bin
)

nvram_read() { sh "$P/touch.sh" read; }
nvram_change() { sh "$P/touch.sh" change "$1" "$2" >/dev/null; }

dependency_path() {
    local scope=${1%%/*} name=${1#*/} id folder
    test "$scope/$name" = "$1" && test -n "$name" || return 1
    case "$name" in .|..|*[!a-zA-Z0-9.-]*) return 1;; esac
    case "$scope" in
        root) firmware_dependencies | awk -v n="$name" '$2==n && n!="autostart"{print $3;found++} END{if(found!=1)exit 1}';;
        package-*) id=${scope#package-}; folder=packages;;
        composed-*) id=${scope#composed-}; folder=composed;;
        *) return 1;;
    esac
    test "$scope" = root && return
    hex "$id" 64 && private_dir "$D/$folder/$id" || return 1
    printf '%s\n' "$D/$folder/$id/$name"
}

dependencies_capture() {
    local package=$1 digest name target folder path
    firmware_dependencies | while read -r digest name target; do
        test "$name" != autostart || continue
        file "$target" || exit 1
        digest=$(sha "$target") && hex "$digest" 64 || exit 1
        printf '%s  root/%s\n' "$digest" "$name" || exit 1
    done || return 1
    test "$package" != - || return 0
    hex "$package" 64 || return 1
    for folder in package composed; do
        case "$folder" in package) path=$D/packages/$package;; composed) path=$D/composed/$package;; esac
        private_dir "$path" || return 1
        # Pin the private package and composed bytes until the transaction ends.
        for target in "$path"/*; do
            name=${target##*/}
            case "$name" in .|..|*[!a-zA-Z0-9.-]*) return 1;; esac
            file "$target" || return 1
            digest=$(sha "$target") && hex "$digest" 64 || return 1
            printf '%s  %s-%s/%s\n' "$digest" "$folder" "$package" "$name" || return 1
        done
    done
}

stock_dependencies() {
    firmware_dependencies | while read -r digest name target; do
        test "$name" != autostart || continue
        file "$target" && test "$(sha "$target")" = "$digest" || exit 1
    done
}

package_save() (
    set -eu
    local work digest name extra id
    verify_manifest "$P" || fail damaged_source_package
    work=$(mktemp -d "$D/packages/.new-XXXXXX") || fail package_create_failed
    while read -r digest name extra; do
        # INSTANCE is private data added below, never supplied by a USB package.
        test "$name" != INSTANCE || continue
        cp "$P/$name" "$work/$name" || fail package_copy_failed
        chmod 600 "$work/$name" || fail package_mode_failed
        case "$name" in api|flush) chmod 700 "$work/$name" || fail package_mode_failed;; esac
        test "$(sha "$work/$name")" = "$digest" || fail package_copy_changed
        printf '%s  %s\n' "$digest" "$name" || fail package_manifest_failed
        flush f "$work/$name"
    done < "$P/files.sha256" > "$work/files.sha256" || fail package_manifest_failed
    uuid > "$work/INSTANCE" || fail package_instance_failed
    digest=$(sha "$work/INSTANCE") && hex "$digest" 64 || fail package_hash_failed
    printf '%s  INSTANCE\n' "$digest" >> "$work/files.sha256" || fail package_manifest_failed
    flush f "$work/INSTANCE"; flush f "$work/files.sha256"; flush d "$work"
    id=$(sha "$work/files.sha256") && hex "$id" 64 || fail package_hash_failed
    absent "$D/packages/$id" || fail package_collision
    mv "$work" "$D/packages/$id" || fail package_publish_failed
    flush d "$D/packages"
    printf '%s\n' "$id"
)
