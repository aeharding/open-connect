# SPDX-License-Identifier: AGPL-3.0-or-later
# preferences.awk supplies the authenticated OC2 policy. Never renumber UIAs.
function ui_reject() { ui_invalid=1; exit 1 }
function ui_attr_count(line, name, probe) {
    probe=line
    return gsub("[ \t]" name "[ \t]*=", "", probe)
}
function ui_attr(line, name, value) {
    if(ui_attr_count(line,name)!=1 || !match(line,"[ \t]" name "=\"[^\"]*\"")) ui_reject()
    value=substr(line,RSTART,RLENGTH);sub("^[ \t]" name "=\"","",value);sub(/"$/,"",value)
    return value
}
function ui_enabled(group) {
    return prefs["base"]!="1" || group=="keep" || (group!="base" && prefs["service." group]=="1")
}
BEGIN {
    if(operation!="compose" || invalid || (ui_mode!="mmui" && ui_mode!="plugins")) ui_reject()
    while((ui_read=getline ui_line < modules)>0) {
        if(ui_line~/^#/) continue
        if(split(ui_line,ui_fields,"\t")!=4) ui_reject()
        ui_kind=ui_fields[1];ui_name=ui_fields[2];ui_group=ui_fields[3];ui_pin=ui_fields[4]
        if(ui_group!~/^(keep|base|pandora|android-auto|siriusxm)$/ || ui_name!~/^[a-z0-9_.-]+$/) ui_reject()
        if(ui_kind=="uia") {
            if(ui_name in ui_ids || ui_pin!~/^[0-9]+$/ || ui_pin in ui_seen_id) ui_reject()
            ui_ids[ui_name]=ui_pin;ui_seen_id[ui_pin]=1;ui_groups[ui_name]=ui_group;ui_count++
        } else if(ui_kind=="vui") {
            if(ui_name in ui_pins || length(ui_pin)!=64 || ui_pin~/[^a-f0-9]/) ui_reject()
            ui_pins[ui_name]=ui_pin;ui_plugin_group[ui_name]=ui_group
            ui_order[++ui_plugins]=ui_name
        } else ui_reject()
    }
    close(modules)
    if(ui_read<0 || ui_count!=43 || ui_plugins!=56 || ui_ids["system"]!="1") ui_reject()
    if(ui_mode=="plugins") {
        if(prefs["base"]=="1") for(ui_i=1;ui_i<=ui_plugins;ui_i++) {
            ui_name=ui_order[ui_i]
            if(ui_enabled(ui_plugin_group[ui_name])) print ui_name
        }
        exit
    }
}
ui_mode=="mmui" {
    if($0~/^[ \t]*<Config[ \t]/) {
        if(ui_omit) ui_reject()
        ui_name=ui_attr($0,"name");ui_id=ui_attr($0,"uiaid")
        if(!(ui_name in ui_ids) || ui_seen[ui_name]++ || ui_ids[ui_name]!=ui_id) ui_reject()
        ui_hits++
        ui_omit=!ui_enabled(ui_groups[ui_name])
        if(ui_name=="system" && prefs["warning"]=="1") {
            if(sub(/libpath="\/jci\/mmui\/uia\/" lib="libjciuiasystem.so"/,"libpath=\"/tmp/open-connect/feature/\" lib=\"uia.so\"")!=1) ui_reject()
        }
        if(ui_omit && (/\/>[ \t]*$/ || /<\/Config>[ \t]*$/)) {ui_omit=0;next}
    }
    if(ui_omit) {if(/^[ \t]*<\/Config>[ \t]*$/)ui_omit=0;next}
    print
}
END {
    if(ui_invalid || invalid || (ui_mode=="mmui" && (ui_hits!=43 || ui_omit))) exit 1
}
