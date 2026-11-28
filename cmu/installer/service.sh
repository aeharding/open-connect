#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
ro=$(id -u) && ro=$ro:$(id -g) || exit 1
case "$ro" in :*|*:|*:*:*|*[!0-9:]*) exit 1;; esac
fail() { printf '%s\n' "$1" >&2; exit 1; }
sha() { "$P/flush" h "$1"; }
hex() { [ "${#1}" -eq "$2" ] && case "$1" in *[!a-f0-9]*) false;; *) true;; esac; }
sha_is() { local d; d=$(sha "$1") && hex "$d" 64 && [ "$d" = "$2" ]; }
uuid() { tr -d '-' < /proc/sys/kernel/random/uuid; }
absent() { [ ! -e "$1" ] && [ ! -L "$1" ]; }
rf() { [ -f "$1" ] && [ ! -L "$1" ]; }
file() { rf "$1" && [ "$(readlink -f "$1")" = "$1" ]; }
directory() { [ -d "$1" ] && [ ! -L "$1" ] && [ "$(readlink -f "$1")" = "$1" ]; }
one_line() { file "$1" && IFS= read -r line < "$1" && [ "$(wc -c < "$1")" -eq "$((${#line}+1))" ]; }
private_dir() { directory "$1" && [ "$(stat -c '%a:%u:%g' "$1")" = "700:$ro" ]; }
boot_id() {
local v=$1 d
case "$1" in ????????-????-????-????-????????????) ;; *) return 1;; esac
for d in 1 2 3 4; do v=${v%%-*}${v#*-}; done
hex "$v" 32
}
current_boot_id() {
local m=${R:-/tmp/open-connect}/boot-id v
[ -L "$m" ] && [ "$(stat -c '%s:%u:%g' "$m")" = "36:$ro" ] || return 1
v=$(readlink "$m") && boot_id "$v" || return 1
printf '%s\n' "$v"
}
record_read() {
local line fmt ex lu
one_line "$D/record" || return 1
IFS='|' read -r fmt R_PHASE R_REV R_BACKEND R_BASE R_CURRENT R_BEFORE R_AFTER lu R_BUDGET R_OFF R_BOOT R_NOTICE ex < "$D/record" || return 1
[ "$line" = "OC1|$R_PHASE|$R_REV|$R_BACKEND|$R_BASE|$R_CURRENT|$R_BEFORE|$R_AFTER|$lu|$R_BUDGET|$R_OFF|$R_BOOT|$R_NOTICE" ] || return 1
[ "$fmt" = OC1 ] && hex "$R_REV" 32 && hex "$R_BACKEND" 64 && hex "$R_BASE" 64 && hex "$R_CURRENT" 64 || return 1
for ex in "$R_BEFORE" "$R_AFTER" "$lu"; do [ "$ex" = - ] || hex "$ex" 64 || return 1; done
case "$R_PHASE" in
active|removed|purge) [ "$R_BEFORE:$R_AFTER" = -:- ] || return 1;;
install|set|uninstall|apply) hex "$R_BEFORE" 64 && hex "$R_AFTER" 64 || return 1;;
*) return 1;;
esac
case "$R_BUDGET" in 0|1|2|3) ;; *) return 1;; esac
[ "$R_OFF" = - ] || boot_id "$R_OFF" || return 1
[ "$R_BOOT" = - ] || boot_id "$R_BOOT" || return 1
case "$R_NOTICE" in -|installed|removed|undone|restart) ;; *) return 1;; esac
}

