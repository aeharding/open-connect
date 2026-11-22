# SPDX-License-Identifier: AGPL-3.0-or-later
# Exact v74 normal/WCP SM inputs; unrelated OEM hardware/GPS/reset policy is retained.
BEGIN {
    helper = "/tmp/open-connect/feature/wireless.sh"
    if (pandora != 0 && pandora != 1) exit 1
    if (wireless != 0 && wireless != 1) exit 1
    if (base != 0 && base != 1) exit 1
}
base && /<service / && /name="stage_wifi"/ { wifi = 1; wifi_count++ }
wifi && /<dependency / && /type="service"/ && /value="stage_3"/ { wifi_stage3++ }
wifi && /<dependency / && /type="service"/ && /value="blm_ira_aha"/ { wifi_aha++; next }
wifi && /<\/service>/ {
    if (wifi_stage3 != 1 || wifi_aha != 1) exit 1
    wifi = 0
}
wireless && /<service / && /name="jciMMUI"/ {
    if ($0 !~ /display=filtered-touchscreen0, wcp"/ && sub(/display=filtered-touchscreen0"/, "display=filtered-touchscreen0, wcp\"") != 1) exit 1
    mmui++
}
wireless && /<service / && /name="(jciUSBMGR|jciCARPLAY|jciBCA|blm_nms_svc)"/ {
    if ($0 !~ / args="wcp"/ && ($0 ~ / args=/ || sub(/>$/, " args=\"wcp\">") != 1)) exit 1
    simple++
}
wireless && /<service / && /name="bds"/ {
    if ($0 !~ /args="-interface dbus -wcp"/ && sub(/args="-interface dbus"/, "args=\"-interface dbus -wcp\"") != 1) exit 1
    bds++
}
wireless && /<service / && /name="start_network"/ {
    if ($0 !~ /args=""/ && sub(/args="UCP"/, "args=\"\"") != 1) exit 1
    network++
}
wireless && /<service / && /name="devicemanager"/ {
    manager++
    print "        <service type=\"process\" name=\"open_connect_wireless\" path=\"/bin/busybox\" args=\"timeout -t 15 sh " helper "\" autorun=\"yes\" retry_count=\"0\" reset_board=\"no\" ready_flag=\"/tmp/open-connect/feature/wireless-ready\" exit_allowed=\"yes\" started_after_exit_allowed=\"yes\">"
    print "            <dependency type=\"service\" value=\"jciVBS\"/>"
    print "        </service>"
    print
    print "            <dependency type=\"service\" value=\"open_connect_wireless\"/>"
    next
}
/<service / && /name="blm_ira_pandora"/ {
    if (pandora == 0 && sub(/autorun="yes"/, "autorun=\"no\"") != 1) exit 1
    pandora_count++
}
{ print }
END {
    if (pandora_count != 1 || (base && (wifi_count != 1 || wifi))) exit 1
    if (wireless && (mmui != 1 || simple != 4 || bds != 1 || network != 1 || manager != 1)) exit 1
}
