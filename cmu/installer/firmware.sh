#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Compose private launch files from this unit's verified originals. All code
# fragments and native replacement bytes are authored/compiled in the package.

original_files() {
    cat <<'ORIGINALS'
a8d019650c2a17a50b5ff39435f916c2cbeb3556af128fd913b9714b380e06bd autostart /usr/bin/autostart
fa3484d7c644393ab6cb083990e483201129a207e7755459296dde8ec82a4d84 sm.conf /jci/sm/sm.conf
92034449e76689b995fcd369d584f441829a0ee6e8d74c858cd92f4049f7b27d sm_WCP.conf /jci/sm/sm_WCP.conf
2c66145fe9c76cbbed471b6e190c57837c72ae5a3cf8f750c6c87a689ded20da board.sh /jci/scripts/get_board_type.sh
034d5339116aa2f2da81ec6caaf3426081c452544f3b527af3a2121b7a7e0bca mmui.so /jci/mmui/svcjcimmui.so
ef9550fa084a34b6a997d2e488c41e50667b409fa2e6ad9c896429c74dc705f0 mmui.xml /jci/mmui/mmui_config.xml
32431c6b74c8ba531fcc10c50748075416e0f7dc1a3f903f182d816a0f3f5fc2 uia.so /jci/mmui/uia/libjciuiasystem.so
b0e116b941f29078ced19b864a1b888cf76d8bc3e4974af081efca4693e5c420 index.html /jci/gui/index.html
23106b04bd6bad514dd879b217a34a0f0289d58f86a0ae022488be6a022ca8e1 system-app.js /jci/gui/apps/system/js/systemApp.js
a83dd588b54531475024b7cd048be1d0e11556abd68bbbcc334cc5ede7534cd1 settings-app.js /jci/gui/apps/syssettings/js/syssettingsApp.js
1489e544e483c878fa000be378a3bbb92dcc9965aadc5029a58f3fc1147337da base-app.js /jci/gui/framework/js/BaseApp.js
ORIGINALS
}

firmware_dependencies() {
    original_files
    printf '%s\n' '1d2c6c1d583493a5b1128a52a75937c6bed720117b1344168bc9b27df6893e29 manager.so /jci/lib/libjciuiamgr.so'
    printf '%s\n' \
        '9f1811e2d9a905ba9060a9c20b8d91c18aaa5c079512e3261b51cf0114fc857b device-master.xml /etc/devmgr_config_master.xml' \
        '0160354861d0dddf09f05dc69df95f14be074de706a4d7656166666d587439d9 eem.so /jci/vbs/modules/libjcimod_eem.so' \
        '88d6291d74fe993536ec724064b8ccfbc133b2341282b93cfc7fb2927fbbc563 device-manager.so /jci/devicemanager/libdevicemanager.so'
    printf '%s\n' \
        '0b205e203510bef6d20b910f31c88a7f9c141048c41b1704eed20b880d67ac82 rungetty /usr/bin/rungetty' \
        'f83f7661e0ba41da379936ba319f40e228cd14d470c3081f19d8fbec8297a195 sshd /usr/sbin/sshd' \
        'b735d7dd9a9a45badf18b2a9d0e32ca791a4e582400e57378a27b2a2d92ae9c9 ssh-keygen /usr/bin/ssh-keygen'
    printf '%s\n' \
        'ca2889f7cb0361610e57b43004572fdd53c00d1d3003409bb92c744fcb253f70 framework.js /jci/gui/framework/js/GuiFramework.js' \
        '19a56b9e7b9f7399b152dbc7e8bd8de3fa01f154e45e8981becec6e96d3f70eb lvds-service /jci/lvds/lvds_service'
}

firmware_guard() {
    test "$(id -u)" = 0 || fail root_required
    awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_74.00.324\""{v++}
         $0=="JCI_SW_VER_PATCH=\"A\""{p++}
         $0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++}
         END{exit !(v==1&&p==1&&f==1)}' /jci/version.ini || fail unsupported_firmware
    test "$(md5sum < /jci/gui/framework/js/GuiFramework.js)" = '0228bd6330c544eb500dacd7b00a9e79  -' || fail unsupported_framework
    test "$(md5sum < /jci/lvds/lvds_service)" = '1d3e74362d4a97814a9f0fb316ff583f  -' || fail unsupported_display
    awk '$1=="/dev/mmcblk0p2"&&$2=="/tmp/mnt/data_persist"&&$3=="relfs"{
        n++;split($4,a,",");for(i in a)if(a[i]=="rw")rw++} END{exit !(n==1&&rw==1)}' /proc/mounts || fail persistence_unavailable
    for path in /tmp /tmp/mnt /tmp/mnt/data_persist; do directory "$path" || fail invalid_persistence_path; done
    # Maintenance must be able to finish a known publication interrupted while
    # root was writable. Boot selection separately requires the strict RO mode.
    boot_mount_guard maintenance || fail invalid_boot_mounts
}

