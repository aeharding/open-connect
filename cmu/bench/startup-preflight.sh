#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Reference experiment: pinned condition, declared owner SSH access, root RO.
set -eu
condition=${1:-stock} package=${2:--} pandora=${3:--}
case "$pandora" in -|0|1) ;; *) exit 64;; esac
test "$(id -u)" = 0
awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_74.00.324\""{v++}
     $0=="JCI_SW_VER_PATCH=\"A\""{p++}
     $0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++}
     END{exit !(v==1&&p==1&&f==1)}' /jci/version.ini
test -d /sys/class/nvram/nv-config/keys
awk '$1=="/dev/ffx01p1"&&$2=="/"&&$4=="ro,noatime"{n++} END{exit n!=1}' /proc/mounts
sha() { v=$(openssl dgst -sha256 < "$1"); printf '%s\n' "${v##* }"; }
case "$condition" in
stock)
    test "$pandora" = -
    test "$package" = -
    test ! -e /tmp/mnt/data_persist/open-connect
    test ! -e /tmp/open-connect
    test ! -e /sys/class/nvram/nv-config/keys/lvds_speed_restriction
    test "$(sha /usr/bin/autostart)" = a8d019650c2a17a50b5ff39435f916c2cbeb3556af128fd913b9714b380e06bd
    ;;
open-connect)
    case "$package" in ''|*[!a-f0-9]*) exit 64;; esac
    test "${#package}" = 64
    P=$(readlink -f /tmp/open-connect/runtime)
    test "$(sha "$P/files.sha256")" = "$package"
    test "$(sha /tmp/mnt/data_persist/open-connect/originals/autostart)" = a8d019650c2a17a50b5ff39435f916c2cbeb3556af128fd913b9714b380e06bd
    test "$(cat /sys/class/nvram/nv-config/keys/lvds_speed_restriction)" = disable
    current=$(awk -F '|' '$1=="OC1"&&$2=="active"&&NF==13{print $6}' /tmp/mnt/data_persist/open-connect/record)
    test "${#current}" = 64
    test "$(cat /tmp/open-connect/selected)" = "$current"
    printf '\nCANDIDATE_STATUS|'
    sh "$P/backend.sh" api - status - - -
    if test "$pandora" != -; then
        test "$(sha /jci/sm/smctl)" = a51a03ce7bc1f602ccca7b15af8c9698fed5debfb904f01fcc358f57ca46330f
        printf '\nPANDORA_INFO_BEGIN\n'
        LD_LIBRARY_PATH=/jci/lib:/usr/lib:/lib timeout -t 8 /jci/sm/smctl --get --type info --name blm_ira_pandora
        printf 'PANDORA_INFO_END\nPANDORA_STARTS|'
        awk -F , '$2=="blm_ira_pandora"&&$3=="SM_SVC_CMD_START"{n++} END{print n+0}' /tmp/smevents.txt
    fi
    ;;
*) exit 64;;
esac
test "$(sha /usr/bin/runlogin)" = b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8
test "$(sha /jci/sm/sm.conf)" = fa3484d7c644393ab6cb083990e483201129a207e7755459296dde8ec82a4d84
test "$(sha /etc/devmgr_config_master.xml)" = 9f1811e2d9a905ba9060a9c20b8d91c18aaa5c079512e3261b51cf0114fc857b
test "$(sha /jci/scripts/get_board_type.sh)" = 2c66145fe9c76cbbed471b6e190c57837c72ae5a3cf8f750c6c87a689ded20da
test "$(sha /jci/scripts/stage_1.sh)" = "$(sha /tmp/mnt/data_persist/oc-bench-startup/startup-hook.sh)"
sh /tmp/mnt/data_persist/oc-bench-startup/startup-profile.sh --check
test "$(cat /sys/class/gpio/ACC_Sense/value)" = 1
printf '\nREFERENCE_BOOT|'; cat /proc/sys/kernel/random/boot_id
printf 'OWNER_SSH_SHA|'; sha /etc/ssh/sshd_config
