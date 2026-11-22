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
/[ \t](name|value)[ \t]*=[ \t]*["']open_connect_(settings|wireless)["']/ {refuse()}
/^[ \t]*<service[ \t]/ {
    sm_name=attribute("name")
    if(sm_name in service_owner) {
        name=sm_name
        service_hits[name]++
        if(attribute("autorun")!="yes") refuse()
        if(prefs["service." service_owner[name]]=="0") put_attribute("autorun","no")
    }
    if(prefs["base"]=="1" && sm_name in base_hits) {
        name=sm_name
        base_hits[name]++
        if(attribute("autorun")!="yes") refuse()
        put_attribute("autorun","no")
    }
    if(sm_name=="stage_1") stage++
    if(sm_name=="jciVBS") vbs++
}
prefs["wireless"]=="1" && /^[ \t]*<service[ \t]/ && sm_name=="jciMMUI" {
    mmui++
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
        if(attribute_count("args")) {
            if(attribute("args")!="wcp") refuse()
        } else if($0~/\/>[ \t]*$/ || sub(/>$/," args=\"wcp\">")!=1) refuse()
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
        if(mmui!=1 || bds!=1 || network!=1 || manager!=1 || vbs!=1) exit 1
        for(name in wireless_hits) if(wireless_hits[name]!=1) exit 1
    }
}