boot_mount_guard() {
    awk -v writable="${1:-no}" '
        $2=="/tmp/mnt/data_persist/open-connect" || index($2,"/tmp/mnt/data_persist/open-connect/")==1 ||
        $2=="/tmp/open-connect" || index($2,"/tmp/open-connect/")==1 {bad=1}
        $2=="/" {
            if($1=="rootfs" && $3=="rootfs" && $4=="rw" && root==0 && rootfs==0)rootfs++
            else if($1=="/dev/ffx01p1" && $3=="relfs" &&
                    ($4=="ro,noatime" || (writable=="maintenance" && $4=="rw,noatime")))root++
            else bad=1
        }
        $2=="/tmp/mnt/data_persist" {
            if($1!="/dev/mmcblk0p2" || $3!="relfs")bad=1
            data++;split($4,a,",");for(i in a)if(a[i]=="rw")rw++
        }
        END {exit bad || root!=1 || data!=1 || rw!=1}
    ' /proc/self/mounts
}

native_dependency_guard() { test "$1" = 1d2c6c1d583493a5b1128a52a75937c6bed720117b1344168bc9b27df6893e29; }
native_guard() { native_dependency_guard "$(sha /jci/lib/libjciuiamgr.so)" || fail unsupported_manager; }

factory_wireless() (
    # Follow the verified OEM hardware branch, never our rendered RAM flags.
    file /jci/scripts/get_board_type.sh || exit 1
    test "$(sha /jci/scripts/get_board_type.sh)" = 2c66145fe9c76cbbed471b6e190c57837c72ae5a3cf8f750c6c87a689ded20da || exit 1
    result=0
    PATH=/usr/bin:/bin:/usr/sbin:/sbin sh /jci/scripts/get_board_type.sh >/dev/null 2>&1 || result=$?
    test "$result" = 2
)

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

base_ui_files() {
    # Read-only sources: these are never replaced or added to uninstall targets.
    cat <<'BASE_UI'
83f5a71617f34427bb903c90ac5df53ed4e0e6437cca8a8bdb509909a324ba3a log-defaults.js /jci/gui/common/js/logDefaults.js
BASE_UI
}

base_ui_inputs_verify() {
    local digest name target
    base_ui_files | while read -r digest name target; do
        file "$target" && test "$(sha "$target")" = "$digest" || exit 1
    done
}

compose_native() {
    local package=$1 original=$2 target=$3 destination source extra
    # Retain all original virtual addresses. The exact v74 ELF has no file
    # padding after RX: move its complete file tail by one 0x8000 alignment.
    # LLD emits code/relocations and replacement metadata words; this only
    # composes those bytes with the unit's already hash-verified original.
    head -c 456604 "$original" > "$target" || return 1
    dd if=/dev/zero bs=32768 count=1 2>/dev/null >> "$target" || return 1
    tail -c 217443 "$original" >> "$target" || return 1
    dd if="$package/native.bin" of="$target" bs=1 seek=456604 conv=notrunc 2>/dev/null || return 1
    dd if="$package/branch.bin" of="$target" bs=1 seek=49076 conv=notrunc 2>/dev/null || return 1
    dd if="$package/sizes.bin" of="$target" bs=1 seek=68 conv=notrunc 2>/dev/null || return 1
    while read -r destination source extra; do
        case "$destination" in ''|*[!0-9]*) return 1;; esac
        case "$source" in ''|*[!0-9]*) return 1;; esac
        test -z "$extra" || return 1
        dd if="$package/layout.bin" of="$target" bs=1 skip="$source" seek="$destination" count=4 conv=notrunc 2>/dev/null || return 1
    done < "$package/layout.txt"
}