service_usb_observe() {
local idx=${R:-/tmp/open-connect}/feature/index.html boot sv ids= u nm num ln
boot=$(current_boot_id) && file "$idx" || return 1
if sv=$(awk -v boot="$boot" '
index($0,"<!-- OCUSB1"){n++;s=$0
if(sub(/^<!-- OCUSB1[|]/,"",s)!=1||sub(/ -->$/,"",s)!=1||split(s,a,"[|]")!=2||a[1]!=boot||length(a[2])>96||(a[2]!="-"&&a[2]!~/^([0-9]+-[0-9]+([.][0-9]+)*:[0-9]+;)+$/))bad=1
value=a[2];next}
n&&NF{bad=1}
END{if(n!=1||bad)exit 1;print value}' "$idx"); then printf '%s\n' "$sv"; return 0; fi
grep -Fq '<!-- OCUSB1' "$idx" && return 1
[ "${1:-installed}" = installed ] && [ -d /sys/bus/usb/devices ] || return 1
for u in /sys/bus/usb/devices/[0-9]*-*; do
nm=${u##*/}
case "$nm" in *[!0-9.-]*) continue;; esac
[ -r "$u/devnum" ] || return 1
read -r num < "$u/devnum" || return 1
case "$num" in ''|*[!0-9]*) return 1;; esac
ids=$ids$nm:$num';'
done
ids=${ids:--}; [ "${#ids}" -le 96 ] || return 1
ln="<!-- OCUSB1|$boot|$ids -->"
set -- $(stat -c '%s %b' "$idx")
[ "$#" -eq 2 ] && [ "$(($2 * 512 - $1))" -ge "$((${#ln} + 2))" ] || return 1
printf '\n%s\n' "$ln" >> "$idx" || return 1
printf '%s\n' "$ids"
}

