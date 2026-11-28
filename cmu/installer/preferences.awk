# SPDX-License-Identifier: AGPL-3.0-or-later
# Canonical OC2 snapshot data and the one packaged Services catalog.
# No value is interpreted as shell or JavaScript. Compose imports this file.
function refuse() {
  invalid=1
  print "invalid_preferences" > "/dev/stderr"
  exit 1
}
function bit(value) { return value=="0" || value=="1" }
function touch_mode(value) { return bit(value) || value=="2" }
# Only the upgrade writer admits retired NA DVD data. Stored snapshots keep
# their package's reader; new snapshots and commands use the current catalog.
function input_service(id) { return id in service_default || (operation=="write" && id=="dvd") }
function service_id(value) {
  return length(value)<=32 && value~/^[a-z][a-z0-9-]*$/ &&
    value!~/^(touch|warning|base|wireless|uart|ssh|carplay-autoshow|source-order|menu-loop|hold-scroll)$/
}
function load_catalog(path, line, columns, fields, id, members, count, i, member, joined, bytes) {
  while ((catalog_read=getline line < path)>0) {
    bytes+=length(line)+1
    if(bytes>16384) refuse()
    if(line~/^#/ || line=="") continue
    fields=split(line,columns,"|")
    id=columns[1]
    if(fields!=6 || !service_id(id) || id in service_default || ++service_count>16 ||
      (service_count>1 && id<=service_ids[service_count-1]) ||
      !bit(columns[3]) || columns[2]=="" || length(columns[2])>64 ||
      columns[5]=="" || columns[6]=="" || length(columns[5])>256 || length(columns[6])>256 ||
      line~/[[:cntrl:]]/) refuse()
    service_ids[service_count]=id
    service_label[id]=columns[2]
    service_default[id]=columns[3]
    service_enable[id]=columns[5]
    service_disable[id]=columns[6]
    count=split(columns[4],members," ")
    if(count<1 || count>8) refuse()
    joined=""
    for(i=1;i<=count;i++) {
      member=members[i]
      if(length(member)>64 || member!~/^[A-Za-z_][A-Za-z0-9_]*$/ || member in service_owner) refuse()
      service_owner[member]=id
      if(i>1) joined=joined " "
      joined=joined member
    }
    if(joined!=columns[4]) refuse()
  }
  close(path)
  if(catalog_read<0 || service_count<1 || catalog_bytes+0!=bytes) refuse()
}
function metadata(value, fields, n, i) {
  n=split(value,fields,":")
  if(n!=3 || fields[1]!~/^[0-7]+$/ || length(fields[1])>4) return 0
  for(i=2;i<=3;i++)
    if(fields[i]!~/^[0-9]+$/ || length(fields[i])>10 || fields[i]+0>4294967295) return 0
  return 1
}
function known_key(key, id) {
  if(key~/^(package|touch|warning|nvram|metadata|base|wireless|service-ids|carplay-autoshow|source-order|menu-loop|hold-scroll)$/) return 1
  if(index(key,"service.")!=1) return 0
  id=substr(key,9)
  return input_service(id)
}
function load_preferences(path, partial, line, key, value, separator, previous, bytes, i, id, count, keys, listed) {
  if((getline line < path)!=1 || line!="OC2") refuse()
  bytes=4
  while((preferences_read=getline line < path)>0) {
    bytes+=length(line)+1
    separator=index(line,"=")
    key=substr(line,1,separator-1);value=substr(line,separator+1)
    if(bytes>1023 || !separator || key<=previous || !known_key(key) || value=="" ||
      index(value,"=") || line~/[[:cntrl:]]/) refuse()
    previous=key;seen[key]=1;prefs[key]=value
  }
  close(path)
  # The caller supplies the regular file's byte count. This also rejects a
  # missing final newline or a truncated NUL interpretation in an older awk.
  if(preferences_read<0 || input_bytes+0!=bytes) refuse()
  if(!seen["package"] || !seen["metadata"] || !seen["nvram"] || !seen["touch"] ||
    !seen["warning"] || !seen["base"] || !seen["wireless"]) refuse()
  for(i=1;i<=service_count;i++) {
    id=service_ids[i]
    if(!partial && !seen["service." id]) refuse()
  }
  if(seen["service-ids"]) {
    count=split(prefs["service-ids"],keys,",");previous=""
    if(count<1 || count>16) refuse()
    for(i=1;i<=count;i++) {
      id=keys[i]
      if(!input_service(id) || id<=previous || !seen["service." id]) refuse()
      previous=id;listed[id]=1
    }
    for(id in service_default) if(seen["service." id] && !(id in listed)) refuse()
  } else if(!partial) refuse()
  if(seen["service.dvd"] && !("dvd" in listed)) refuse()
}
function validate_preferences(key, value) {
  value=prefs["package"]
  if(length(value)!=64 || value~/[^a-f0-9]/ || !metadata(prefs["metadata"]) ||
    prefs["nvram"]!~/^(absent|enable|disable)$/) refuse()
  for(key in prefs)
    if(key!~/^(package|metadata|nvram|service-ids)$/ && !(key=="touch" ? touch_mode(prefs[key]) : bit(prefs[key]))) refuse()
}
function write_preferences(key, keys, count, i, j, swap, bytes, line) {
  for(key in prefs) keys[++count]=key
  for(i=2;i<=count;i++) {
    swap=keys[i];j=i-1
    while(j>0 && keys[j]>swap) {keys[j+1]=keys[j];j--}
    keys[j+1]=swap
  }
  bytes=4
  for(i=1;i<=count;i++) bytes+=length(keys[i])+length(prefs[keys[i]])+2
  if(bytes>1023) refuse()
  print "OC2"
  for(i=1;i<=count;i++) print keys[i] "=" prefs[keys[i]]
}
function json_string(value, result, i, character) {
  result="\""
  for(i=1;i<=length(value);i++) {
    character=substr(value,i,1)
    if(character=="\\" || character=="\"") result=result "\\"
    result=result character
  }
  return result "\""
}
BEGIN {
  if(legacy!="" || operation!~/^(decode|write|set|compose|rows)$/) refuse()
  load_catalog(catalog)
  prefs["base"]="0";prefs["wireless"]="0";prefs["touch"]="1";prefs["warning"]="1"
  prefs["carplay-autoshow"]="0";prefs["source-order"]="0";prefs["menu-loop"]="0";prefs["hold-scroll"]="0"
  for(id in service_default) prefs["service." id]=service_default[id]
  service_keys=""
  for(i=1;i<=service_count;i++) {
    if(i>1) service_keys=service_keys ","
    service_keys=service_keys service_ids[i]
  }
  prefs["service-ids"]=service_keys
  if(input!="") load_preferences(input,operation=="write")
  else if(operation!="write") refuse()
  if(input!="") validate_preferences()
  if(operation=="write") {
    delete prefs["service.dvd"]
    prefs["package"]=package_id;prefs["nvram"]=nvram_value;prefs["metadata"]=metadata_value
  }
  if(operation=="set") {
    if(!(key=="touch" ? touch_mode(value) : bit(value)) || (key!~/^(touch|warning|base|wireless|carplay-autoshow|source-order|menu-loop|hold-scroll)$/ && index(key,"service.")!=1) ||
      !known_key(key)) refuse()
    prefs[key]=value
  }
  validate_preferences()
  if(operation=="rows") {
    if(selected_services!="") {
      count=split(selected_services,pairs,",")
      if(count>16) refuse()
      for(i=1;i<=count;i++) {
        if(split(pairs[i],pair,"=")!=2 || !service_id(pair[1]) || !bit(pair[2]) || pair[1] in selected) refuse()
        selected[pair[1]]=pair[2]
      }
    }
    printf "["
    for(i=1;i<=service_count;i++) {
      id=service_ids[i]
      printf "%s{\"id\":%s,\"label\":%s,\"saved\":%s,\"current\":%s,\"enable\":%s,\"disable\":%s}", \
        (i==1 ? "" : ","), json_string(id), json_string(service_label[id]), prefs["service." id], \
        (id in selected ? selected[id] : "null"), json_string(service_enable[id]), json_string(service_disable[id])
    }
    print "]"
    exit
  }
  if(operation=="decode") {
    choices=""
    # Config keys are sorted; retain that same order in the shell summary.
    for(i=1;i<=service_count;i++) {
      id=service_ids[i]
      if(i>1) choices=choices ","
      choices=choices id "=" prefs["service." id]
    }
    print prefs["package"] "|" prefs["touch"] "|" prefs["warning"] "|" prefs["nvram"] "|" \
      prefs["metadata"] "|" ("service.pandora" in prefs ? prefs["service.pandora"] : "1") "|" \
      prefs["base"] "|" prefs["wireless"] "|" choices
    exit
  }
  if(operation=="write" || operation=="set") {prefs["service-ids"]=service_keys;write_preferences();exit}
}