compose() (
    set -eu
    # $1 is the public package's content ID. Original bytes stay on this unit.
    local package=$D/packages/$1 work name digest
    hex "$1" 64 && verify_manifest "$package" && originals_verify || fail compose_inputs_invalid
    if ! absent "$D/composed/$1"; then verify_manifest "$D/composed/$1" || fail composed_files_changed; return; fi
    work=$(mktemp -d "$D/composed/.new-XXXXXX") || fail compose_create_failed
    compose_native "$package" "$D/originals/uia.so" "$work/uia.so" || fail compose_patch_failed
    cp "$D/originals/mmui.so" "$work/mmui.so" || fail compose_copy_failed
    dd if="$package/mmui-path.bin" of="$work/mmui.so" bs=1 seek=15812 conv=notrunc 2>/dev/null || fail compose_patch_failed
    dd if="$package/mmui-sizes.bin" of="$work/mmui.so" bs=1 seek=68 conv=notrunc 2>/dev/null || fail compose_patch_failed
    dd if="$package/mmui-length.bin" of="$work/mmui.so" bs=1 seek=7112 conv=notrunc 2>/dev/null || fail compose_patch_failed
    dd if="$package/mmui-count-pointer.bin" of="$work/mmui.so" bs=1 seek=7368 conv=notrunc 2>/dev/null || fail compose_patch_failed
    dd if="$package/mmui-length.bin" of="$work/mmui.so" bs=1 seek=10688 conv=notrunc 2>/dev/null || fail compose_patch_failed
    dd if="$package/mmui-pointer.bin" of="$work/mmui.so" bs=1 seek=12540 conv=notrunc 2>/dev/null || fail compose_patch_failed
    sed 's@name="system" libpath="/jci/mmui/uia/" lib="libjciuiasystem.so"@name="system" libpath="/tmp/open-connect/feature/" lib="uia.so"@' \
        "$D/originals/mmui.xml" > "$work/mmui.xml" || fail compose_xml_failed
    # The supported original has CRLF line endings. Insert authored JS bytes.
    dd if="$D/originals/system-app.js" bs=1 count=17463 2>/dev/null > "$work/system-app.js" || fail compose_javascript_failed
    sed 's/$/\r/' "$package/intro.js" > "$work/intro" || fail compose_javascript_failed
    test "$(wc -c < "$work/intro")" -eq 2150 || fail javascript_fragment_changed
    head -c 2148 "$work/intro" >> "$work/system-app.js" || fail compose_javascript_failed
    rm "$work/intro" || fail compose_cleanup_failed
    dd if="$D/originals/system-app.js" bs=1 skip=17463 2>/dev/null >> "$work/system-app.js" || fail compose_javascript_failed
    test "$(sha "$work/system-app.js")" = 61cb4085195bcc1ea6f0efdd01ab691a10b9f9cee45d32e8a78b4410c9b07f40 || fail javascript_composition_failed
    for setting in on off; do
        awk -v route="$package/system-route.js" -v selected="$setting" '
            /<head>/{
                print;print "        <base href=\"file:///jci/gui/\" />"
                print "        <meta name=\"open-connect-token\" content=\"@TOKEN@\" />"
                print "        <meta name=\"open-connect-version\" content=\"@VERSION@\" />"
                print "        <meta name=\"open-connect-notice\" content=\"@NOTICE@\" />"
                next
            }
            /var utility = new Utility\(\);/{print;if(selected=="on"){while((r=getline line < route)>0)print line;if(r<0)exit 1;close(route)};next}
            /<\/body>/{
                print "        <script src=\"file:///tmp/open-connect/feature/runtime.js\" type=\"text/javascript\"></script>"
            }
            {print}
        ' "$D/originals/index.html" > "$work/index-$setting.html" || fail compose_index_failed
        for profile in normal wcp; do
            if test "$profile" = normal; then name=sm.conf; else name=sm_WCP.conf; fi
            sed 's@args="-u /jci/gui/index.html"@args="-u /tmp/open-connect/feature/index.html"@' \
                "$D/originals/$name" > "$work/sm-$profile-$setting.conf" || fail compose_config_failed
            if test "$setting" = on; then
                sed 's@name="jciMMUI" path="/jci/mmui/svcjcimmui.so"@name="jciMMUI" path="/tmp/open-connect/feature/mmui.so"@' \
                    "$work/sm-$profile-$setting.conf" > "$work/sm.next" || fail compose_config_failed
                mv "$work/sm.next" "$work/sm-$profile-$setting.conf" || fail compose_config_failed
            fi
        done
    done
    file "$package/startup-hook.sh" && test -s "$package/startup-hook.sh" &&
        file "$package/startup-join.sh" && test -s "$package/startup-join.sh" || fail startup_fragment_missing
    awk -v hook="$package/startup-hook.sh" -v join="$package/startup-join.sh" '
        $0=="                $(/jci/scripts/get_board_type.sh)" && previous=="                sleep 1" {
            if(n!=1)exit 1
            while((r=getline line < join)>0){print line;join_lines++}
            if(r<0)exit 1
            close(join);joined++
        }
        {print}
        $0=="        echo $MESSAGE_NORMALMODE" {while((r=getline line < hook)>0){print line;hook_lines++};if(r<0)exit 1;close(hook);n++}
        {previous=$0}
        END{if(n!=1 || joined!=1 || !hook_lines || !join_lines)exit 1}
    ' "$D/originals/autostart" > "$work/autostart" || fail startup_anchor_missing
    sh -n "$work/autostart" || fail startup_syntax
    for name in autostart uia.so mmui.so mmui.xml system-app.js index-on.html index-off.html \
        sm-normal-on.conf sm-normal-off.conf sm-wcp-on.conf sm-wcp-off.conf; do
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

native_log_inputs_verify() {
    file /config/common/log/settings.txt &&
        test "$(sha /config/common/log/settings.txt)" = 8c95ceaf213af1086e913fd78b69c9b00869c848375c3b40de3c36166d5d3ea0 &&
        file /jci/lib/libjcicommon.so &&
        test "$(sha /jci/lib/libjcicommon.so)" = 637cc53cd0621ec7fed24be2519b3e208191dd22954d2442d70e854413874b0d
}

native_log_prepare() {
    # Prepare only: no external logging policy becomes visible here.
    local folder
    LOG_STAGE=
    bit "$1" || return 1
    test "$1" = 1 || return 0
    native_log_inputs_verify || return 1
    for folder in /tmp/common /tmp/common/log; do
        if absent "$folder"; then mkdir -m 755 "$folder" || return 1; fi
        test -d "$folder" && test ! -L "$folder" &&
            test "$(readlink -f "$folder")" = "$folder" || return 1
    done
    absent /tmp/common/log/settings.txt || return 1
    LOG_STAGE=$(mktemp /tmp/common/log/.open-connect-log-XXXXXX) || return 1
    printf 'COMMON_LOG_LEVEL=Warn\n' > "$LOG_STAGE" && chmod 644 "$LOG_STAGE"
}

native_log_commit() {
    test -n "$LOG_STAGE" || return 0
    "${1:-$P/flush}" l "$LOG_STAGE" /tmp/common/log/settings.txt
}

native_log_discard() {
    # The retained hardlink identifies our publication, never another provider.
    if test -n "${LOG_STAGE:-}"; then
        if test -f /tmp/common/log/settings.txt && test ! -L /tmp/common/log/settings.txt &&
            test "$(stat -c '%d:%i' "$LOG_STAGE")" = "$(stat -c '%d:%i' /tmp/common/log/settings.txt)"; then
            rm /tmp/common/log/settings.txt || return 1
        fi
        rm -f "$LOG_STAGE" || return 1
        LOG_STAGE=
    fi
}

# Standalone callers retain the original one-shot operation. Boot uses the
# prepare/commit functions in its own signal-protected final publication.
native_log_config() (
    set -eu
    LOG_STAGE=
    trap 'test -z "$LOG_STAGE" || rm -f "$LOG_STAGE" || :' EXIT
    native_log_prepare "$1" && native_log_commit
)

base_read_ahead() (
    # Diagnostic-only after successful selection; never a durable setting.
    set -eu
    local block=/sys/devices/virtual/block/ffx01 value
    directory "$block" && directory "$block/queue" &&
        test "$(readlink -f "$block")" = "$block" &&
        file "$block/dev" && test "$(cat "$block/dev")" = 253:16 &&
        file "$block/queue/read_ahead_kb" &&
        test "$(stat -c '%a:%u:%g' "$block/queue/read_ahead_kb")" = "644:$(id -u):$(id -g)" || exit 1
    value=$(cat "$block/queue/read_ahead_kb")
    case "$value" in 4) ;; 128) printf '4\n' > "$block/queue/read_ahead_kb";; *) exit 1;; esac
    test "$(cat "$block/queue/read_ahead_kb")" = 4
)

