# SPDX-License-Identifier: AGPL-3.0-or-later
# Canonical OC2 snapshot loader for AWK profile composition (sm-profile.awk / ui-profile.awk).
# Canonical OC2 parsing, mutation, and writing live in core/oc-config.c.
function refuse() { invalid=1; print "invalid_preferences" > "/dev/stderr"; exit 1 }
function bit(v) { return v=="0" || v=="1" }
function touch_mode(v) { return bit(v) || v=="2" }
function service_id(v) {
  return length(v)<=32 && v~/^[a-z][a-z0-9-]*$/ &&
    v!~/^(touch|warning|base|wireless|uart|ssh|carplay-autoshow|source-order|menu-loop|hold-scroll)$/
}
function load_catalog(path, ln, c, nf, id, mem, n, i, m, j, bytes) {
  while ((cr=getline ln < path)>0) {
    bytes+=length(ln)+1
    if(bytes>16384) refuse()
    if(ln~/^#/ || ln=="") continue
    nf=split(ln,c,"|"); id=c[1]
    if(nf!=6 || !service_id(id) || id in service_default || ++service_count>16 ||
      (service_count>1 && id<=service_ids[service_count-1]) ||
      !bit(c[3]) || c[2]=="" || length(c[2])>64 ||
      c[5]=="" || c[6]=="" || length(c[5])>256 || length(c[6])>256 ||
      ln~/[[:cntrl:]]/) refuse()
    service_ids[service_count]=id; service_default[id]=c[3]
    n=split(c[4],mem," ")
    if(n<1 || n>8) refuse()
    j=""
    for(i=1;i<=n;i++) {
      m=mem[i]
      if(length(m)>64 || m!~/^[A-Za-z_][A-Za-z0-9_]*$/ || m in service_owner) refuse()
      service_owner[m]=id; j=(i>1?j " ":"") m
    }
    if(j!=c[4]) refuse()
  }
  close(path)
  if(cr<0 || service_count<1 || catalog_bytes+0!=bytes) refuse()
}
function metadata(v, f, n, i) {
  n=split(v,f,":")
  if(n!=3 || f[1]!~/^[0-7]+$/ || length(f[1])>4) return 0
  for(i=2;i<=3;i++) if(f[i]!~/^[0-9]+$/ || length(f[i])>10 || f[i]+0>4294967295) return 0
  return 1
}
function known_key(k, id) {
  if(k~/^(package|touch|warning|nvram|metadata|base|wireless|service-ids|carplay-autoshow|source-order|menu-loop|hold-scroll)$/) return 1
  if(index(k,"service.")!=1) return 0
  id=substr(k,9); return id in service_default
}
function load_preferences(path, ln, k, v, s, prev, bytes, i, id, n, ks, listed) {
  if((getline ln < path)!=1 || ln!="OC2") refuse()
  bytes=4
  while((pr=getline ln < path)>0) {
    bytes+=length(ln)+1; s=index(ln,"="); k=substr(ln,1,s-1); v=substr(ln,s+1)
    if(bytes>1023 || !s || k<=prev || !known_key(k) || v=="" || index(v,"=") || ln~/[[:cntrl:]]/) refuse()
    prev=k; seen[k]=1; prefs[k]=v
  }
  close(path)
  # Caller supplies byte count, rejecting missing final LF or NUL truncation.
  if(pr<0 || input_bytes+0!=bytes) refuse()
  if(!seen["package"] || !seen["metadata"] || !seen["nvram"] || !seen["touch"] ||
    !seen["warning"] || !seen["base"] || !seen["wireless"] || !seen["service-ids"]) refuse()
  for(i=1;i<=service_count;i++) if(!seen["service." service_ids[i]]) refuse()
  n=split(prefs["service-ids"],ks,","); prev=""
  if(n<1 || n>16) refuse()
  for(i=1;i<=n;i++) {
    id=ks[i]
    if(!(id in service_default) || id<=prev || !seen["service." id]) refuse()
    prev=id; listed[id]=1
  }
  for(id in service_default) if(!(id in listed)) refuse()
}
function validate_preferences(k, v) {
  v=prefs["package"]
  if(length(v)!=64 || v~/[^a-f0-9]/ || !metadata(prefs["metadata"]) ||
    prefs["nvram"]!~/^(absent|enable|disable)$/) refuse()
  for(k in prefs)
    if(k!~/^(package|metadata|nvram|service-ids)$/ && !(k=="touch" ? touch_mode(prefs[k]) : bit(prefs[k]))) refuse()
}
BEGIN {
  if(legacy!="" || operation!="compose" || input=="") refuse()
  load_catalog(catalog)
  prefs["carplay-autoshow"]="0"; prefs["source-order"]="0"; prefs["menu-loop"]="0"; prefs["hold-scroll"]="0"
  load_preferences(input)
  validate_preferences()
}