service_usb_source() {
local p blk nm num
blk=$(awk -v path="${1%/open-connect}" '$2==path{n++;b=$1}
END{if(n!=1||b!~/^\/dev\/sd[a-d]1$/)exit 1;print b}' /proc/mounts) || return 1
blk=${blk##*/}
p=$(readlink -f "/sys/class/block/$blk") || return 1
while [ -n "$p" ] && [ "$p" != /sys ]; do
if [ -r "$p/idVendor" ] && [ -r "$p/devnum" ]; then
nm=${p##*/}; read -r num < "$p/devnum" || return 1
case "$num" in ''|*[!0-9]*) return 1;; esac
printf '%s:%s\n' "$nm" "$num"; return 0
fi
p=${p%/*}
done
return 1
}

service_lock() {
local c=0
if absent "$R"; then mkdir -m 700 "$R"; fi
private_dir "$R" || fail invalid_runtime
if absent "$R/lock"; then (set -C; : > "$R/lock") 2>/dev/null || :; fi
file "$R/lock" && [ "$(stat -c '%u:%g' "$R/lock")" = "$ro" ] || fail invalid_lock
exec 9<>"$R/lock"
until flock -n -x 9; do
[ "$1" != boot ] || fail busy
c=$((c+1)); [ "$c" -le 5 ] || fail busy
sleep 1
done
}

service_config() {
service_role=${1:-settings}
service_port=15555; service_runtime=$R/runtime; service_listener=$R/listener
if [ "$service_role" = usb ]; then
service_port=15557; service_runtime=$R/usb-runtime; service_listener=$R/usb-listener
fi
}

proc_gone() { local s; s=$(awk '{print $3}' "/proc/$1/stat" 2>/dev/null) || return 0; [ -z "$s" ] || [ "$s" = Z ]; }
stop_listener() {
local pid start old extra c=0 st
if ! absent "$service_listener"; then
file "$service_listener" || fail invalid_listener
read -r pid start old extra < "$service_listener" || fail invalid_listener
case "$pid:$start" in *[!0-9:]*|:*) fail invalid_listener;; esac
case "$old" in "$R"/sessions/session-*) ;; *) fail invalid_listener;; esac
[ -z "$extra" ] || fail invalid_listener
if [ -d "/proc/$pid" ]; then
st=$(awk '{print $3":"$22}' "/proc/$pid/stat" 2>/dev/null) || return 0
case "$st" in ""|:|Z:"$start") return 0;; *:"$start") ;; *) fail listener_replaced;; esac
if [ "$(readlink "/proc/$pid/exe" 2>/dev/null)" = /bin/busybox ] &&
tr '\0' '\n' 2>/dev/null < "/proc/$pid/cmdline" | grep -Fq "$old/api"; then :
elif proc_gone "$pid"; then return 0
else fail listener_replaced; fi
kill -TERM "$pid" 2>/dev/null || proc_gone "$pid" || fail listener_stop_failed
while ! proc_gone "$pid" && [ "$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null)" = "$start" ]; do
c=$((c+1)); [ "$c" -lt 4 ] || fail listener_stop_failed
sleep 1
done
fi
fi
}

service_child_matches() {
[ "$(awk '{print $22}' "/proc/$1/stat" 2>/dev/null)" = "$2" ] &&
[ "$(readlink "/proc/$1/exe")" = /bin/busybox ] &&
tr '\0' '\n' < "/proc/$1/cmdline" | awk -v api="$3/api" '$0==api{n++}END{exit n!=1}'
}

service_owns_listener() {
local ino fd a
case "${4:-15555}" in
15555) a=0100007F:3CC3;;
35555) a=0100007F:8AE3;;
15557) a=0100007F:3CC5;;
*) return 1;;
esac
service_child_matches "$1" "$2" "$3" || return 1
ino=$(awk -v address="$a" '$2==address&&$4=="0A"{n++;i=$10}END{if(n!=1)exit 1;print i}' /proc/net/tcp) || return 1
for fd in /proc/"$1"/fd/*; do
if [ "$(readlink "$fd")" = "socket:[$ino]" ]; then service_child_matches "$1" "$2" "$3"; return; fi
done
return 1
}

service_tick() {
local t _
read -r t _ < /proc/uptime
service_now=$((${t%.*} * 100 + 1${t#*.} - 100))
}

service_usb_retained() (
local f dl rv l c=-
[ -L "$1/admitted" ] && l=$(readlink "$1/admitted") || return 1
[ "$(stat -c %s "$1/admitted")" -eq "${#l}" ] || return 1
IFS='|' read -r f dl rv <<LEASE
$l
LEASE
[ "$f" = OCUSB1 ] && [ "$l" = "$f|$dl|$rv" ] || return 1
case "$dl" in ''|*[!0-9]*) return 1;; esac
[ "${#dl}" -le 12 ] || return 1
service_tick
[ "$dl" -gt "$service_now" ] && [ "$dl" -le "$((service_now+12000))" ] || return 1
if ! absent "$D/record"; then
record_read || return 1
case "$R_PHASE" in active|removed) c=$R_CURRENT;; *) return 1;; esac
elif ! absent "$D"; then return 1
fi
[ "$rv" = "$c" ]
)

service_discard_child() {
if [ -n "$2" ] && [ "$(awk '{print $4 ":" $22}' "/proc/$1/stat" 2>/dev/null)" = "$$:$2" ]; then
kill -TERM "$1" || :; /bin/busybox usleep 10000
if [ "$(awk '{print $4 ":" $22}' "/proc/$1/stat" 2>/dev/null)" = "$$:$2" ]; then kill -KILL "$1" || :; fi
wait "$1" 2>/dev/null || :
fi
if [ "$(readlink "$service_runtime" 2>/dev/null || :)" = "$3" ]; then rm "$service_runtime"; fi
local ptr
for ptr in "$service_listener" "$service_listener.next"; do
if rf "$ptr" && [ "$(cat "$ptr")" = "$1 $2 $3" ]; then rm "$ptr"; fi
done
if [ "${service_role:-}" = usb ] && [ -d "$3" ]; then
: > "$3/closed"
(exec 8>&- 9>&-; sh "$3/usb-service.sh" retire) </dev/null >/dev/null 2>&1 &
elif [ -n "$3" ] && [ "${p_pub:-false}" != true ]; then
service_discard_private "$3"
fi
}

service_discard_private() {
case "$1" in "$R"/sessions/session-*) ;; *) return 1;; esac
private_dir "$1" || return 1
rm -f "$1"/* "$1"/.[!.]* "$1"/..?*
rmdir "$1"
}

service_files() {
runtime=$(_service_files "$@")
}

_service_files() (
set -eu
local pid=$1 kind=${2:-full} w d nm ex tok exp= act n=0 lk shd seen='|' cpn= ru=false lks b
if absent "$R/sessions"; then mkdir -m 700 "$R/sessions"; fi
private_dir "$R/sessions" || fail invalid_sessions
w=$(mktemp -d "$R/sessions/session-XXXXXX")
sw=$w
trap 'service_discard_private "$sw"' EXIT
trap 'exit 1' HUP INT TERM
directory "$P" || fail invalid_source
if [ "$kind" = usb ]; then file "$P/files.sha256" || fail invalid_source; fi
set --
while read -r d nm ex; do
hex "$d" 64 && [ -n "$nm" ] && [ -z "$ex" ] || fail invalid_manifest
case "$nm" in .|..|*[!a-zA-Z0-9.-]*) fail invalid_manifest;; esac
case "$seen" in *"|$nm|"*) fail invalid_manifest;; esac
seen="$seen$nm|"
rf "$P/$nm" || fail invalid_source
if [ "$kind" = boot ]; then
case "$nm" in service.sh|console.sh|VERSION|api|flush|runtime.js|dialog.js|settings.js) ;; *) continue;; esac
fi
n=$((n+1))
exp="$exp$d *$w/$nm
"
lk=false
case "$kind:$nm" in boot:runtime.js|boot:dialog.js|boot:settings.js|boot:service.sh|boot:flush)
for shd in "$R/feature/$nm" "$R/ignition/$nm"; do
if rf "$shd"; then
if [ "$nm" = flush ] && [ "$(stat -c %a "$shd")" != 700 ]; then continue; fi
ln "$shd" "$w/$nm" || fail runtime_link_failed
lk=true; break
fi
done;;
esac
if [ "$lk" = false ]; then
set -- "$@" "$P/$nm"
cpn="$cpn$nm
"
fi
done < "$P/files.sha256"
[ -z "${d:-}${nm:-}${ex:-}" ] || fail invalid_manifest
if [ "$kind" = boot ]; then [ "$n" -eq 8 ] || fail incomplete_runtime; fi
case "$kind:${P%/*}:${P##*/}" in usb:/tmp:oc-usb-??????)
if private_dir "$P" && lks=$(stat -c %h "$@" "$P/files.sha256") &&
printf '%s\n' "$lks" | awk '$0!="1"{bad=1}END{exit bad}'; then ru=true; fi;;
esac
if [ "$ru" = true ]; then ln "$@" "$P/files.sha256" "$w/" || fail runtime_link_failed; cpn=
else cp "$@" "$P/files.sha256" "$w/"; fi
set -- "$w/files.sha256"
while IFS= read -r nm; do if [ -n "$nm" ]; then set -- "$@" "$w/$nm"; fi; done <<COPIED
$cpn
COPIED
chmod 600 "$@"
chmod 700 "$w/api" "$w/flush"
for b in ignition install; do if rf "$w/$b"; then chmod 700 "$w/$b"; fi; done
sha_is "$w/files.sha256" "$pid" || fail damaged_runtime
set --
while read -r d nm ex; do if rf "$w/$nm"; then set -- "$@" "$w/$nm"; fi; done < "$w/files.sha256"
act=$(openssl dgst -sha256 -r "$@") || fail damaged_runtime
[ "$act" = "${exp%?}" ] || fail damaged_runtime
if [ "$kind" = usb ]; then uuid > "$w/token"
else
if absent "$R/token"; then uuid > "$R/token.next"; mv "$R/token.next" "$R/token"; fi
file "$R/token" && [ "$(wc -c < "$R/token")" -eq 33 ] || fail token_failed
ln "$R/token" "$w/token" || fail token_failed
fi
tok=$(cat "$w/token"); hex "$tok" 32 || fail token_failed
printf '%s\n' "$w"
trap - EXIT HUP INT TERM
)

service_listen() {
local work=$1 pid start deadline
service_config "${2:-settings}"
stop_listener
if ! absent "$service_runtime"; then [ -L "$service_runtime" ] || fail invalid_runtime_pointer; fi
p_pid=; p_st=; p_wk=$work; p_can=false; p_pub=false
trap 'service_discard_child "$p_pid" "$p_st" "$p_wk"' EXIT
trap 'p_can=true' HUP INT TERM
( exec 8>&- 9>&-; exec /bin/busybox tcpsvd -E -c 4 127.0.0.1 "$service_port" \
/bin/busybox timeout -t 180 "$work/api" "$work/token" ) </dev/null >"$work/service.log" 2>&1 &
pid=$!
start=$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null) || start=
p_pid=$pid; p_st=$start
if [ "$p_can" = true ]; then fail listener_start_cancelled; fi
service_tick; deadline=$((service_now+100))
until [ -n "$start" ] && service_owns_listener "$pid" "$start" "$work" "$service_port"; do
if [ "$p_can" = true ]; then fail listener_start_cancelled; fi
service_tick
if [ "$service_now" -ge "$deadline" ] || [ ! -d "/proc/$pid" ]; then
fail listener_start_failed
fi
/bin/busybox usleep 10000
done
if [ "$p_can" = true ]; then fail listener_start_cancelled; fi
printf '%s %s %s\n' "$pid" "$start" "$work" > "$service_listener.next"
ln -sfn "$work" "$service_runtime"
p_pub=true
mv -f "$service_listener.next" "$service_listener"
runtime=$work
trap 'exit 1' HUP INT TERM
if [ "$p_can" = true ]; then fail listener_start_cancelled; fi
trap - EXIT HUP INT TERM
unset p_pid p_st p_wk p_can p_pub
}

service_stage() {
service_config settings
if [ "$1" = boot ]; then absent "$service_runtime" || fail busy; fi
service_files "$2" "$1"
service_listen "$runtime" "$1"
}

eth1_ip() { ip -4 addr show dev eth1 2>/dev/null; }
eth1_dhcp() { eth1_ip | awk '$1=="inet"&&$2!~/^(192\.168\.42\.1\/|127\.|169\.254\.)/{ok=1}END{exit !ok}'; }
eth1_fb() { [ -d /sys/class/net/eth1 ] || return 0; eth1_ip | grep -Fq 'inet 192.168.42.1/' || ip addr add dev eth1 192.168.42.1/24 2>/dev/null || :; }
eth1_busy() {
local p
for p in /proc/[0-9]*/cmdline; do
[ -r "$p" ] || continue
case "$(tr '\0' ' ' 2>/dev/null < "$p")" in *udhcpc*eth1*) return 0;; esac
done
return 1
}
eth1_wait_free() {
local w=0
while eth1_busy; do w=$((w+1)); [ "$w" -le 45 ] || return 1; sleep 1; done
}
service_eth1_dhcp() {
set +e
local i=0 eh=
while [ ! -d /sys/class/net/eth1 ]; do i=$((i+1)); [ "$i" -le 20 ] || return 0; sleep 1; done
sleep 2
eth1_wait_free || return 0
if eth1_dhcp; then eth1_fb; return 0; fi
eh=$(mktemp "$R/.eth1-dhcp-XXXXXX") || return 0
oc_eh=$eh
trap 'rm -f "$oc_eh"' EXIT
trap 'exit 1' HUP INT TERM
cat > "$eh" <<'EOF'
#!/bin/sh
[ "$interface" = eth1 ] || exit 0
case "$1" in
deconfig) exit 0;;
bound|renew) /usr/share/udhcpc/default.script "$1"; ip -4 addr show dev eth1 2>/dev/null | grep -Fq 'inet 192.168.42.1/' || ip addr add dev eth1 192.168.42.1/24 2>/dev/null || :;;
esac
EOF
chmod 700 "$eh" || { rm -f "$eh"; trap - EXIT HUP INT TERM; return 0; }
for i in 1 2 3; do
[ -d /sys/class/net/eth1 ] || break
eth1_wait_free || break
eth1_dhcp && { eth1_fb; break; }
udhcpc -i eth1 -q -f -t 5 -T 2 -n -s "$eh"
eth1_fb
eth1_dhcp && break
[ "$i" -lt 3 ] && sleep 4
done
rm -f "$eh"
trap - EXIT HUP INT TERM
return 0
}

