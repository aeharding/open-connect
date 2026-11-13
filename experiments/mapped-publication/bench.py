"""Direct bench utilities; reuses the established serial protocol and DATA stager."""
import importlib.util, json, sys, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"experiments/native-disclaimer-runtime"))
import runtime as rt
from open_connect.session import AdapterLock, Bundle, Session, open_adapter
stock=rt.module("_mapped_stock_helpers",ROOT/"experiments/stock-warm-start/observe.py")

def validate_live_dependencies():
    # Importing/parsing is offline. Historical execution pins still gate hardware.
    try:
        rt.verify_dependencies()
    except (ValueError, OSError) as exc:
        raise ValueError(
            "Runtime profile is not qualified for this checkout; "
            "preserve historical manifests and qualify current code before live execution"
        ) from exc

def command(text, path, timeout=60):
    validate_live_dependencies()
    b=Bundle(path,"Open Connect mapped-library experiment","t6",mode="live")
    port=None
    with AdapterLock(owner="t6",purpose="Open Connect mapped-library experiment"):
        try:
            port=open_adapter(b)
            s=Session(port,b,timeout=timeout,output_cap=4194304)
            s.observe_prompt(solicit=True);s.identify()
            rc,out=s.execute(text)
            b.save("result.bin",out)
            outcome="completed" if rc==0 else "remote_nonzero"
        except BaseException as e:
            if port is not None:port.close();b.meta["port_closed"]=True
            b.finish("unknown",type(e).__name__+": "+str(e));raise
        else:
            port.close();b.meta["port_closed"]=True
            b.finish(outcome)
            if rc:raise RuntimeError(f"Remote rc {rc}; evidence {path}")
            return out

def stage(data,path):
    d=rt.delivery();run=__import__("secrets").token_hex(16)
    snap=dict(data=data,**d.fingerprint(data))
    out=command(d.stage_command(snap,run),Path(path)/"upload")
    desc=rt.stage_descriptor(out,data,run)
    (Path(path)/"descriptor.json").write_text(json.dumps(desc,indent=2)+"\n")
    return desc

if __name__=="__main__":
    text=Path(sys.argv[1]).read_text()
    command(text,Path(sys.argv[2]))
