#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Reference experiment: exact stock files, declared owner SSH access, root RO.
set -eu
test "$(id -u)" = 0
awk '$0=="JCI_SW_VER=\"MAZ_CMU-150_74.00.324\""{v++}
     $0=="JCI_SW_VER_PATCH=\"A\""{p++}
     $0=="JCI_SW_FLAVOR=\"cmu150_NA\""{f++}
     END{exit !(v==1&&p==1&&f==1)}' /jci/version.ini
test ! -e /tmp/mnt/data_persist/open-connect
test ! -e /tmp/open-connect
test -d /sys/class/nvram/nv-config/keys
test ! -e /sys/class/nvram/nv-config/keys/lvds_speed_restriction
awk '$1=="/dev/ffx01p1"&&$2=="/"&&$4=="ro,noatime"{n++} END{exit n!=1}' /proc/mounts
sha() { v=$(openssl dgst -sha256 < "$1"); printf '%s\n' "${v##* }"; }
test "$(sha /usr/bin/autostart)" = a8d019650c2a17a50b5ff39435f916c2cbeb3556af128fd913b9714b380e06bd
test "$(sha /usr/bin/runlogin)" = b77e4dadaa1173578e58d319dd3d37bb24117cb9b3baf73731c401f5a47360b8
test "$(sha /jci/sm/sm.conf)" = fa3484d7c644393ab6cb083990e483201129a207e7755459296dde8ec82a4d84
test "$(sha /etc/devmgr_config_master.xml)" = 9f1811e2d9a905ba9060a9c20b8d91c18aaa5c079512e3261b51cf0114fc857b
test "$(sha /jci/scripts/get_board_type.sh)" = 2c66145fe9c76cbbed471b6e190c57837c72ae5a3cf8f750c6c87a689ded20da
test "$(cat /sys/class/gpio/ACC_Sense/value)" = 1
printf '\nSTOCK_BOOT|'; cat /proc/sys/kernel/random/boot_id
printf 'OWNER_SSH_SHA|'; sha /etc/ssh/sshd_config