boot_render_profiles() {
    # This function runs from the verified target package, before prepare.
    local destination=$1 config=$2 source setting=off profile logging_digest
    config_decode "$config" && test "$S_SCHEMA" = OC2 &&
        test "$P" = "$D/packages/$S_PACKAGE" || return 1
    source=$D/composed/$S_PACKAGE
    private_dir "$source" && verify_manifest "$source" || return 1
    test "$S_WARNING" != 1 || setting=on
    if test "$S_BASE" = 1; then
        base_ui_inputs_verify && file "$P/base-logging.js" || return 1
        logging_digest=$(awk '$2=="base-logging.js"{n++;print $1}END{exit n!=1}' "$P/files.sha256") || return 1
        test "$(sha "$P/base-logging.js")" = "$logging_digest" || return 1
    fi
    for profile in normal wcp; do
        awk -v operation=compose -v catalog="$P/services.tsv" -v catalog_bytes="$(wc -c < "$P/services.tsv")" -v input="$config" \
            -v input_bytes="$(wc -c < "$config")" -f "$P/preferences.awk" -f "$P/sm-profile.awk" \
            "$source/sm-$profile-$setting.conf" > "$destination/sm-$profile.conf" || return 1
    done
    # Keep the OEM script available through compatible-media purge and browser
    # reload. The authored override lives inside the already RAM-owned index.
    awk -v base="$S_BASE" -v logger="$P/base-logging.js" '
        base=="1" && /src="common\/js\/logDefaults[.]js"/ {
            print
            print "        <script type=\"text/javascript\">"
            while((r=getline line < logger)>0)print line
            if(r<0)exit 1
            close(logger)
            print "        </script>"
            logging++;next
        }
        {print}
        END {if(base=="1" && logging!=1)exit 1}
    ' "$source/index-$setting.html" > "$destination/index.html" || return 1
    awk '{n+=gsub(/@TOKEN@/,"@TOKEN@")}END{exit n!=1}' "$destination/index.html"
}

