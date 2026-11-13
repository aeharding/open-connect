"""Reuse the proven boot loop with link-aware native identity checks."""
import json,sys,time,math,re
from pathlib import Path
from types import SimpleNamespace
from bench import rt,ROOT,stock
from trial import load,entry,R
def mapping_command():
 cmd=rt.native_check().replace('$6==p&&(NF==6||(NF==7&&$7=="(deleted)"))','index($6,"libjciuiasystem.so")>0')
 # Gather first, then emit each typed record with one printf. Never print a
 # prefix before a child command can be interrupted by an unrelated logger.
 for key,command,code in [("META","stat -c '%d:%i:%Y:%s:%a:%u:%g:%h' \"$p\"",73),("HASH","md5sum < \"$p\"",74),("CRC","cksum < \"$p\"",75),("UPTIME","cat /proc/uptime",76),("BOOT_ID","cat /proc/sys/kernel/random/boot_id",77)]:
  old=f"printf 'SWST|{key}|';{command} || exit {code}"
  new=f"v=$({command}) || exit {code};printf 'SWST|{key}|%s\\n' \"$v\""
  if old not in cmd:raise ValueError("status producer anchor")
  cmd=cmd.replace(old,new)
 old='printf \'NATIVE_PARENT|%s|\' "$d";stat -c \'%d:%i:%a:%u:%g\' "$d" || exit 71'
 new='v=$(stat -c \'%d:%i:%a:%u:%g\' "$d") || exit 71;printf \'NATIVE_PARENT|%s|%s\\n\' "$d" "$v"'
 if old not in cmd:raise ValueError("parent producer anchor")
 return cmd.replace(old,new)
def verify(session,kind,sid):
 status,raw=session.execute(entry("VERIFY"))
 phase="candidate" if kind=="C" else "restored"
 expected=f"VERIFY|{kind}|{phase}|{sid}|ro,noatime|writes=0"
 if status or rt.typed_records(raw,b"OCLINK|")!=[expected]:raise ValueError("persistent verification mismatch")
 return raw
def check_output(status,raw,v,before=None,pre=False):
 if status:raise ValueError("native check failed")
 f=rt.fields().candidate_fields(raw);p=load("plan/plan.json")
 expect=p["candidate"] if v["kind"]=="C" else p["original"]
 if f["META"]!=v["identity"]:raise rt.IdentityConflict(f)
 if f["HASH"].split()!=[expect["md5"],"-"] or f["CRC"].split()!=[str(expect["crc"]),str(expect["bytes"])]:raise ValueError("bytes changed")
 if f["ROOT"]!="/dev/ffx01p1 / relfs ro,noatime 0 0":raise ValueError("physical root not RO")
 u=float(f["UPTIME"].split()[0])
 if not math.isfinite(u) or u<0 or not re.fullmatch("[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",f["BOOT_ID"]):raise ValueError("boot metadata")
 if before and (f["BOOT_ID"]==before["BOOT_ID"] or u>=before["uptime_seconds"]):raise ValueError("new boot not established")
 parents=dict(x.split("|") for x in rt.typed_records(raw,b"NATIVE_PARENT|"))
 if parents!=p["parents"]:raise ValueError("parent identity changed")
 module=rt.typed_records(raw,b"NATIVE_MODULE|")
 if len(module)!=1 or not re.fullmatch(r"[1-9][0-9]*\|[1-9][0-9]*:[0-9]+\|a43fc1bb895b0e6c13480c8f4b875a58  -",module[0]):raise ValueError("MMUI identity")
 if pre and module[0]!=v["previously_loaded"]["process"]:raise ValueError("previous module changed")
 maps=rt.typed_records(raw,b"NATIVE_MAP|")
 wanted=(v["previously_loaded"]["identity"] if pre else v["identity"]).split(":")[1]
 if not maps:raise ValueError("no mapped library")
 for line in maps:
  fields=line.split()
  valid_shape = len(fields)==6 or (pre and len(fields)==7 and fields[6]=="(deleted)" and fields[5] in (p["target"],p["stage"]))
  if not valid_shape or fields[3]!="fd:11" or fields[4]!=wanted or fields[5] not in (p["target"],p["hold_o"],p["hold_c"],p["stage"]):
   raise rt.IdentityConflict(dict(f,mapping=line))
 mgr=rt.typed_records(raw,b"NATIVE_MANAGER|")
 if mgr!=[v["manager"]]:raise ValueError("native manager changed")
 return dict(f,uptime_seconds=u,module=module[0],maps=maps,manager=mgr[0],kind=v["kind"])
