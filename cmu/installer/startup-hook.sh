        # Open Connect: failed selection retains Mazda's normal configuration.
        if timeout -t 25 sh -c 'set -eu
umask 077
read -r entered idle < /proc/uptime || entered=unknown
test "$(id -u)" = 0
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
    boot_select
    startup_stamps_publish
else
    exec 9>&-
    exec sh "$P/boot.sh"
fi
'; then
            SMCFG_NORMALMODE=/tmp/open-connect/feature/sm.conf
            SMCFG_WCPMODE=/tmp/open-connect/feature/sm_WCP.conf
        fi