boot_plan_inputs() {
    local work=$1 snapshot=$2 manifest=$3 digest name target extra
    shift 3
    printf 'OCBP1|%s|%s\n' "$R_BASE" "$S_PACKAGE"
    while read -r digest name extra; do
        test -z "$extra" && hex "$digest" 64 || return 1
        target=$(dependency_path "$name") && file "$target" || return 1
        printf '%s|%s|%s\n' "$name" "$target" "$digest"
    done < "$D/snapshots/$snapshot/dependencies"
    for name in "$@"; do
        digest=$(printf '%s\n' "$manifest" | awk -v name="$name" '$2==name{n++;print $1}END{exit n!=1}') || return 1
        hex "$digest" 64 || return 1
        printf 'current/%s|@/%s|%s\n' "$name" "$name" "$digest"
    done
    while read -r digest name extra; do
        printf 'baseline/%s|%s/snapshots/%s/%s|%s\n' "$name" "$D" "$R_BASE" "$name" "$digest"
    done < "$D/snapshots/$R_BASE/files.sha256"
    printf 'baseline/files.sha256|%s/snapshots/%s/files.sha256|%s\n' "$D" "$R_BASE" "$R_BASE"
    printf 'target/autostart|%s|%s\n' "$AUTOSTART" "$(sha "$work/autostart")"
    if test "${S_SELECTOR_HASH:--}" != -; then
        printf 'target/boot-select|/usr/bin/open-connect-boot-select|%s\n' "$S_SELECTOR_HASH"
    fi
    for target in /jci/version.ini; do
        printf 'guard/%s|%s|%s\n' "${target##*/}" "$target" "$(sha "$target")"
    done
    if test "$S_BASE" = 1; then
        native_log_inputs_verify || return 1
        for name in settings.txt libjcicommon.so; do
            case "$name" in
                settings.txt) target=/config/common/log/settings.txt;;
                libjcicommon.so) target=/jci/lib/libjcicommon.so;;
            esac
            printf 'base/%s|%s|%s\n' "$name" "$target" "$(sha "$target")"
        done
        base_ui_files | while read -r digest name target; do
            file "$target" && test "$(sha "$target")" = "$digest" || exit 1
            printf 'base/%s|%s|%s\n' "$name" "$target" "$digest"
        done || return 1
    fi
    if test "$S_ACCESS" = true; then
        printf 'target/runlogin|/usr/bin/runlogin|%s\n' "$(sha "$work/runlogin")"
        printf 'target/sshd.conf|/etc/ssh/sshd_config|%s\n' "$(sha "$work/sshd.conf")"
        if test "$S_LOGIN_INODE" != -; then
            target=/usr/bin/.open-connect-runlogin-$S_LOGIN_INODE
            digest=-
            if ! absent "$target"; then digest=$(sha "$D/snapshots/$R_BASE/runlogin") || return 1; fi
            printf 'hold/runlogin|%s|%s\n' "$target" "$digest"
        fi
        if test "$S_KEY" != -; then
            access_key_verify "$S_KEY" || return 1
            printf 'key/owner|%s/keys/%s.cmu|%s\n' "$D" "$S_KEY" "$S_KEY"
        fi
    fi
}

boot_snapshot_seal() (
    # Serialization and rendering must belong to the snapshot's package,
    # including an old Set recovered by a newer maintenance USB session.
    set -eu
    local snapshot=$1 package target
    snapshot_read "$snapshot" || fail invalid_boot_snapshot
    package=$S_PACKAGE
    if test "$package" = -; then printf '%s\n' "$snapshot"; exit 0; fi
    test "$package" = "$R_BACKEND" || fail invalid_boot_package
    target=$(package_programs "$package" state.sh firmware.sh access.sh transaction.sh boot-select VERSION) || fail invalid_boot_package
    if test "$S_SCHEMA" = dev9; then
        test "$(cat "$target/VERSION")" = 0.3.0-dev.9 && absent "$target/preferences.awk" || fail unsupported_boot_package
        sh -c 'set -eu; D=$1; P=$2; R_BACKEND=$3; R_BASE=$4; AUTOSTART=$5;
            . "$P/state.sh"; . "$P/firmware.sh"; . "$P/access.sh"; . "$P/transaction.sh";
            boot_snapshot_seal "$6"' seal "$D" "$target" "$R_BACKEND" "$R_BASE" "$AUTOSTART" "$snapshot"
    else
        test "$S_SCHEMA" = OC2 || fail invalid_boot_package
        sh -c 'set -eu; D=$1; P=$2; R_BACKEND=$3; R_BASE=$4; AUTOSTART=$5;
            . "$P/state.sh"; . "$P/firmware.sh"; . "$P/access.sh"; . "$P/transaction.sh";
            _boot_snapshot_seal "$6"' seal "$D" "$target" "$R_BACKEND" "$R_BASE" "$AUTOSTART" "$snapshot"
    fi
)

