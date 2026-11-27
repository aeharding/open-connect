#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later

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
  service_now=$((${tick%.*} * 100 + 1${tick#*.} - 100))
}

service_usb_retained() (
  local format deadline revision lease current=-
  test -L "$1/admitted" && lease=$(readlink "$1/admitted") || return 1
  test "$(stat -c %s "$1/admitted")" -eq "${#lease}" || return 1
  IFS='|' read -r format deadline revision <<LEASE
$lease
LEASE
  test "$format" = OCUSB1 && test "$lease" = "$format|$deadline|$revision" || return 1
  case "$deadline" in ''|*[!0-9]*) return 1;; esac
  test "${#deadline}" -le 12 || return 1
  service_tick
  test "$deadline" -gt "$service_now" && test "$deadline" -le "$((service_now+12000))" || return 1
  if ! absent "$D/record"; then
    record_read || return 1
    case "$R_PHASE" in active|removed) current=$R_CURRENT;; *) return 1;; esac
  elif ! absent "$D"; then return 1
  fi
  test "$revision" = "$current"
)

service_discard_child() {
  if test -n "$2" && test "$(awk '{print $4 ":" $22}' "/proc/$1/stat" 2>/dev/null)" = "$$:$2"; then
    kill -TERM "$1" || :
    /bin/busybox usleep 10000
    if test "$(awk '{print $4 ":" $22}' "/proc/$1/stat" 2>/dev/null)" = "$$:$2"; then kill -KILL "$1" || :; fi
    wait "$1" 2>/dev/null || :
  fi
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
  elif test -n "$3" && test "${pending_published:-false}" != true; then
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
  local package_id=$1 kind=${2:-full} work digest name extra token expected= actual count=0 linked shared
  local seen='|' copied= reuse=false links
if absent "$R/sessions"; then mkdir -m 700 "$R/sessions"; fi
private_dir "$R/sessions" || fail invalid_sessions
work=$(mktemp -d "$R/sessions/session-XXXXXX")
service_staging_work=$work
trap 'service_discard_private "$service_staging_work"' EXIT
trap 'exit 1' HUP INT TERM
directory "$P" || fail invalid_source
if test "$kind" = usb; then file "$P/files.sha256" || fail invalid_source; fi
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
  case "$kind:$name" in boot:runtime.js|boot:dialog.js|boot:settings.js|boot:service.sh|boot:state.sh|boot:flush)
    for shared in "$R/feature/$name" "$R/ignition/$name"; do
      if test -f "$shared" && test ! -L "$shared"; then
        if test "$name" = flush && test "$(stat -c %a "$shared")" != 700; then continue; fi
        ln "$shared" "$work/$name" || fail runtime_link_failed
        linked=true
        break
      fi
    done
    ;;
  esac
  if test "$linked" = false; then
    set -- "$@" "$P/$name"
    copied="$copied$name
"
  fi
done < "$P/files.sha256"
if test "$kind" = boot; then test "$count" -eq 16 || fail incomplete_runtime; fi
case "$kind:${P%/*}:${P##*/}" in usb:/tmp:oc-usb-??????)
  if private_dir "$P" && links=$(stat -c %h "$@" "$P/files.sha256") &&
    printf '%s\n' "$links" | awk '$0!="1"{bad=1}END{exit bad}'; then reuse=true; fi
  ;;
esac
if test "$reuse" = true; then
  ln "$@" "$P/files.sha256" "$work/" || fail runtime_link_failed
  copied=
else
  cp "$@" "$P/files.sha256" "$work/"
fi
set -- "$work/files.sha256"
while IFS= read -r name; do
  if test -n "$name"; then set -- "$@" "$work/$name"; fi
done <<COPIED
$copied
COPIED
chmod 600 "$@"
chmod 700 "$work/api" "$work/flush"
set --
while read -r digest name extra; do
  if test -f "$work/$name" && test ! -L "$work/$name"; then set -- "$@" "$work/$name"; fi
done < "$P/files.sha256"
sha_is "$work/files.sha256" "$package_id" || fail damaged_runtime
actual=$(openssl dgst -sha256 -r "$@") || fail damaged_runtime
test "$actual" = "${expected%?}" || fail damaged_runtime
if test "$kind" = usb; then
  uuid > "$work/token"
else
  if absent "$R/token"; then uuid > "$R/token.next"; mv "$R/token.next" "$R/token"; fi
  file "$R/token" && test "$(wc -c < "$R/token")" -eq 33 || fail token_failed
  ln "$R/token" "$work/token" || fail token_failed
fi
token=$(cat "$work/token"); hex "$token" 32 || fail token_failed
printf '%s\n' "$work"
trap - EXIT HUP INT TERM
)

service_listen() {
local work=$1 pid start deadline
service_config "${2:-settings}"
stop_listener
if ! absent "$service_runtime"; then test -L "$service_runtime" || fail invalid_runtime_pointer; fi
pending_pid=; pending_start=; pending_work=$work; pending_cancel=false; pending_published=false
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
    fail listener_start_failed
  fi
  /bin/busybox usleep 10000
done
if test "$pending_cancel" = true; then fail listener_start_cancelled; fi
printf '%s %s %s\n' "$pid" "$start" "$work" > "$service_listener.next"
ln -sfn "$work" "$service_runtime"
pending_published=true
mv -f "$service_listener.next" "$service_listener"
runtime=$work
trap 'exit 1' HUP INT TERM
if test "$pending_cancel" = true; then fail listener_start_cancelled; fi
trap - EXIT HUP INT TERM
unset pending_pid pending_start pending_work pending_cancel pending_published
}