def observe(args,v,p):
 user,password=stock.private_credentials(args.credentials)
 bundle=stock.Bundle(args.bundle,"ONE native "+v["kind"]+" startup",args.owner,mode="live")
 bundle.meta.update(profile=v,expected_native_kind=v["kind"],visual_feature_verified=False)
 video=stock.Video(bundle,args.camera_index)
 port=None;requested=False;outcome="failed_before_request";error=None
 def check(session,before=None,pre=False):
  nonlocal bundle
  result=session.execute(mapping_command())
  f=check_output(*result,v,before,pre)
  raw=verify(session,v["kind"],v["identity"])
  bundle.event("native_persistent_verified",source_kind=v["kind"],writes=0,phase="pre" if pre else "post",identity=f["META"])
  return f
 with stock.AdapterLock(owner=args.owner,purpose="ONE native "+v["kind"]+" startup"):
  try:
   port=stock.open_adapter(bundle);session=stock.Session(port,bundle,timeout=20,output_cap=stock.MAX_RX)
   session.observe_prompt(solicit=args.solicit_prompt);session.identify()
   before=check(session,pre=True)
   bundle.save("before.json",(json.dumps(before,indent=2)+"\n").encode())
   video.start();start=time.monotonic();deadline=start+180;received=bytearray()
   requested=True;session.state="intentional_restart";session.identity=None
   bundle.event("restart_request",source_kind=v["kind"],command_hex=stock.REBOOT.hex(),request_limit=1,deadline_monotonic=deadline)
   session._send(stock.REBOOT,deadline=min(deadline,start+2),received=received)
   gate=stock.BootGate();pending=bytearray(received)
   while time.monotonic()<deadline:
    if pending:chunk=bytes(pending);pending.clear()
    else:chunk=session._read(received,until=deadline)
    if not chunk:continue
    event=gate.feed(chunk)
    if event:bundle.event("restart_transition",transition=event)
    if event in ("login","password"):
     session._send(user if event=="login" else password,deadline=min(deadline,time.monotonic()+2),received=received,on_rx=pending.extend)
    if event=="shell":
     session.state="shell";session.timeout=min(20,deadline-time.monotonic())
     if session.timeout<=1:raise TimeoutError("no bounded identity time")
     session.identify();session.timeout=min(20,deadline-time.monotonic())
     after=check(session,before)
     bundle.save("after.json",(json.dumps(after,indent=2)+"\n").encode())
     tail=min(deadline,time.monotonic()+20)
     while time.monotonic()<tail:
      extra=session._read(received,until=tail)
      if extra:
       gate.raw.extend(extra)
       if len(gate.raw)>stock.MAX_RX or len(list(stock.KERNEL_BANNER.finditer(stock.ANSI.sub(b"",bytes(gate.raw)))))>1:raise RuntimeError("RX cap/repeated boot during native settling")
     session.timeout=min(20,deadline-time.monotonic())
     if session.timeout<=1:raise TimeoutError("no bounded final state time")
     final=check(session)
     if final["module"]!=after["module"]:raise rt.IdentityConflict(dict(final,module_changed=True))
     bundle.save("final.json",(json.dumps(final,indent=2)+"\n").encode())
     outcome="native_"+v["kind"]+"_startup_access_mapping_RO_verified";break
   else:raise TimeoutError("180s readiness bound; no retry")
  except rt.IdentityConflict as exc:
   bundle.save("identity-conflict.json",(json.dumps(exc.actual,indent=2)+"\n").encode())
   outcome="native_identity_conflict_OTHER";error=str(exc)
  except BaseException as exc:
   error=type(exc).__name__+": "+str(exc);outcome="unknown_after_request" if requested else "failed_before_request"
  finally:
   try:video.stop()
   except BaseException as exc:
    error=(error or "")+"; video: "+str(exc)
    outcome=outcome+"_video_failed" if outcome.startswith("native_") else outcome
   if port is not None:port.close();bundle.meta["port_closed"]=True
   bundle.finish(outcome,error)
 print(json.dumps(dict(outcome=outcome,error=error,bundle=str(args.bundle),visual_feature_verified=False)))
 return 0 if outcome=="native_"+v["kind"]+"_startup_access_mapping_RO_verified" else 2

def main():
 kind=sys.argv[1]
 if kind not in ("C","O"):raise ValueError("explicit C or O boot")
 p=load("plan/plan.json")
 baseline=rt.json_data(R/"baseline/manifest.json")
 # These IDs come only from actual completed publication/undo evidence.
 if kind=="C":
  rows=load("apply.json")["rows"];key="APPLIED|"
  loaded=rt.json_data(R/"baseline.json")
 else:
  rows=load("undo.json")["rows"];key="RESTORED|"
  loaded=rt.json_data(R/"boot-C/final.json")
 ids=[x[len(key):] for x in rows if x.startswith(key)]
 if len(ids)!=1 or not any(x=="FINAL|operation=0|sync=0|ro_request=0|row=ro,noatime" for x in rows):raise ValueError("completed transition and physical RO required")
 v=dict(kind=kind,identity=ids[0],previously_loaded=dict(identity=loaded["META"],process=loaded["module"]),manager=loaded["manager"])
 args=SimpleNamespace(credentials=ROOT/"runs/20261113T055807-0600-t14-stock-reboot-preflight/credentials.private.json",bundle=R/("boot-"+kind),owner="t6",camera_index=0,solicit_prompt=True)
 (R/("boot-"+kind+"-plan.json")).write_text(json.dumps(v,indent=2)+"\n")
 return observe(args,v,p)
if __name__=="__main__":raise SystemExit(main())