_boot_snapshot_seal() (

    # Reconciliation has already applied and fully verified the after-state.
    # Seal a new immutable snapshot before record can call it current. A cut
    # leaves the existing prepared transaction recoverable, never a side flag.
    set -eu
    local snapshot=$1 package helper work name digest magic base backend manifest expected
    snapshot_read "$snapshot" || fail invalid_boot_snapshot
    package=$S_PACKAGE
    if test "$package" = - || absent "$D/packages/$package/boot-select"; then
        printf '%s\n' "$snapshot"; exit 0
    fi
    test "$package" = "$R_BACKEND" && test "$S_SCHEMA" = OC2 || fail invalid_boot_package
    P=$D/packages/$package
    private_dir "$P" && test "$(sha "$P/files.sha256")" = "$R_BACKEND" &&
        verify_manifest "$P" && boot_dependencies_match "$snapshot" || fail boot_dependencies_changed
    helper=$P/boot-select
    file "$helper" && test -x "$helper" || fail invalid_boot_selector
    snapshot_verify "$R_BASE" && firmware_guard && test "$(root_mode)" = ro,noatime || fail invalid_boot_baseline
    if ! absent "$D/snapshots/$snapshot/boot.plan"; then
        file "$D/snapshots/$snapshot/boot.plan" &&
            awk '$2=="boot.plan"{n++}END{exit n!=1}' "$D/snapshots/$snapshot/files.sha256" || fail invalid_boot_plan
        IFS='|' read -r magic base backend < "$D/snapshots/$snapshot/boot.plan"
        if test "$magic:$base:$backend" = "OCBP1:$R_BASE:$package" &&
            "$helper" check / "${D#/}/snapshots/$snapshot" < "$D/snapshots/$snapshot/boot.plan"; then
            printf '%s\n' "$snapshot"; exit 0
        fi
    fi
    work=$(mktemp -d "$D/snapshots/.new-XXXXXX") || fail boot_snapshot_create_failed
    set -- autostart config dependencies
    if test "$S_ACCESS" = true; then set -- "$@" access runlogin sshd.conf; fi
    if test "${S_SELECTOR_RECORDED:-false}" = true; then set -- "$@" selector; fi
    set -- "$@" sm-normal.conf sm-wcp.conf index.html
    # Capture the authenticated manifest, then keep each copied member bound to
    # its original named digest. A copied replacement must never be re-blessed.
    manifest=$(cat "$D/snapshots/$snapshot/files.sha256") || fail boot_profiles_missing
    digest=$(printf '%s\n' "$manifest" | openssl dgst -sha256) || fail boot_profiles_missing
    test "${digest##* }" = "$snapshot" || fail boot_profiles_changed
    for name in "$@"; do
        expected=$(printf '%s\n' "$manifest" | awk -v name="$name" '$2==name{n++;print $1}END{exit n!=1}') || fail boot_profiles_missing
        hex "$expected" 64 && file "$D/snapshots/$snapshot/$name" &&
            cp "$D/snapshots/$snapshot/$name" "$work/$name" &&
            test "$(sha "$work/$name")" = "$expected" || fail boot_profiles_changed
        chmod 600 "$work/$name" || fail boot_snapshot_mode_failed
    done
    boot_plan_inputs "$work" "$snapshot" "$manifest" "$@" > "$work/inputs" || fail boot_inputs_failed
    "$helper" seal / "${work#/}" < "$work/inputs" > "$work/boot.plan" || fail boot_plan_failed
    rm "$work/inputs" || fail boot_inputs_cleanup_failed
    chmod 600 "$work/boot.plan" || fail boot_snapshot_mode_failed
    snapshot_finish "$work" "$@" boot.plan
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
    for path in /usr/bin/.open-connect-* /etc/ssh/.open-connect-*; do absent "$path" || return 1; done
}
remount() {
    timeout -t 8 -s TERM /bin/busybox mount -i -n -t relfs -o "remount,$1,noatime" /dev/ffx01p1 / &&
        test "$(root_mode)" = "$1,noatime"
}
startup_publish() { root_publish "$AUTOSTART" "$@"; }

