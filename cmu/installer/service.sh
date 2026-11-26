#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Shared synchronous RAM staging. Boot calls these functions under its existing
# lock; the USB entry takes that same lock here. Old sessions survive requests.

# Freeze attachment facts at completion proof/first scan, under R/lock. Keep the
# successful empty observation; a later insertion must remain maintenance.
service_usb_observe() {
    local index=${R:-/tmp/open-connect}/feature/index.html boot saved ids= usb name number line
    boot=$(current_boot_id) && file "$index" || return 1
    if saved=$(awk -v boot="$boot" '
        index($0,"<!-- OCUSB1") {
            n++;s=$0
            if(sub(/^<!-- OCUSB1[|]/,"",s)!=1||sub(/ -->$/,"",s)!=1||
               split(s,a,"[|]")!=2||a[1]!=boot||length(a[2])>96||
               (a[2]!="-"&&a[2]!~/^([0-9]+-[0-9]+([.][0-9]+)*:[0-9]+;)+$/))bad=1
            value=a[2];next
        }
        n&&NF{bad=1}
        END{if(n!=1||bad)exit 1;print value}' "$index"); then
        printf '%s\n' "$saved"; return 0
    fi
    grep -F -q '<!-- OCUSB1' "$index" && return 1
    test "${1:-installed}" = installed || return 1
    test -d /sys/bus/usb/devices || return 1
    for usb in /sys/bus/usb/devices/[0-9]*-*; do
        name=${usb##*/}
        case "$name" in *[!0-9.-]*) continue;; esac
        test -r "$usb/devnum" || return 1
        read -r number < "$usb/devnum" || return 1
        case "$number" in ''|*[!0-9]*) return 1;; esac
        ids=$ids$name:$number';'
    done
    ids=${ids:--}; test "${#ids}" -le 96 || return 1
    line="<!-- OCUSB1|$boot|$ids -->"
    set -- $(stat -c '%s %b' "$index")
    test "$#" -eq 2 && test "$(($2 * 512 - $1))" -ge "$((${#line} + 2))" || return 1
    printf '\n%s\n' "$line" >> "$index" || return 1
    printf '%s\n' "$ids"
}

