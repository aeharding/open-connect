#!/usr/bin/env python3
"""ONE ORIGINAL-only recovery boot with explicit truthful RW-before/RO-after."""
import argparse,json,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import runtime as rt, recover_rw as rw
def approved(path):
 v=rt.json_data(path)
 if (v.get("schema")!="NATIVE_ORIGINAL_RW_RECOVERY_V1" or v.get("live_authority") is not True or
 v.get("kind")!="O" or v.get("identity")!=rw.OID or v.get("pre_mount")!="rw" or
 v.get("request_limit")!=1 or v.get("credential_attempts")!=1 or v.get("deadline_s")!=180 or
 v.get("reboot_hex")!="2f7362696e2f7265626f6f740d"):
  raise ValueError("original-only recovery profile required")
 if v.get("authority")!=str(rw.AUTHORITY.relative_to(rt.ROOT)) or rt.sha(rw.AUTHORITY.read_bytes())!=v["authority_sha256"]:
  raise ValueError("recovery authority pin")
 for n,h in v["source_pins"].items():
  if rt.sha(rt.artifact(rt.ROOT/n))!=h:raise ValueError("recovery code pin changed")
 p=rt.profile(v["candidate_profile"])
 known=rw.known_undo_failure(v["undo_bundle"],Path(v["undo_entry"]).read_text())
 if known!=v["binding"] or known.get("sync_verified") is not True:raise ValueError("exact O+sync+soleEBUSY evidence")
 raw,e=rt.core_output(v["fresh_O_bundle"],Path(v["fresh_O_command"]).read_text())
 rw.rw_observation(0,raw,p,"O",rw.OID,v["baseline"])
 rw.inspection_output(0,raw,"O","rw")
 if e!=v["fresh_O_evidence"]:raise ValueError("fresh O evidence changed")
 return v,p
def observe(args,v,p):
 stock=rt.fields().stock
 user,password=stock.private_credentials(args.credentials)
 bundle=stock.Bundle(args.bundle,"ONE native "+v["kind"]+" startup",args.owner,mode="live")
 bundle.meta.update(profile=v,expected_native_kind=v["kind"],visual_feature_verified=False)
 video=stock.Video(bundle,args.camera_index)
 port=None;requested=False;outcome="failed_before_request";error=None
 def check(session,before=None,pre=False):
  nonlocal bundle
  cmd=rt.native_check()
  if pre:cmd=cmd.replace('$6==p&&(NF==6||(NF==7&&$7=="(deleted)"))','index($0,"libjciuiasystem.so")>0')
  result=session.execute(cmd)
  loaded=v["previously_loaded"]
  if pre and v["pre_mount"]=="rw":
   f=rw.rw_observation(*result,p,"O",rw.OID,v["baseline"])
  else:
   f=rt.observation(*result,p,"O",v["identity"],before,
    mapped_identity=loaded["identity"] if pre else v["identity"],
    deleted=None if pre else False,process=loaded["process"] if pre else None,
    parents=v["baseline"]["parents"])
  if f["manager"]!=v["baseline"]["manager"]:raise rt.IdentityConflict(dict(f,manager_changed=True))
  if pre and v["pre_mount"]=="rw":
   rw.inspection_output(*session.execute(rw.inspector("O","rw")),"O","rw")
  else:
   rt.verified_output(*session.execute(rt.code_entry(v["context"],v["code"],"VERIFY")),v["context"],"O",v["identity"])
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

def main(argv=None):
 a=argparse.ArgumentParser(description=__doc__)
 a.add_argument("--live",action="store_true");a.add_argument("--profile",type=Path)
 a.add_argument("--bundle",type=Path);a.add_argument("--credentials",type=Path)
 a.add_argument("--camera-index",type=int);a.add_argument("--owner",default="t14");a.add_argument("--solicit-prompt",action="store_true")
 x=a.parse_args(argv)
 if not x.live:print(json.dumps(dict(mode="HOST_ONLY_ORIGINAL_RECOVERY",request_limit=1,kind="O",pre_root_mode="rw",post_root_mode="ro")));return 0
 if not all((x.profile,x.bundle,x.credentials)) or x.camera_index is None or x.camera_index<0:a.error("private profile/bundle/credentials/camera")
 v,p=approved(x.profile)
 return observe(x,v,p)
if __name__=="__main__":raise SystemExit(main())