service_stage() {
  service_config settings
  if test "$1" = boot; then absent "$service_runtime" || fail busy; fi
  service_files "$2" "$1"
  service_listen "$runtime" "$1"
}

boot_select_verified() {
  local d=$D/packages/$R_BACKEND e a f
  test "$role" = settings || return 2
  file "$P/files.sha256" && sha_is "$P/files.sha256" "$R_BACKEND" || return 1
  awk 'NF==2&&$2=="boot-select"{n++}END{exit n!=1}' "$P/files.sha256" || return 2
  e=$(awk -v d="$d" 'BEGIN{split("boot-select state.sh firmware.sh access.sh flush VERSION preferences.awk services.tsv sm-profile.awk ui-profile.awk ui-modules.tsv system-hook.js base-logging.js",m," ");for(i in m)w[m[i]]=1}
NF==2&&($2 in w){if(length($1)!=64||$1~/[^a-f0-9]/||s[$2]++){b=1;exit 1};r[++n]=$1" *"d"/"$2}
END{if(b||n!=13)exit 1;for(i=1;i<=n;i++)print r[i]}' "$P/files.sha256") || return 1
  private_dir "$d" && file "$d/boot-select" && test "$(stat -c '%a:%u:%g' "$d/boot-select")" = "700:$(id -u):$(id -g)" || return 1
  set --
  while read -r _ f; do f=${f#\*}; test -f "$f" && test ! -L "$f" || return 1; set -- "$@" "$f"; done <<F
$e
F
  a=$(sha_many "$@") && test "$a" = "$e" || return 1
  BOOT_SELECT=$d/boot-select
  d=$D/snapshots/$R_CURRENT; private_dir "$d" && file "$d/files.sha256" && sha_is "$d/files.sha256" "$R_CURRENT" || return 1
  absent "$d/boot.plan" && { BOOT_SELECT=; return 2; }
  VERIFIED_PACKAGE=$R_BACKEND; S_CUR=; snapshot_decode "$R_CURRENT" || return 1
  test "$S_SCHEMA:$S_PACKAGE" = "OC2:$R_BACKEND" || { VERIFIED_PACKAGE=; BOOT_SELECT=; return 2; }
}

service_boot() {
  set -eu
  umask 077
  D=/tmp/mnt/data_persist/open-connect
  R=/tmp/open-connect
  service_config settings
  test "$(id -u)" = 0
  test "$(readlink -f "$D")" = "$D" && test "$(stat -c '%a:%u:%g' "$D")" = 700:0:0 || exit 1
  test "$(readlink -f "$R")" = "$R" && test "$(stat -c '%a:%u:%g' "$R")" = 700:0:0 || exit 1
  test -f "$R/lock" && test ! -L "$R/lock" || exit 1
  notice=
  if test -f "$D/record" && test ! -L "$D/record"; then
    IFS='|' read -r _ _ _ _ _ _ _ _ _ _ _ _ notice _ < "$D/record" || notice=
  fi
  if test "$notice" != installed; then sleep 4; fi
  exec 9<>"$R/lock"
  tries=0
  until flock -n -x 9; do
    tries=$((tries+1)); test "$tries" -lt 80 || exit 0
    /bin/busybox usleep 100000
  done
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
  hasher=
  if test "$(readlink -f "$R/ignition" 2>/dev/null || :)" = "$R/ignition" &&
    test "$(stat -c '%a:%u:%g' "$R/ignition")" = 700:0:0 &&
    test -f "$R/ignition/flush" && test ! -L "$R/ignition/flush" && test -x "$R/ignition/flush"; then
    hasher=$R/ignition/flush
  fi
  if test -n "$hasher"; then digest=$("$hasher" h "$P/files.sha256"); else digest=$(openssl dgst -sha256 < "$P/files.sha256"); fi
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
  test "$mandatory" = 5 && test -x "$P/flush" || exit 1
  actual_count=0
  for item in "$P"/* "$P"/.[!.]* "$P"/..?*; do
    if test ! -e "$item" && test ! -L "$item"; then continue; fi
    test -f "$item" && test ! -L "$item"
    actual_count=$((actual_count+1))
  done
  test "$actual_count" -eq "$((count+1))"
  if test -n "$hasher"; then actual=$("$hasher" H "$@"); else actual=$(openssl dgst -sha256 -r "$@"); fi
  test "$actual" = "${expected%?}"
  . "$P/state.sh"
  record_read && test "$R_PHASE:$R_BACKEND:$R_CURRENT:$R_BOOT" = "active:$package:$current:$boot" || fail state_changed
  service_stage boot "$package"
}

case "${0##*/}" in service.sh) test "${1:-}" = boot || exit 1; service_boot;; esac
