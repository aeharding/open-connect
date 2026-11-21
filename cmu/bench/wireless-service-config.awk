# SPDX-License-Identifier: AGPL-3.0-or-later
# Exact v74 normal SM input; unrelated OEM hardware/GPS/reset policy is retained.
BEGIN {
    if (helper !~ /^\/tmp\/mnt\/data_persist\/oc-bench-wireless\/wireless-prepare.sh$/) exit 1
}
/<service / && /name="jciMMUI"/ {
    if (sub(/display=filtered-touchscreen0"/, "display=filtered-touchscreen0, wcp\"") != 1) exit 1
    mmui++
}
/<service / && /name="(jciUSBMGR|jciCARPLAY|jciBCA|blm_nms_svc)"/ {
    if ($0 ~ / args=/ || sub(/>$/, " args=\"wcp\">") != 1) exit 1
    simple++
}
/<service / && /name="bds"/ {
    if (sub(/args="-interface dbus"/, "args=\"-interface dbus -wcp\"") != 1) exit 1
    bds++
}
/<service / && /name="start_network"/ {
    if (sub(/args="UCP"/, "args=\"\"") != 1) exit 1
    network++
}
/<service / && /name="devicemanager"/ {
    manager++
    print "        <service type=\"process\" name=\"open_connect_wireless_config\" path=\"/bin/busybox\" args=\"timeout -t 15 sh " helper "\" autorun=\"yes\" retry_count=\"0\" reset_board=\"no\" ready_flag=\"/tmp/oc-bench-wireless/config-ready\" exit_allowed=\"yes\" started_after_exit_allowed=\"yes\">"
    print "            <dependency type=\"service\" value=\"jciVBS\"/>"
    print "        </service>"
    print
    print "            <dependency type=\"service\" value=\"open_connect_wireless_config\"/>"
    next
}
{ print }
END { if (mmui != 1 || simple != 4 || bds != 1 || network != 1 || manager != 1) exit 1 }
