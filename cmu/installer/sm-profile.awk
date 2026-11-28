# SPDX-License-Identifier: AGPL-3.0-or-later
# One final SM writer. preferences.awk loads the verified catalog and OC2 data.
function attribute_count(name, probe) {
    probe=$0
    return gsub("[ \t]" name "[ \t]*=", "", probe)
}
function attribute(name, value) {
    if(attribute_count(name)!=1 || !match($0,"[ \t]" name "=\"[^\"]*\"")) refuse()
    value=substr($0,RSTART,RLENGTH)
    sub("^[ \t]" name "=\"", "", value);sub(/"$/, "", value)
    return value
}
function put_attribute(name, value, previous, at, size, space) {
    previous=attribute(name);at=RSTART;size=RLENGTH;space=substr($0,at,1)
    $0=substr($0,1,at-1) space name "=\"" value "\"" substr($0,at+size)
}
function append_attribute(name, value) {
    if(attribute_count(name) || $0~/\/>[ \t]*$/ || sub(/>$/," " name "=\"" value "\">")!=1) refuse()
}
BEGIN {
    if(operation!="compose" || invalid) refuse()
    early_wireless=(prefs["base"]=="1" && prefs["wireless"]=="1")
    split("jciDAB jcitv blm_ira_stitcher irsstitcher_server blm_ira_aha offboard_service jcidvd",base_names," ")
    for(i=1;i<=7;i++) {
        name=base_names[i]
        if(name in service_owner) refuse()
        base_hits[name]=0
    }
    base_affinity["jciVBS"]=0
    base_affinity["system_mazda_my14"]=0
    split("jciUSBMGR jciCARPLAY jciBCA blm_nms_svc",wireless_names," ")
    for(i=1;i<=4;i++) wireless_hits[wireless_names[i]]=0
}
/[ \t](name|value)[ \t]*=[ \t]*["']open_connect_(settings|wireless|gap2|nav)["']/ {refuse()}
omit_service {
    if(/^[ \t]*<\/service>[ \t]*$/) {omit_service=0;sm_name=""}
    else if(/<service[ \t]|<\/services>/) refuse()
    next
}
/^[ \t]*<service[ \t]/ {
    sm_name=attribute("name")
    if(sm_name in service_owner) {
        name=sm_name
        service_hits[name]++
        owner=service_owner[name]
        expected="yes"
        if(owner=="siriusxm" && name~/^(jcixm|jcixmad|jciXMDATA)$/) expected="no"
        if(attribute("autorun")!=expected) refuse()
        if(prefs["service." owner]=="0") {
            if(owner=="siriusxm") {omit_service=1;next}
            put_attribute("autorun","no")
        }
    }
    if(prefs["base"]=="1" && sm_name in base_hits) {
        name=sm_name
        base_hits[name]++
        if(attribute("autorun")!="yes") refuse()
        put_attribute("autorun","no")
    }
    if(prefs["base"]=="1" && sm_name in base_affinity) {
        base_affinity[sm_name]++
        append_attribute("affinity_mask","0x03")
    }
    if(prefs["base"]=="1" && prefs["service.pandora"]=="0" && sm_name=="irs_server") {
        irs++
        if(attribute("autorun")!="yes") refuse()
        put_attribute("autorun","no")
    }
    if(sm_name=="devices" && prefs["touch"]=="2") {
        devices++
        if(attribute("path")!="/jci/devices/svc-com-jci-cpp-devices.so") refuse()
        put_attribute("path","/tmp/open-connect/feature/touch-disable.so")
    }
    if(sm_name=="stage_1") stage++
    if(sm_name=="stage_3") stage3++
    if(sm_name=="stage_wifi") wifi_stage++
    if(sm_name=="jciVBS") vbs++
    if(sm_name=="jciMMUI" && prefs["base"]=="1" && prefs["warning"]!="1") {
        mmui_path++
        if(attribute("path")!="/jci/mmui/svcjcimmui.so") refuse()
        put_attribute("path","/tmp/open-connect/feature/mmui.so")
    }
    if(sm_name=="jciVUI" && prefs["base"]=="1") {
        vui++
        if(attribute("path")!="/jci/vui/svcjcivui.so") refuse()
        put_attribute("path","/tmp/open-connect/feature/vui.so")
    }
}
early_wireless && /^[ \t]*<service[ \t]/ && sm_name=="jcinavi" {
    nav++
    if(attribute("autorun")!="yes") refuse()
    print
    print "            <dependency type=\"service\" value=\"open_connect_nav\"/>"
    next
}
early_wireless && /^[ \t]*<service[ \t]/ && sm_name=="stage_gap2" {
    gap2++
    if(attribute("autorun")!="yes") refuse()
    print
    print "            <dependency type=\"service\" value=\"open_connect_gap2\"/>"
    next
}
early_wireless && /^[ \t]*<dependency[ \t]/ && sm_name=="stage_gap2" {
    dependency=attribute("value")
    if(attribute("type")!="service") refuse()
    if(dependency=="stage_3") gap2_stage3++
}
prefs["base"]=="1" && /^[ \t]*<dependency[ \t]/ && sm_name~/^(stage_vr|stage_gap2|stage_wifi)$/ {
    dependency=attribute("value")
    if(attribute("type")!="service") refuse()
    if(dependency=="stage_ir") refuse()
    if(dependency=="blm_ira_aha") {
        aha_edges[sm_name]++
        if(sm_name=="stage_wifi" && early_wireless) {wifi_aha++;next}
        put_attribute("value","stage_ir")
    }
}
prefs["wireless"]=="1" && /^[ \t]*<service[ \t]/ && sm_name=="jciMMUI" {
    mmui++
    if(prefs["base"]=="1") append_attribute("affinity_mask","0x03")
    args=attribute("args")
    if(args!~/display=filtered-touchscreen0, wcp$/) {
        if(sub(/display=filtered-touchscreen0$/,"display=filtered-touchscreen0, wcp",args)!=1) refuse()
        put_attribute("args",args)
    }
}
prefs["wireless"]=="1" && /^[ \t]*<service[ \t]/ {
    if(sm_name in wireless_hits) {
        name=sm_name
        wireless_hits[name]++
        if(prefs["base"]=="1" && name=="jciCARPLAY") append_attribute("affinity_mask","0x03")
        if(attribute_count("args")) {
            if(attribute("args")!="wcp") refuse()
        } else append_attribute("args","wcp")
    }
}
prefs["wireless"]=="1" && /^[ \t]*<service[ \t]/ && sm_name=="bds" {
    bds++
    args=attribute("args")
    if(args!="-interface dbus -wcp") {
        if(args!="-interface dbus") refuse()
        put_attribute("args","-interface dbus -wcp")
    }
}
prefs["wireless"]=="1" && /^[ \t]*<service[ \t]/ && sm_name=="start_network" {
    network++
    args=attribute("args")
    if(args!="") {
        if(args!="UCP") refuse()
        put_attribute("args","")
    }
}
prefs["wireless"]=="1" && /^[ \t]*<service[ \t]/ && sm_name=="devicemanager" {
    manager++
    print "        <service type=\"process\" name=\"open_connect_wireless\" path=\"/bin/busybox\" args=\"timeout -t 15 sh /tmp/open-connect/feature/wireless.sh\" autorun=\"yes\" retry_count=\"0\" reset_board=\"no\" ready_flag=\"/tmp/open-connect/feature/wireless-ready\" exit_allowed=\"yes\" started_after_exit_allowed=\"yes\">"
    print "            <dependency type=\"service\" value=\"jciVBS\"/>"
    print "        </service>"
    print
    print "            <dependency type=\"service\" value=\"open_connect_wireless\"/>"
    next
}
early_wireless && /^[ \t]*<dependency[ \t]/ && sm_name=="bds" {
    dependency=attribute("value")
    if(attribute("type")!="service") refuse()
    if(dependency=="stage_3") {
        bds_stage++
        put_attribute("value","jciUSBMGR")
    } else if(dependency=="jciUSBMGR") refuse()
    else if(dependency=="settings") bds_settings++
    else if(dependency=="dmserver") bds_registry++
}
early_wireless && /^[ \t]*<dependency[ \t]/ && sm_name=="stage_wifi" {
    dependency=attribute("value")
    if(attribute("type")!="service") refuse()
    if(dependency=="stage_3") wifi_parent++
}
/<\/services>/ {
    if(early_wireless) {
        print "        <service type=\"process\" name=\"open_connect_nav\" path=\"/bin/busybox\" args=\"timeout -t 22 /bin/busybox sh /tmp/open-connect/feature/defer-nav.sh\" autorun=\"yes\" retry_count=\"0\" reset_board=\"no\" affinity_mask=\"0x02\" ready_flag=\"/tmp/open-connect/feature/nav-ready\" exit_allowed=\"yes\" started_after_exit_allowed=\"yes\">"
        print "            <dependency type=\"service\" value=\"stage_3\"/>"
        print "        </service>"
        print "        <service type=\"process\" name=\"open_connect_gap2\" path=\"/bin/busybox\" args=\"timeout -t 15 /bin/busybox sh /tmp/open-connect/feature/defer-gap2.sh\" autorun=\"yes\" retry_count=\"0\" reset_board=\"no\" affinity_mask=\"0x02\" ready_flag=\"/tmp/open-connect/feature/gap2-ready\" exit_allowed=\"yes\" started_after_exit_allowed=\"yes\">"
        print "            <dependency type=\"service\" value=\"jciCARPLAY\"/>"
        print "            <dependency type=\"service\" value=\"blm_nms_svc\"/>"
        print "        </service>"
    }
    print "        <service type=\"process\" name=\"open_connect_settings\" path=\"/bin/busybox\" args=\"timeout -t 20 sh /tmp/open-connect/feature/service.sh boot\" autorun=\"yes\" retry_count=\"0\" reset_board=\"no\" affinity_mask=\"0x02\" exit_allowed=\"yes\" started_after_exit_allowed=\"yes\">"
    print "            <dependency type=\"service\" value=\"stage_3\"/>"
    print "        </service>"
    end++
}
/^[ \t]*<\/service>[ \t]*$/ {sm_name=""}
{print}
END {
    if(prefs["touch"]=="2" && devices!=1) exit 1
    if(invalid || omit_service || stage!=1 || stage3!=1 || end!=1) exit 1
    if(early_wireless && (bds_stage!=1 || bds_settings!=1 || bds_registry!=1 ||
       wifi_stage!=1 || wifi_parent!=1 || wifi_aha!=1 ||
       gap2!=1 || gap2_stage3!=1 || nav!=1)) exit 1
    for(name in service_owner) if(service_hits[name]!=1) exit 1
    if(prefs["base"]=="1") {
        if(vui!=1) exit 1
        if(prefs["warning"]!="1" && mmui_path!=1) exit 1
        for(name in base_hits) if(base_hits[name]!=1) exit 1
        for(name in base_affinity) if(base_affinity[name]!=1) exit 1
        if(aha_edges["stage_vr"]!=1 || aha_edges["stage_gap2"]!=1 || aha_edges["stage_wifi"]!=1) exit 1
        if(prefs["service.pandora"]=="0" && irs!=1) exit 1
    }
    if(prefs["wireless"]=="1") {
        if(mmui!=1 || bds!=1 || network!=1 || manager!=1 || vbs!=1) exit 1
        for(name in wireless_hits) if(wireless_hits[name]!=1) exit 1
    }
}
