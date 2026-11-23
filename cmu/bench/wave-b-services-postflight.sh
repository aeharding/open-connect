#!/bin/sh
set -eu
boot=$1
base=$2
package=$3
R=/tmp/open-connect
awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_74.00.324\""{v++} $0=="JCI_SW_VER_PATCH=\"A\""{p++} $0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++} END{exit v!=1||p!=1||f!=1}' /jci/version.ini
awk '$1=="/dev/ffx01p1"&&$2=="/"&&$4=="ro,noatime"{n++}END{exit n!=1}' /proc/self/mounts
record=/tmp/mnt/data_persist/open-connect/record
test "$(cut -d '|' -f 4 "$record")" = "$package"
test "$(cat "$R/selected")" = "$(cut -d '|' -f 6 "$record")"
test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot"
if test -f /tmp/open-connect/startup-times; then
 printf 'NATIVE_SELECTOR_PHASES_BEGIN\n';cat /tmp/open-connect/startup-times;printf 'NATIVE_SELECTOR_PHASES_END\n'
fi
printf 'SM_EVENTS_BEGIN\n';cat /tmp/smevents.txt;printf 'SM_EVENTS_END\n'
version=$(cat /tmp/open-connect/runtime/VERSION)
for name in jciDAB jcitv blm_ira_stitcher irsstitcher_server aap_service jciAAPA blm_ira_pandora blm_ira_aha offboard_service irs_server jcidvd jciSXMS jciXMMGR; do
 info=$(LD_LIBRARY_PATH=/jci/lib:/usr/lib:/lib timeout -t 5 /jci/sm/smctl --get --type info --name "$name")
 expected=RUNNING
 case "$base:$name" in 1:jciDAB|1:jcitv|1:blm_ira_stitcher|1:irsstitcher_server) expected=STOPPED;; esac
 if test "$version" = 0.3.0-dev.15; then
   case "$name" in blm_ira_aha|offboard_service|jcidvd) expected=STOPPED;; esac
 fi
 printf '%s\n' "$info"
 actual=$(printf '%s\n' "$info" | awk -F '"' '/^    state=/{print $2}')
 printf 'SERVICE|%s|%s|expected=%s\n' "$name" "$actual" "$expected"
 test "$actual" = "$expected"
done
test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot"
printf 'EXTRA_VERIFIED|%s\n' "$boot"