service_usb_source() {
    local path block name number
    block=$(awk -v path="${1%/open-connect}" '$2==path{n++;b=$1}
        END{if(n!=1||b!~/^\/dev\/sd[a-d]1$/)exit 1;print b}' /proc/mounts) || return 1
    block=${block##*/}
    path=$(readlink -f "/sys/class/block/$block") || return 1
    while test -n "$path" && test "$path" != /sys; do
        if test -r "$path/idVendor" && test -r "$path/devnum"; then
            name=${path##*/}; read -r number < "$path/devnum" || return 1
            case "$number" in ''|*[!0-9]*) return 1;; esac
            printf '%s:%s\n' "$name" "$number"; return 0
        fi
        path=${path%/*}
    done
    return 1
}

service_lock() {
    local count=0
    if absent "$R"; then mkdir -m 700 "$R"; fi
    private_dir "$R" || fail invalid_runtime
    if absent "$R/lock"; then (set -C; : > "$R/lock") || fail invalid_lock; fi
    file "$R/lock" || fail invalid_lock
    exec 9<>"$R/lock"
    until flock -n -x 9; do
        test "$1" != boot || fail busy
        count=$((count+1)); test "$count" -le 5 || fail busy
        sleep 1
    done
}

service_config() {
    service_role=${1:-settings}
    service_port=15555; service_runtime=$R/runtime; service_listener=$R/listener
    if test "$service_role" = usb; then
        service_port=15557; service_runtime=$R/usb-runtime; service_listener=$R/usb-listener
    fi
}

stop_listener() {
if ! absent "$service_listener"; then
    file "$service_listener" || fail invalid_listener
    read -r pid start old extra < "$service_listener" || fail invalid_listener
    case "$pid:$start" in *[!0-9:]*|:*) fail invalid_listener;; esac
    case "$old" in "$R"/sessions/session-*) ;; *) fail invalid_listener;; esac
    test -z "$extra" || fail invalid_listener
    if test -d "/proc/$pid"; then
        test "$(awk '{print $22}' "/proc/$pid/stat")" = "$start" &&
            test "$(readlink "/proc/$pid/exe")" = /bin/busybox &&
            tr '\0' '\n' < "/proc/$pid/cmdline" | grep -F -q "$old/api" || fail listener_replaced
        kill -TERM "$pid" || fail listener_stop_failed
        count=0
        while test -d "/proc/$pid" && test "$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null)" = "$start"; do
            test "$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null || :)" != Z || break
            count=$((count+1)); test "$count" -lt 4 || fail listener_stop_failed
            sleep 1
        done
    fi
fi
}

service_child_matches() {
    test "$(awk '{print $22}' "/proc/$1/stat" 2>/dev/null)" = "$2" &&
        test "$(readlink "/proc/$1/exe")" = /bin/busybox &&
        tr '\0' '\n' < "/proc/$1/cmdline" | awk -v api="$3/api" '$0==api{n++}END{exit n!=1}'
}

# Keep the fixed loopback listener below the OEM ephemeral range (32768..61000).
# MMUI keeps a client socket to SM:9091 for the session; its source can be 35555.
service_owns_listener() {
    local inode fd address
    case "${4:-15555}" in
        15555) address=0100007F:3CC3;;
        35555) address=0100007F:8AE3;;
        15557) address=0100007F:3CC5;;
        *) return 1;;
    esac
    service_child_matches "$1" "$2" "$3" || return 1
    inode=$(awk -v address="$address" '$2==address&&$4=="0A"{n++;i=$10}END{if(n!=1)exit 1;print i}' /proc/net/tcp) || return 1
    for fd in /proc/"$1"/fd/*; do
        if test "$(readlink "$fd")" = "socket:[$inode]"; then
            service_child_matches "$1" "$2" "$3"
            return
        fi
    done
    return 1
}

service_tick() {
    local tick idle
    read -r tick idle < /proc/uptime
    # Linux uptime has two fractional decimal digits; prefix avoids octal input.
    service_now=$((${tick%.*} * 100 + 1${tick#*.} - 100))
}

service_discard_child() {
    if test -n "$2" && test "$(awk '{print $4 ":" $22}' "/proc/$1/stat" 2>/dev/null)" = "$$:$2"; then
        kill -TERM "$1" || :
        /bin/busybox usleep 10000
        if test "$(awk '{print $4 ":" $22}' "/proc/$1/stat" 2>/dev/null)" = "$$:$2"; then kill -KILL "$1" || :; fi
        wait "$1" 2>/dev/null || :
    fi
    # Publication can itself fail. Remove only this unpublished child's pointers.
    if test "$(readlink "$service_runtime" 2>/dev/null || :)" = "$3"; then rm "$service_runtime"; fi
    local pointer value
    for pointer in "$service_listener" "$service_listener.next"; do
        if test -f "$pointer" && test ! -L "$pointer"; then
            value=$(cat "$pointer")
            if test "$value" = "$1 $2 $3"; then rm "$pointer"; fi
        fi
    done
    if test "${service_role:-}" = usb && test -d "$3"; then
        : > "$3/closed"
        (exec 8>&- 9>&-; sh "$3/usb-service.sh" retire) </dev/null >/dev/null 2>&1 &
    fi
}

service_files() {
    # A verified RAM closure can recover/purge even when USB owns the listener
    # or the loopback port is unavailable. This does not publish a session.
    local package_id=$1 kind=${2:-full} work digest name extra token expected= actual count=0 linked shared
    local seen='|' copied=
if absent "$R/sessions"; then mkdir -m 700 "$R/sessions"; fi
private_dir "$R/sessions" || fail invalid_sessions
work=$(mktemp -d "$R/sessions/session-XXXXXX")
if test "$kind" = usb; then staged=$work; fi
# Validate the canonical parent once; restricted direct basenames cannot escape it.
directory "$P" || fail invalid_source
set --
while read -r digest name extra; do
    hex "$digest" 64 && test -n "$name" && test -z "$extra" || fail invalid_manifest
    case "$name" in .|..|*[!a-zA-Z0-9.-]*) fail invalid_manifest;; esac
    case "$seen" in *"|$name|"*) fail invalid_manifest;; esac
    seen="$seen$name|"
    test -f "$P/$name" && test ! -L "$P/$name" || fail invalid_source
    if test "$kind" = boot; then
        case "$name" in
            backend.sh|state.sh|firmware.sh|access.sh|transaction.sh|service.sh|console.sh|touch.sh|preferences.awk|services.tsv|VERSION|api|flush|runtime.js|dialog.js|settings.js) ;;
            *) continue;;
        esac
    fi
    count=$((count+1))
    expected="$expected$digest *$work/$name
"
    linked=false
    case "$kind:$name" in boot:runtime.js|boot:dialog.js|boot:settings.js|boot:service.sh|boot:state.sh)
        for shared in "$R/feature/$name" "$R/ignition/$name"; do
            if test -f "$shared" && test ! -L "$shared"; then
                ln "$shared" "$work/$name" || fail runtime_link_failed
                linked=true
                break
            fi
        done
        ;;
    esac
    if test "$kind" = usb; then
        ln "$P/$name" "$work/$name" || fail runtime_link_failed
        linked=true
    fi
    if test "$linked" = false; then
        set -- "$@" "$P/$name"
        copied="$copied$name
"
    fi
done < "$P/files.sha256"
# Active snapshots always use their verified persistent package's renderer.
# The installed listener needs no private RAM copy of sm-profile.awk.
if test "$kind" = boot; then test "$count" -eq 16 || fail incomplete_runtime; fi
if test "$kind" = usb; then ln "$P/files.sha256" "$work/files.sha256" || fail runtime_link_failed
else cp "$@" "$P/files.sha256" "$work/"; fi
set -- "$work/files.sha256"
while IFS= read -r name; do
    if test -n "$name"; then set -- "$@" "$work/$name"; fi
done <<COPIED
$copied
COPIED
# Do not change the mode of an existing feature inode shared by a hardlink.
chmod 600 "$@"
chmod 700 "$work/api" "$work/flush"
set --
while read -r digest name extra; do
    if test -f "$work/$name" && test ! -L "$work/$name"; then set -- "$@" "$work/$name"; fi
done < "$P/files.sha256"
test "$(sha "$work/files.sha256")" = "$package_id" || fail damaged_runtime
actual=$(openssl dgst -sha256 -r "$@") || fail damaged_runtime
test "$actual" = "${expected%?}" || fail damaged_runtime
if test "$kind" = usb; then
    uuid > "$work/token"
else
    if absent "$R/token"; then uuid > "$R/token.next"; mv "$R/token.next" "$R/token"; fi
    file "$R/token" && test "$(wc -c < "$R/token")" -eq 33 || fail token_failed
    cp "$R/token" "$work/token"
fi
token=$(cat "$work/token"); hex "$token" 32 || fail token_failed
runtime=$work
}

service_listen() {
local work=$1 pid start deadline
service_config "${2:-settings}"
stop_listener
if ! absent "$service_runtime"; then test -L "$service_runtime" || fail invalid_runtime_pointer; fi
# Catch cancellation before fork; defer exit until $! and its birth time are
# captured. A parent-only TERM must not strand an unrecorded listening child.
pending_pid=; pending_start=; pending_work=$work; pending_cancel=false
trap 'service_discard_child "$pending_pid" "$pending_start" "$pending_work"' EXIT
trap 'pending_cancel=true' HUP INT TERM
( exec 8>&- 9>&-; exec /bin/busybox tcpsvd -E -c 4 127.0.0.1 "$service_port" \
    /bin/busybox timeout -t 180 "$work/api" "$work/token" "$work/backend.sh" ) </dev/null >"$work/service.log" 2>&1 &
pid=$!
start=$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null) || start=
pending_pid=$pid; pending_start=$start
if test "$pending_cancel" = true; then fail listener_start_cancelled; fi
service_tick; deadline=$((service_now+100))
until test -n "$start" && service_owns_listener "$pid" "$start" "$work" "$service_port"; do
    if test "$pending_cancel" = true; then fail listener_start_cancelled; fi
    service_tick
    if test "$service_now" -ge "$deadline" || ! test -d "/proc/$pid"; then
        # EXIT also handles selector timeout/signals before publication.
        fail listener_start_failed
    fi
    /bin/busybox usleep 10000
done
if test "$pending_cancel" = true; then fail listener_start_cancelled; fi
# Publish only after identity and owned socket readiness are established.
printf '%s %s %s\n' "$pid" "$start" "$work" > "$service_listener.next"
ln -sfn "$work" "$service_runtime"
mv -f "$service_listener.next" "$service_listener"
runtime=$work
# End the deferred fork window before checking its flag. EXIT cleanup remains
# armed until no cancellation can be forgotten at the completion handoff.
trap 'exit 1' HUP INT TERM
if test "$pending_cancel" = true; then fail listener_start_cancelled; fi
trap - EXIT HUP INT TERM
unset pending_pid pending_start pending_work pending_cancel
}

service_stage() {
    service_config settings
    if test "$1" = boot; then absent "$service_runtime" || fail busy; fi
    service_files "$2" "$1"
    service_listen "$runtime" "$1"
}

service_boot() {
    # This verified RAM entry must establish package trust without sourcing
    # writable code first. SM owns this bounded worker, outside boot selection.
    set -eu
    umask 077
    D=/tmp/mnt/data_persist/open-connect
    R=/tmp/open-connect
    service_config settings
    test "$(id -u)" = 0
    test "$(readlink -f "$D")" = "$D" && test "$(stat -c '%a:%u:%g' "$D")" = 700:0:0 || exit 1
    test "$(readlink -f "$R")" = "$R" && test "$(stat -c '%a:%u:%g' "$R")" = 700:0:0 || exit 1
    test -f "$R/lock" && test ! -L "$R/lock" || exit 1
    sleep 4
    exec 9<>"$R/lock"
    tries=0
    until flock -n -x 9; do
        tries=$((tries+1)); test "$tries" -lt 80 || exit 0
        /bin/busybox usleep 100000
    done
    # The installed endpoint is independent of a temporary USB endpoint.
    if test -e "$service_runtime" || test -L "$service_runtime"; then exit 0; fi
    test -f "$D/record" && test ! -L "$D/record" && test "$(wc -l < "$D/record")" -eq 1 || exit 1
    IFS='|' read -r format phase rev package base current before after undo budget off boot notice extra < "$D/record"
    test "$format:$phase:$before:$after" = OC1:active:-:- && test -z "$extra" || exit 1
    test -L "$R/boot-id" && test "$(stat -c '%s:%u:%g' "$R/boot-id")" = 36:0:0 &&
        test "$boot" = "$(readlink "$R/boot-id")" || exit 1
    test "${#package}:${#current}" = 64:64
    case "$package$current" in *[!a-f0-9]*) exit 1;; esac
    test -f "$R/selected" && test ! -L "$R/selected" && test "$(cat "$R/selected")" = "$current" || exit 1
    P=$D/packages/$package
    test "$(readlink -f "$P")" = "$P" && test "$(stat -c '%a:%u:%g' "$P")" = 700:0:0 || exit 1
    test -f "$P/files.sha256" && test ! -L "$P/files.sha256" || exit 1
    digest=$(openssl dgst -sha256 < "$P/files.sha256")
    test "${digest##* }" = "$package"
    seen='|'; expected=; count=0; mandatory=0
    set --
    while read -r digest name extra; do
        test "${#digest}" = 64 && test -n "$name" && test -z "$extra" || exit 1
        case "$digest" in *[!a-f0-9]*) exit 1;; esac
        case "$name" in .|..|*[!a-zA-Z0-9.-]*) exit 1;; esac
        case "$seen" in *"|$name|"*) exit 1;; esac
        seen="$seen$name|"
        case "$name" in state.sh|backend.sh|service.sh|api|flush) mandatory=$((mandatory+1));; esac
        test -f "$P/$name" && test ! -L "$P/$name" || exit 1
        set -- "$@" "$P/$name"
        expected="$expected$digest *$P/$name
"
        count=$((count+1)); test "$count" -le 64
    done < "$P/files.sha256"
    test "$mandatory" = 5
    actual_count=0
    for item in "$P"/* "$P"/.[!.]* "$P"/..?*; do
        if test ! -e "$item" && test ! -L "$item"; then continue; fi
        test -f "$item" && test ! -L "$item"
        actual_count=$((actual_count+1))
    done
    test "$actual_count" -eq "$((count+1))"
    actual=$(openssl dgst -sha256 -r "$@")
    test "$actual" = "${expected%?}"
    . "$P/state.sh"
    record_read && test "$R_PHASE:$R_BACKEND:$R_CURRENT:$R_BOOT" = "active:$package:$current:$boot" || fail state_changed
    service_stage boot "$package"
}

# Boot selection may source these helpers without starting a listener.
case "${0##*/}" in service.sh) test "${1:-}" = boot || exit 1; service_boot;; esac
