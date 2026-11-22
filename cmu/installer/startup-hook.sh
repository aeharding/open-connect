        # Open Connect: one native worker, one deadline and a join before SM.
        oc_result=1; oc_pid=; oc_frame=; oc_released=false; oc_launched=false
        oc_deadline=0
        if read -r oc_tick oc_idle < /proc/uptime; then
            oc_deadline=$((${oc_tick%.*} * 100 + 1${oc_tick#*.} - 100 + 2500))
            oc_result=95
        fi
        oc_remaining() {
            oc_wait=0
            if read -r oc_tick oc_idle < /proc/uptime; then
                oc_wait=$(((oc_deadline - (${oc_tick%.*} * 100 + 1${oc_tick#*.} - 100)) / 100))
            fi
        }
        oc_wait_worker() {
            if wait "$oc_pid"; then oc_result=0; else oc_result=$?; fi
            oc_pid=
        }
        oc_gate_worker() {
            oc_remaining
            test "$oc_wait" -gt 0 || return 1
            oc_launched=true
            /bin/busybox timeout -t "$oc_wait" /usr/bin/open-connect-boot-select select-gated \
                </dev/null 1>&8 8>&- 7>&- &
            oc_pid=$!
            oc_read=false
            if IFS= read -r -n 1 -t 1 oc_frame <&7; then oc_read=true; fi
            if test "$oc_read:$oc_frame" = true:G; then
                oc_released=true
                oc_result=1 # Pending join; never enter shell recovery concurrently.
                return 0
            fi
            # Keep both endpoints valid until a delayed frame has been resolved.
            oc_wait_worker
            if test "$oc_read" != true && test -z "$oc_frame"; then
                if IFS= read -r -n 1 -t 1 oc_frame <&7; then oc_read=true; fi
            fi
            case "$oc_read:$oc_frame:$oc_result" in
                true:J:95|true:J:0|true:J:2|true:G:0|true:G:2) ;;
                false::64) oc_result=95;; # Known old select ABI: usage, no effects.
                *) oc_result=1;;
            esac
            return 0
        }
        oc_finish_selection() {
            if test "$oc_result" = 0; then
                SMCFG_NORMALMODE=/tmp/open-connect/feature/sm.conf
                SMCFG_WCPMODE=/tmp/open-connect/feature/sm_WCP.conf
            fi
            case "$oc_result" in 0|2)
                if test -d /tmp/open-connect/ignition && test ! -L /tmp/open-connect/ignition; then
                    (
                        unset LD_LIBRARY_PATH LD_PRELOAD LD_AUDIT ENV BASH_ENV
                        PATH=/usr/bin:/bin:/usr/sbin:/sbin
                        export PATH
                        exec 7>&- 8>&- 9>&-
                        exec /bin/busybox sh /tmp/open-connect/ignition/ignition.sh
                    ) </dev/null >/dev/null 2>&1 &
                fi;;
            esac
        }
        if test "$oc_result" = 95 && test -f /usr/bin/open-connect-boot-select && test ! -L /usr/bin/open-connect-boot-select && test -x /usr/bin/open-connect-boot-select; then
            oc_directory=$(mktemp -d /tmp/.open-connect-gate-XXXXXX) || oc_directory=
            if test -n "$oc_directory" && test -d "$oc_directory" && test ! -L "$oc_directory"; then
                if mkfifo -m 600 "$oc_directory/control"; then
                    if oc_gate_worker 7<>"$oc_directory/control" 8>"$oc_directory/control"; then :; else oc_result=1; fi
                    rm "$oc_directory/control"
                fi
                rmdir "$oc_directory"
            fi
            # A setup failure before launch may use the historical sync entry.
            if test "$oc_launched" = false; then
                oc_remaining
                if test "$oc_wait" -gt 0; then
                    if timeout -t "$oc_wait" /usr/bin/open-connect-boot-select select; then oc_result=0; else oc_result=$?; fi
                else oc_result=1; fi
            fi
        fi
        if test "$oc_result" = 95; then
            oc_wait=0
            if read -r oc_tick oc_idle < /proc/uptime; then
                oc_wait=$(((oc_deadline - (${oc_tick%.*} * 100 + 1${oc_tick#*.} - 100)) / 100))
            fi
            if test "$oc_wait" -gt 0; then
        if timeout -t "$oc_wait" sh -c 'set -eu
umask 077
read -r entered idle < /proc/uptime || entered=unknown
test "$(id -u)" = 0
awk '\''
    $2=="/tmp/mnt/data_persist/open-connect" || index($2,"/tmp/mnt/data_persist/open-connect/")==1 ||
    $2=="/tmp/open-connect" || index($2,"/tmp/open-connect/")==1 {bad=1}
    $2=="/" {
        if($1=="rootfs" && $3=="rootfs" && $4=="rw" && root==0 && rootfs==0)rootfs++
        else if($1=="/dev/ffx01p1" && $3=="relfs" && $4=="ro,noatime")root++
        else bad=1
    }
    $2=="/tmp/mnt/data_persist" {
        if($1!="/dev/mmcblk0p2" || $3!="relfs")bad=1
        data++;split($4,a,",");for(i in a)if(a[i]=="rw")rw++
    }
    END {exit bad || root!=1 || data!=1 || rw!=1}
'\'' /proc/self/mounts || exit 1
D=/tmp/mnt/data_persist/open-connect
R=/tmp/open-connect
test "$(readlink -f "$D")" = "$D"
test "$(stat -c '\''%a:%u:%g'\'' "$D")" = 700:0:0
if test ! -e "$R" && test ! -L "$R"; then mkdir -m 700 "$R"; fi
test "$(readlink -f "$R")" = "$R"
test "$(stat -c '\''%a:%u:%g'\'' "$R")" = 700:0:0
if test ! -e "$R/lock" && test ! -L "$R/lock"; then (set -C; : > "$R/lock"); fi
test -f "$R/lock" && test ! -L "$R/lock" || exit 1
exec 9<>"$R/lock"
flock -n -x 9
test -f "$D/record" && test ! -L "$D/record" || exit 1
test "$(wc -l < "$D/record")" -eq 1
IFS="|" read -r format phase rev package rest < "$D/record"
test "$format" = OC1 && test "${#package}" -eq 64 || exit 1
case "$package" in *[!a-f0-9]*) exit 1;; esac
P=$D/packages/$package
test "$(readlink -f "$P")" = "$P"
test -f "$P/files.sha256" && test ! -L "$P/files.sha256" || exit 1
digest=$(openssl dgst -sha256 < "$P/files.sha256")
test "${digest##* }" = "$package"
expected=; seen='\''|'\''; mandatory=0; count=0
set --
while read -r digest name extra; do
    test "${#digest}" = 64 && test -n "$name" && test -z "$extra" || exit 1
    case "$digest" in *[!a-f0-9]*) exit 1;; esac
    case "$name" in .|..|*[!a-zA-Z0-9.-]*) exit 1;; esac
    case "$seen" in *"|$name|"*) exit 1;; esac
    seen="$seen$name|"
    case "$name" in boot.sh|state.sh|firmware.sh|access.sh|transaction.sh|service.sh) mandatory=$((mandatory+1));; esac
    test -f "$P/$name" && test ! -L "$P/$name" || exit 1
    set -- "$@" "$P/$name"
    expected="$expected$digest *$P/$name
"
    count=$((count+1)); test "$count" -le 64
done < "$P/files.sha256"
test "$mandatory" = 6
actual_count=0
for item in "$P"/* "$P"/.[!.]* "$P"/..?*; do
    if test ! -e "$item" && test ! -L "$item"; then continue; fi
    test -f "$item" && test ! -L "$item" || exit 1
    actual_count=$((actual_count+1))
done
test "$actual_count" -eq "$((count+1))"
actual=$(openssl dgst -sha256 -r "$@")
test "$actual" = "${expected%?}" || exit 1
# Source only the explicitly versioned function interface. A verified older
# backend (including interrupted rollback) needs its original standalone entry.
if awk '\''$0=="# Open Connect locked selector interface 1"{n++}END{exit n!=1}'\'' "$P/boot.sh"; then
    . "$P/boot.sh"
    oc_times=; oc_stamp_count=0
    oc_times="hook_entry|$entered
"; oc_stamp_count=1
    startup_stamp package_verified
    oc_outer_observer=true
    boot_select
    startup_stamps_publish
else
    exec 9>&-
    exec sh "$P/boot.sh"
fi
'; then oc_result=0
        else oc_result=$?; fi
            else oc_result=1; fi
        fi
        if test "$oc_released" = true; then
            oc_oem_start=
            read -r oc_oem_start oc_idle < /proc/uptime || oc_oem_start=
        else
            oc_finish_selection
        fi
