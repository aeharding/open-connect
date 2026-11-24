#!/bin/sh
set -eu
test "$#" -eq 2 || { test "$#" -eq 3 && test "$3" = --app-pss; }
boot=$1
package=$2
test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot"
awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_74.00.324\""{v++}$0=="JCI_SW_VER_PATCH=\"A\""{p++}$0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++}END{exit !(v==1&&p==1&&f==1)}' /jci/version.ini
awk '$1=="/dev/ffx01p1"&&$2=="/"&&$3=="relfs"&&$4=="ro,noatime"{n++}END{exit n!=1}' /proc/self/mounts
IFS='|' read -r format phase revision backend baseline current before after retired budget off attempt notice < /tmp/mnt/data_persist/open-connect/record
test "$format:$phase:$backend:$before:$after:$retired" = "OC1:active:$package:-:-:-"
test "$(cat /tmp/open-connect/selected)" = "$current"
# Appended after polling-read-probe.sh's exact identity/read-only guards.
R=/tmp/open-connect
test -d "$R" && test ! -L "$R"
printf 'RAM_UPTIME|'; cat /proc/uptime
printf 'RAM_MEMINFO_BEGIN\n'; cat /proc/meminfo; printf 'RAM_MEMINFO_END\n'
find "$R" -type f | while IFS= read -r path; do
    printf 'RAM_FILE|'; stat -c '%n|%s|%b|%d|%i' "$path"
done
printf 'RAM_DU_BEGIN\n'; du -k "$R"; printf 'RAM_DU_END\n'
process_memory() {
    local role=$1 pid=$2 birth
    birth=$(awk '{print $22}' "/proc/$pid/stat")
    test "$(readlink "/proc/$pid/exe")" = /bin/busybox
    printf 'RAM_PROCESS|%s|%s|%s\n' "$role" "$pid" "$birth"
    awk -v role="$role" -v pid="$pid" '
      /^(Rss|Pss|Shared_Clean|Shared_Dirty|Private_Clean|Private_Dirty|Swap):/ {sum[$1]+=$2}
      END {for (key in sum) print "RAM_PROCESS_TOTAL|" role "|" pid "|" key "|" sum[key]}
    ' "/proc/$pid/smaps"
    test "$(awk '{print $22}' "/proc/$pid/stat")" = "$birth"
}
IFS=' ' read -r listener listener_start session extra < "$R/listener"
test -z "$extra" && test "$(awk '{print $22}' "/proc/$listener/stat")" = "$listener_start"
tr '\0' '\n' < "/proc/$listener/cmdline" | grep -F -q "$session/api"
process_memory listener "$listener"
for fd in /proc/[0-9]*/fd/8; do
    test -L "$fd" || continue
    if test "$(readlink "$fd")" = "$R/ignition.lock"; then
        pid=${fd#/proc/}; pid=${pid%%/*}
        if tr '\0' '\n' < "/proc/$pid/cmdline" | grep -F -q "$R/ignition/ignition.sh"; then
            process_memory ignition "$pid"
        fi
    fi
done
for maps in /proc/[0-9]*/maps; do
    if grep -F -q "$R/" "$maps" 2>/dev/null; then
        pid=${maps#/proc/}; pid=${pid%%/*}
        awk -v pid="$pid" '
          /^[0-9a-f]+-[0-9a-f]+ / {path=$NF; selected=index(path,"/tmp/open-connect/")==1}
          selected && /^(Rss|Pss|Shared_Clean|Shared_Dirty|Private_Clean|Private_Dirty):/ {
              print "RAM_MAPPING|" pid "|" path "|" $1 "|" $2
          }
        ' "/proc/$pid/smaps"
    fi
done
test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot"
printf 'RAM_READ_ONLY_PROBE_COMPLETE\n'

if test "${3:-}" = --app-pss; then
    for role in L_jciMMUI L_jciVUI opera; do
        count=0
        for comm in /proc/[0-9]*/comm;do
            test -r "$comm" || continue
            read -r name < "$comm" || continue
            test "$name" = "$role" || continue
            pid=${comm#/proc/};pid=${pid%%/*}
            birth=$(awk '{print $22}' "/proc/$pid/stat")
            printf 'APP_PSS_BEGIN|%s|%s|%s|' "$role" "$pid" "$birth";cat /proc/uptime
            awk -v role="$role" -v pid="$pid" '/^(Rss|Pss|Shared_Clean|Shared_Dirty|Private_Clean|Private_Dirty|Swap):/{sum[$1]+=$2}END{for(key in sum)print "APP_PSS_TOTAL|"role"|"pid"|"key"|"sum[key]}' "/proc/$pid/smaps"
            printf 'APP_MAPS_BEGIN|%s|%s\n' "$role" "$pid";cat "/proc/$pid/maps";printf 'APP_MAPS_END|%s|%s\n' "$role" "$pid"
            test "$(awk '{print $22}' "/proc/$pid/stat")" = "$birth"
            printf 'APP_PSS_END|%s|%s\n' "$role" "$pid"
            count=$((count+1))
        done
        test "$count" = 1
    done
    test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot"
    printf 'MMUI_VUI_MATCHED_AGE_PSS_COMPLETE\n'
fi
