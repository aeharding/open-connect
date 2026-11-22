# SPDX-License-Identifier: AGPL-3.0-or-later
# One final SM writer. preferences.awk loads the verified catalog and OC2 data.
BEGIN {
    if(operation!="compose" || invalid) refuse()
    split("jciDAB jcitv blm_ira_stitcher irsstitcher_server",base_names," ")
    for(i=1;i<=4;i++) {
        name=base_names[i]
        if(name in service_owner) refuse()
        base_hits[name]=0
    }
    split("jciUSBMGR jciCARPLAY jciBCA blm_nms_svc",wireless_names," ")
    for(i=1;i<=4;i++) wireless_hits[wireless_names[i]]=0
}
/name="open_connect_settings"|value="open_connect_settings"|name="open_connect_wireless"|value="open_connect_wireless"/ {refuse()}
/^[ \t]*<service / {
    probe=$0
    if(gsub(/[ \t]name="/,"",probe)!=1 || !match($0,/[ \t]name="[^"]*"/)) refuse()
    sm_name=substr($0,RSTART,RLENGTH)
    sub(/^[ \t]name="/,"",sm_name);sub(/"$/,"",sm_name)
    if(sm_name in service_owner) {
        name=sm_name
        service_hits[name]++
        probe=$0
        if(gsub(/autorun="yes"/,"",probe)!=1) refuse()
        if(prefs["service." service_owner[name]]=="0") sub(/autorun="yes"/,"autorun=\"no\"")
    }
    if(prefs["base"]=="1" && sm_name in base_hits) {
        name=sm_name
        base_hits[name]++
        if(gsub(/autorun="yes"/,"autorun=\"no\"")!=1) refuse()
    }
    if(sm_name=="stage_1") stage++
}
prefs["wireless"]=="1" && /^[ \t]*<service / && sm_name=="jciMMUI" {
    mmui++
    probe=$0;if(gsub(/[ \t]args="/,"",probe)!=1) refuse()
    if($0!~/display=filtered-touchscreen0, wcp"/ &&
        sub(/display=filtered-touchscreen0"/,"display=filtered-touchscreen0, wcp\"")!=1) refuse()
}
prefs["wireless"]=="1" && /^[ \t]*<service / {
    if(sm_name in wireless_hits) {
        name=sm_name
        wireless_hits[name]++
        probe=$0;if(gsub(/[ \t]args="/,"",probe)>1) refuse()
        if($0!~/ args="wcp"/ && ($0~/ args=/ || sub(/>$/," args=\"wcp\">")!=1)) refuse()
    }
}
prefs["wireless"]=="1" && /^[ \t]*<service / && sm_name=="bds" {
    bds++
    probe=$0;if(gsub(/[ \t]args="/,"",probe)!=1) refuse()
    if($0!~/args="-interface dbus -wcp"/ &&
        sub(/args="-interface dbus"/,"args=\"-interface dbus -wcp\"")!=1) refuse()
}
prefs["wireless"]=="1" && /^[ \t]*<service / && sm_name=="start_network" {
    network++
    probe=$0;if(gsub(/[ \t]args="/,"",probe)!=1) refuse()
    if($0!~/args=""/ && sub(/args="UCP"/,"args=\"\"")!=1) refuse()
}
prefs["wireless"]=="1" && /^[ \t]*<service / && sm_name=="devicemanager" {
    manager++
    print "        <service type=\"process\" name=\"open_connect_wireless\" path=\"/bin/busybox\" args=\"timeout -t 15 sh /tmp/open-connect/feature/wireless.sh\" autorun=\"yes\" retry_count=\"0\" reset_board=\"no\" ready_flag=\"/tmp/open-connect/feature/wireless-ready\" exit_allowed=\"yes\" started_after_exit_allowed=\"yes\">"
    print "            <dependency type=\"service\" value=\"jciVBS\"/>"
    print "        </service>"
    print
    print "            <dependency type=\"service\" value=\"open_connect_wireless\"/>"
    next
}
/<\/services>/ {
    print "        <service type=\"process\" name=\"open_connect_settings\" path=\"/bin/busybox\" args=\"timeout -t 20 sh /tmp/open-connect/feature/service.sh boot\" autorun=\"yes\" retry_count=\"0\" reset_board=\"no\" exit_allowed=\"yes\" started_after_exit_allowed=\"yes\">"
    print "            <dependency type=\"service\" value=\"stage_1\"/>"
    print "        </service>"
    end++
}
{print}
END {
    if(invalid || stage!=1 || end!=1) exit 1
    for(name in service_owner) if(service_hits[name]!=1) exit 1
    if(prefs["base"]=="1") for(name in base_hits) if(base_hits[name]!=1) exit 1
    if(prefs["wireless"]=="1") {
        if(mmui!=1 || bds!=1 || network!=1 || manager!=1) exit 1
        for(name in wireless_hits) if(wireless_hits[name]!=1) exit 1
    }
}
