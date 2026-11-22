#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Shared synchronous RAM staging. Boot calls these functions under its existing
# lock; the USB entry takes that same lock here. Old sessions survive requests.

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

stop_listener() {
if ! absent "$R/listener"; then
    file "$R/listener" || fail invalid_listener
    read -r pid start old extra < "$R/listener" || fail invalid_listener
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

service_owns_listener() {
    local inode fd
    service_child_matches "$1" "$2" "$3" || return 1
    inode=$(awk '$2=="0100007F:8AE3"&&$4=="0A"{n++;i=$10}END{if(n!=1)exit 1;print i}' /proc/net/tcp) || return 1
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
    if test "$(readlink "$R/runtime" 2>/dev/null || :)" = "$3"; then rm "$R/runtime"; fi
    local pointer value
    for pointer in "$R/listener" "$R/listener.next"; do
        if test -f "$pointer" && test ! -L "$pointer"; then
            value=$(cat "$pointer")
            if test "$value" = "$1 $2 $3"; then rm "$pointer"; fi
        fi
    done
}

service_stage() {
    local role=$1 package_id=$2 work digest name extra token pid start deadline
    # A USB session can release its staging lock while its UI remains live.
    # Boot never replaces any already-published runtime in this kernel.
    if test "$role" = boot; then absent "$R/runtime" || fail busy; fi
if absent "$R/sessions"; then mkdir -m 700 "$R/sessions"; fi
private_dir "$R/sessions" || fail invalid_sessions
work=$(mktemp -d "$R/sessions/session-XXXXXX")
# Validate the canonical parent once; restricted direct basenames cannot escape it.
directory "$P" || fail invalid_source
set --
while read -r digest name extra; do
    hex "$digest" 64 && test -n "$name" && test -z "$extra" || fail invalid_manifest
    case "$name" in .|..|*[!a-zA-Z0-9.-]*) fail invalid_manifest;; esac
    test -f "$P/$name" && test ! -L "$P/$name" || fail invalid_source
    set -- "$@" "$P/$name"
done < "$P/files.sha256"
cp "$@" "$P/files.sha256" "$work/"
set -- "$work/files.sha256"
while read -r digest name extra; do set -- "$@" "$work/$name"; done < "$P/files.sha256"
chmod 600 "$@"
chmod 700 "$work/api" "$work/flush"
test "$(sha "$work/files.sha256")" = "$package_id" && verify_manifest "$work" || fail damaged_runtime
# One capability per boot keeps the installed Settings client usable while a
# replacement USB service is staged, even if its UI loading is cancelled.
if absent "$R/token"; then
    uuid > "$R/token.next"
    mv "$R/token.next" "$R/token"
fi
file "$R/token" && test "$(wc -c < "$R/token")" -eq 33 || fail token_failed
token=$(cat "$R/token"); hex "$token" 32 || fail token_failed
cp "$R/token" "$work/token"
stop_listener
if ! absent "$R/runtime"; then test -L "$R/runtime" || fail invalid_runtime_pointer; fi
( exec 8>&- 9>&-; exec /bin/busybox tcpsvd -E -c 4 127.0.0.1 35555 \
    /bin/busybox timeout -t 180 "$work/api" "$work/token" "$work/backend.sh" ) </dev/null >"$work/service.log" 2>&1 &
pid=$!
start=$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null) || start=
pending_pid=$pid; pending_start=$start; pending_work=$work
trap 'service_discard_child "$pending_pid" "$pending_start" "$pending_work"' EXIT
trap 'exit 1' HUP INT TERM
service_tick; deadline=$((service_now+100))
until test -n "$start" && service_owns_listener "$pid" "$start" "$work"; do
    service_tick
    if test "$service_now" -ge "$deadline" || ! test -d "/proc/$pid"; then
        # EXIT also handles selector timeout/signals before publication.
        fail listener_start_failed
    fi
    /bin/busybox usleep 10000
done
# Publish only after identity and owned socket readiness are established.
printf '%s %s %s\n' "$pid" "$start" "$work" > "$R/listener.next"
ln -sfn "$work" "$R/runtime"
mv -f "$R/listener.next" "$R/listener"
runtime=$work
trap - EXIT HUP INT TERM
unset pending_pid pending_start pending_work
}

service_main() {
    set -eu
    umask 077
    P=$(dirname "$(readlink -f "$0")")
    . "$P/state.sh"
    R=/tmp/open-connect
    service_lock usb
    case "${1:-start}" in
      stop)
        verify_manifest "$P" || fail damaged_package
        test "$(readlink -f "$R/runtime")" = "$P" || return 0
        absent "$R/selected" || return 0
        D=/tmp/mnt/data_persist/open-connect
        if ! absent "$D/record"; then
            private_dir "$D" && record_read || fail invalid_record
            test "$R_PHASE" = removed || return 0
        fi
        stop_listener
        rm "$R/runtime" "$R/listener";;
      start)
        service_stage usb "$(sha "$P/files.sha256")"
        printf '%s\n' "$runtime";;
      *) fail invalid_action;;
    esac
}

# A sourced module only defines functions. The fixed installed filename is also
# its standalone entry (used by USB); boot sources it from boot.sh or sh -c.
case "${0##*/}" in service.sh) service_main "$@";; esac
