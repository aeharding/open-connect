#!/usr/bin/env python3
"""ONE native-kind boot observer. Host profile default; no automatic second boot."""
import argparse,json,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import runtime as rt

def make_profile(candidate_path,baseline,ctx,code,binding,loaded,kind):
 if kind not in ("C","O") or binding.get("kind")!=kind:raise ValueError("native boot kind binding")
 p=rt.profile(candidate_path);rt.baseline_valid(baseline)
 rt.identity(binding["identity"],64785,454142,1433953535 if kind=="O" else None)
 if not binding.get("evidence") or not loaded.get("identity") or not loaded.get("process"):raise ValueError("actual apply/undo and previous-loaded evidence required")
 deps=dict(rt.json_data(HERE/"dependencies.json"))
 for path in [HERE/"runtime.py",HERE/"observe.py",HERE/"dependencies.json"]:
  deps[str(path.relative_to(rt.ROOT))]=rt.sha(path.read_bytes())
 deps.update(p["source_pins"])
 return dict(schema="NATIVE_BOOT_V1",live_authority=False,authority=None,authority_sha256=None,
  candidate_profile=str(Path(candidate_path).resolve()),candidate_profile_sha256=rt.sha(Path(candidate_path).read_bytes()),
  kind=kind,identity=binding["identity"],baseline=baseline,context=ctx,code=code,binding=binding,
  previously_loaded=loaded,source_pins=deps,reboot_hex="2f7362696e2f7265626f6f740d",request_limit=1,
  credential_attempts=1,deadline_s=180,visual_feature_verified=False,identity_policy="exact-full-no-adoption",
  complete_scope="C boot then disk undo then separate O confirmation; each observer owns only ONE boot")
def approved(path):
 v=rt.json_data(path)
 if (v.get("schema")!="NATIVE_BOOT_V1" or v.get("live_authority") is not True or
 v.get("reboot_hex")!="2f7362696e2f7265626f6f740d" or v.get("request_limit")!=1 or
 v.get("credential_attempts")!=1 or v.get("deadline_s")!=180 or v.get("identity_policy")!="exact-full-no-adoption"):
  raise ValueError("review-only/unbound native profile")
 p=rt.profile(v["candidate_profile"])
 if rt.sha(Path(v["candidate_profile"]).read_bytes())!=v["candidate_profile_sha256"]:raise ValueError("candidate profile changed")
 auth=rt.ROOT/v["authority"]
 if not v.get("authority_sha256") or rt.sha(rt.artifact(auth))!=v["authority_sha256"]:raise ValueError("concrete coordinator handoff pin required")
 for name,h in v["source_pins"].items():
  if rt.sha(rt.artifact(rt.ROOT/name))!=h:raise ValueError("checked observer/runtime source changed")
 rt.baseline_valid(v["baseline"]);rt.parse_journal(rt.record(v["context"]),p)
 ev=v["binding"]["evidence"]
 raw,actual=rt.core_output(ev["core_bundle"])
 if actual!=ev:raise ValueError("binding evidence changed")
 if v["binding"]["kind"]!=v["kind"] or v["binding"]["identity"]!=v["identity"]:raise ValueError("kind binding")
 rt.identity(v["identity"],64785,454142,1433953535 if v["kind"]=="O" else None)
 loaded=v["previously_loaded"]
 rt.identity(loaded["identity"],64785,454142)
 if not loaded["process"]:raise ValueError("previous mapped process binding")
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
  result=session.execute(rt.native_check())
  loaded=v["previously_loaded"]
  f=rt.observation(*result,p,v["kind"],v["identity"],before,
   mapped_identity=loaded["identity"] if pre else v["identity"],
   deleted=None if pre else False,process=loaded["process"] if pre else None,
   parents=v["baseline"]["parents"])
  if f["manager"]!=v["baseline"]["manager"]:raise rt.IdentityConflict(dict(f,manager_changed=True))
  command=rt.code_entry(v["context"],v["code"],"VERIFY")
  rt.verified_output(*session.execute(command),v["context"],v["kind"],v["identity"])
  bundle.event("native_persistent_verified",kind=v["kind"],writes=0,phase="pre" if pre else "post",identity=f["META"])
  return f
 with stock.AdapterLock(owner=args.owner,purpose="ONE native "+v["kind"]+" startup"):
  try:
   port=stock.open_adapter(bundle);session=stock.Session(port,bundle,timeout=20,output_cap=stock.MAX_RX)
   session.observe_prompt(solicit=args.solicit_prompt);session.identify()
   before=check(session,pre=True)
   bundle.save("before.json",(json.dumps(before,indent=2)+"\n").encode())
   video.start();start=time.monotonic();deadline=start+180;received=bytearray()
   requested=True;session.state="intentional_restart";session.identity=None
   bundle.event("restart_request",kind=v["kind"],command_hex=stock.REBOOT.hex(),request_limit=1,deadline_monotonic=deadline)
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
 a=argparse.ArgumentParser(description=__doc__);a.add_argument("--live",action="store_true")
 a.add_argument("--profile",type=Path);a.add_argument("--bundle",type=Path);a.add_argument("--credentials",type=Path)
 a.add_argument("--camera-index",type=int);a.add_argument("--owner",default="t14");a.add_argument("--solicit-prompt",action="store_true")
 x=a.parse_args(argv)
 if not x.live:
  print(json.dumps(dict(mode="HOST_REVIEW_ONLY",live_authority=False,kind=None,identity=None,retained=None,opens_devices=False,request_limit=1,complete_request_budget=2)));return 0
 if not all([x.profile,x.bundle,x.credentials]) or x.camera_index is None or x.camera_index<0:a.error("checked profile/private bundle/credentials/camera required")
 v,p=approved(x.profile)
 return observe(x,v,p)
if __name__=="__main__":raise SystemExit(main())