service_boot() {
set -eu
umask 077
D=/tmp/mnt/data_persist/open-connect
R=/tmp/open-connect
rd() { [ "$(readlink -f "$1" 2>/dev/null || :)" = "$1" ] && [ "$(stat -c '%a:%u:%g' "$1")" = 700:0:0 ]; }
service_config settings
test "$(id -u)" = 0
rd "$D" && rd "$R" && rf "$R/lock" || exit 1
n=
if rf "$D/record"; then IFS='|' read -r _ _ _ _ _ _ _ _ _ _ _ _ n _ < "$D/record" || n=; fi
[ "$n" = installed ] || sleep 4
exec 9<>"$R/lock"
t=0
until flock -n -x 9; do t=$((t+1)); [ "$t" -lt 80 ] || exit 0; /bin/busybox usleep 100000; done
absent "$service_runtime" || exit 0
rf "$D/record" && [ "$(wc -l < "$D/record")" -eq 1 ] || exit 1
IFS='|' read -r fmt ph _ pkg _ cur bf af _ _ _ boot _ ex < "$D/record"
[ "$fmt:$ph:$bf:$af" = OC1:active:-:- ] && [ -z "$ex" ] || exit 1
[ -L "$R/boot-id" ] && [ "$(stat -c '%s:%u:%g' "$R/boot-id")" = 36:0:0 ] && [ "$boot" = "$(readlink "$R/boot-id")" ] || exit 1
hex "$pkg" 64 && hex "$cur" 64 || exit 1
rf "$R/selected" && [ "$(cat "$R/selected")" = "$cur" ] || exit 1
P=$D/packages/$pkg
rd "$P" && rf "$P/files.sha256" || exit 1
hs=
if rd "$R/ignition" && rf "$R/ignition/flush" && [ -x "$R/ignition/flush" ]; then hs=$R/ignition/flush; fi
if [ -n "$hs" ]; then d=$("$hs" h "$P/files.sha256"); else d=$(openssl dgst -sha256 < "$P/files.sha256"); fi
[ "${d##* }" = "$pkg" ]
seen='|'; exp=; cnt=0; mn=0; set --
while read -r d nm ex; do
hex "$d" 64 && [ -n "$nm" ] && [ -z "$ex" ] || exit 1
case "$nm" in .|..|*[!a-zA-Z0-9.-]*) exit 1;; esac
case "$seen" in *"|$nm|"*) exit 1;; esac
seen="$seen$nm|"
case "$nm" in service.sh|api|flush) mn=$((mn+1));; esac
rf "$P/$nm" || exit 1
set -- "$@" "$P/$nm"
exp="$exp$d *$P/$nm
"
cnt=$((cnt+1)); [ "$cnt" -le 64 ]
done < "$P/files.sha256"
[ "$mn" = 3 ] && [ -x "$P/flush" ] || exit 1
ac=0
for f in "$P"/* "$P"/.[!.]* "$P"/..?*; do
if absent "$f"; then continue; fi
rf "$f"; ac=$((ac+1))
done
[ "$ac" -eq "$((cnt+1))" ]
if [ -n "$hs" ]; then act=$("$hs" H "$@"); else act=$(openssl dgst -sha256 -r "$@"); fi
[ "$act" = "${exp%?}" ]
record_read && [ "$R_PHASE:$R_BACKEND:$R_CURRENT:$R_BOOT" = "active:$pkg:$cur:$boot" ] || fail state_changed
service_stage boot "$pkg"
if rf "$R/access-selected" && IFS= read -r acc < "$R/access-selected" &&
hex "$acc" 64 && rf "$D/snapshots/$acc/access" &&
IFS='|' read -r _ ssh _ < "$D/snapshots/$acc/access" && [ "$ssh" = 1 ]; then
(exec 9>&-; service_eth1_dhcp) </dev/null >/dev/null 2>&1 &
fi
}

case "${0##*/}" in service.sh) [ "${1:-}" = boot ] || exit 1; service_boot;; esac