selector_matches_loaded() {
    local target=/usr/bin/open-connect-boot-select
    if test "${S_SELECTOR_HASH:--}" = -; then absent "$target"
    else
        file "$target" && test "$(sha "$target")" = "$S_SELECTOR_HASH" &&
            test "$(stat -c '%a:%u:%g' "$target")" = "$S_SELECTOR_META"
    fi
}

selector_capture() {
    selector_matches_loaded || return 1
    if test "${S_SELECTOR_HASH:--}" = -; then printf '%s\n' -
    else printf '%s|%s|%s\n' "$S_SELECTOR_HASH" "$S_SELECTOR_META" "$S_SELECTOR_PACKAGE"; fi > "$1/selector"
}

selector_compose() {
    local folder=$D/packages/$2 expected
    hex "$2" 64 && private_dir "$folder" &&
        test "$(sha "$folder/files.sha256")" = "$2" && file "$folder/boot-select" || return 1
    expected=$(awk '$2=="boot-select"{n++;print $1}END{exit n!=1}' "$folder/files.sha256") || return 1
    hex "$expected" 64 && test "$(sha "$folder/boot-select")" = "$expected" || return 1
    printf '%s|700:%s:%s|%s\n' "$expected" "$(id -u)" "$(id -g)" "$2" > "$1/selector"
}

selector_keep() {
    if ! absent "$1/selector"; then
        file "$1/selector" && cp "$1/selector" "$2/selector"
    fi
}

selector_pair_check() (
    local before_hash before_mode after_hash after_mode actual=- actual_mode=-
    snapshot_read "$1" || return 1
    before_hash=$S_SELECTOR_HASH; before_mode=$S_SELECTOR_META
    snapshot_read "$2" || return 1
    after_hash=$S_SELECTOR_HASH; after_mode=$S_SELECTOR_META
    if ! absent /usr/bin/open-connect-boot-select; then
        file /usr/bin/open-connect-boot-select || return 1
        actual=$(sha /usr/bin/open-connect-boot-select) &&
            actual_mode=$(stat -c '%a:%u:%g' /usr/bin/open-connect-boot-select) || return 1
    fi
    case "$actual:$actual_mode" in "$before_hash:$before_mode"|"$after_hash:$after_mode") ;; *) return 1;; esac
)

selector_apply() (
    local source=- actual=- actual_mode=-
    selector_pair_check "$1" "$2" && snapshot_read "$2" || return 1
    if test "$S_SELECTOR_HASH" != -; then
        source=$D/packages/$S_SELECTOR_PACKAGE/boot-select
        file "$source" && test "$(sha "$source")" = "$S_SELECTOR_HASH" || return 1
    fi
    if ! absent /usr/bin/open-connect-boot-select; then
        actual=$(sha /usr/bin/open-connect-boot-select) &&
            actual_mode=$(stat -c '%a:%u:%g' /usr/bin/open-connect-boot-select) || return 1
    fi
    root_publish /usr/bin/open-connect-boot-select "$source" "$S_SELECTOR_META" "$actual" "$actual_mode"
)

