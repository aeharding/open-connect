"""Exact OEM55 patch: dispose the native intro only after renderer transition completion."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from open_connect.files import posix_cksum
BASE=ROOT/"runs/20261113T022134-0600-t14-oem-disclaimer/originals/jci/gui/apps/system/js/systemApp.js"
SHA="985cbcbeb1dedf11b76f61ffa1224e43165f80d8eb9c8d5d853d118d2eec3432"
ANCHOR=b'        "IntroAnimation" : {'
INSERT=b'''
            "noLongerDisplayedFunction" : function(template) {
                // The stock Disclaimer displayed callback already owns this case.
                if (template === this._outgoingContextTemplate &&
                    this._currentContext && this._currentContext.ctxtId === "Disclaimer")
                    return;
                // GuiFramework has completed the incoming transition and hidden
                // outgoing native surfaces before calling this lifecycle hook.
                framework.sendEventToMmui("system", "DisposeIntroVideo");
            }.bind(this),'''
def fp(b):
 return dict(bytes=len(b),md5=hashlib.md5(b).hexdigest(),crc=posix_cksum(b),sha256=hashlib.sha256(b).hexdigest())
def patch(b):
 if fp(b)["sha256"]!=SHA or len(b)!=94058:raise ValueError("unsupported exact OEM55 base")
 if b.count(ANCHOR)!=1:raise ValueError("ambiguous context")
 offset=b.index(ANCHOR)+len(ANCHOR)
 insertion=INSERT.replace(b"\n",b"\r\n") if b"\r\n" in b else INSERT
 return b[:offset]+insertion+b[offset:],offset,insertion
def build(out,original):
 out=Path(out).resolve()
 if not out.is_relative_to(ROOT/"runs") or out==ROOT/"runs":raise ValueError("private output required")
 b=Path(original).read_bytes();c,offset,insert=patch(b)
 out.mkdir(mode=0o700,parents=True,exist_ok=False)
 for name,data in [("original.js",b),("candidate.js",c),("insert.bin",insert)]:out.joinpath(name).write_bytes(data)
 profile=dict(original=fp(b),candidate=fp(c),insert=fp(insert),offset=offset,
              target="/jci/gui/apps/system/js/systemApp.js",candidate_path=str(out/"candidate.js"))
 out.joinpath("profile.json").write_text(json.dumps(profile,indent=2)+"\n")
 return profile
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument("--original",type=Path,required=True,help="exact private OEM systemApp.js")
 parser.add_argument("--output",type=Path,required=True,help="new private directory under runs/")
 args=parser.parse_args()
 try: result=build(args.output,args.original)
 except (OSError,ValueError) as exc: parser.exit(2,f"build not completed: {exc}\n")
 print(json.dumps(result,indent=2))
if __name__=="__main__":main()