root_publish() (
    set -eu
    # BusyBox ash unwinds function locals before this subshell's EXIT trap.
    # Keep trap inputs in the subshell scope so cleanup can still read them.
    target=$1; source=$2; mode=$3; expected=$4; expected_mode=$5; identity=
    held=${6:-}; hold_mode=${7:-}
    case "$target" in /usr/bin/autostart|/usr/bin/runlogin|/etc/ssh/sshd_config|/usr/bin/open-connect-boot-select) ;; *) fail invalid_target;; esac
    case "$hold_mode" in
        '') test -z "$held" || fail invalid_hold;;
        keep|restore)
            test "$target" = /usr/bin/runlogin || fail invalid_hold
            case "$held" in /usr/bin/.open-connect-runlogin-*) ;; *) fail invalid_hold;; esac
            case "${held##*-}" in ''|*[!0-9]*) fail invalid_hold;; esac;;
        *) fail invalid_hold;;
    esac
    parent=${target%/*}
    directory "$parent" || fail invalid_startup_parent
    hex "$R_REV" 32 || fail invalid_startup_plan
    if test "$source" = -; then
        test "$target:$mode:$hold_mode" = /usr/bin/open-connect-boot-select:-: || fail invalid_startup_plan
    else file "$source" || fail invalid_startup_plan; fi
    if test "$expected" = -; then
        test "$target:$expected_mode" = /usr/bin/open-connect-boot-select:- || fail invalid_startup_plan
    else hex "$expected" 64 && metadata "$expected_mode" || fail invalid_startup_plan; fi
    # The durable pending revision names this exact staging file across retries.
    if test "$target" = "$AUTOSTART"; then work=/usr/bin/.open-connect-$R_REV
    else work=$parent/.open-connect-$R_REV-${target##*/}; fi
    case "$(root_mode)" in ro,noatime|rw,noatime) ;; *) fail root_mount_changed;; esac
    stage_matches() {
        local size prefix
        file "$work" || return 1
        size=$(stat -c %s "$work") || return 1
        test "$size" -le "$(stat -c %s "$source")" || return 1
        prefix=$(head -c "$size" "$source" | openssl dgst -sha256) || return 1
        test "$(sha "$work")" = "${prefix##* }"
    }
    target_matches() {
        if test "$expected" = -; then absent "$target"
        else
            file "$target" && test "$(sha "$target")" = "$expected" &&
                test "$(stat -c '%a:%u:%g' "$target")" = "$expected_mode"
        fi
    }
    # An already-written target still needs the directory flush and read-only
    # restoration if a preceding process was killed between those steps.
    finish() {
        local result=$?
        trap - EXIT HUP INT TERM
        if ! absent "$work" && test -n "$identity"; then
            if test "$(stat -c '%d:%i' "$work")" = "$identity" && stage_matches; then
                remount rw && rm "$work" && "$P/flush" d "$parent" || result=1
            else result=1; fi
        fi
        remount ro || result=1
        exit "$result"
    }
    trap finish EXIT
    trap 'exit 1' HUP INT TERM
    target_matches || fail startup_changed
    if test "$source" = -; then
        absent "$work" || fail startup_stage_changed
        if test "$expected" != -; then
            remount rw && target_matches && rm "$target" || fail selector_remove_failed
        fi
        flush d "$parent"
        exit 0
    fi
    if ! absent "$work"; then
        stage_matches || fail startup_stage_changed
        if test "$hold_mode" = restore; then
            test "$(stat -c '%d:%i' "$work")" = "$(stat -c '%d:%i' "$held")" || fail startup_stage_changed
        fi
        identity=$(stat -c '%d:%i' "$work") || fail startup_stage_changed
    fi
    if test "$expected" != "$(sha "$source")" || test "$expected_mode" != "$mode"; then
        remount rw || fail remount_failed
        if test "$hold_mode" = keep; then
            if absent "$held"; then
                test "$(stat -c %i "$target")" = "${held##*-}" || fail console_identity_changed
                ln "$target" "$held" || fail console_hold_failed
            fi
            access_hold_verify || fail console_hold_changed
            flush f "$held"
            flush d "$parent"
        fi
        if absent "$work"; then
            if test "$hold_mode" = restore; then
                access_hold_verify && test "$(stat -c '%a:%u:%g' "$held")" = "$mode" || fail console_hold_changed
                ln "$held" "$work" || fail startup_stage_failed
            else (set -C; : > "$work") || fail startup_stage_failed; fi
            identity=$(stat -c '%d:%i' "$work") || fail startup_stage_failed
        fi
        metadata "$mode" || fail invalid_startup_metadata
        # BusyBox cp replaces an existing inode. Preserve the exclusively
        # created stage's identity so the failure handler can remove it.
        if test "$hold_mode" != restore; then
            cat "$source" > "$work" && chown "$S_UID:$S_GID" "$work" && chmod "$S_MODE" "$work" || fail startup_copy_failed
        fi
        test "$(sha "$work")" = "$(sha "$source")" || fail startup_copy_changed
        flush f "$work"
        target_matches || fail startup_changed
        mv -f "$work" "$target" || fail startup_rename_failed
    fi
    flush f "$target"
    flush d "$parent"
)

nvram_read() { sh "$P/touch.sh" read; }
nvram_change() { sh "$P/touch.sh" change "$1" "$2" >/dev/null; }

dependency_path() {
    # Resolve names only. The dependency verifier checks the canonical file and
    # private package parent before reading any bytes.
    local scope=${1%%/*} name=${1#*/} id folder
    test "$scope/$name" = "$1" && test -n "$name" || return 1
    case "$name" in .|..|*[!a-zA-Z0-9_.-]*) return 1;; esac
    case "$scope" in
        root) firmware_dependencies | awk -v n="$name" '$2==n && n!="autostart"{print $3;found++} END{if(found!=1)exit 1}'; return;;
        package-*) id=${scope#package-}; folder=packages;;
        composed-*) id=${scope#composed-}; folder=composed;;
        *) return 1;;
    esac
    hex "$id" 64 || return 1
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
        case "$name" in api|flush|boot-select) chmod 700 "$work/$name" || fail package_mode_failed;; esac
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
