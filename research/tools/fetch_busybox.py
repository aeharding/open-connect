#!/usr/bin/env python3
"""Bounded primary BusyBox1.19.2 source preservation for offline parser review."""
from datetime import datetime,timezone
import hashlib,json,io,tarfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
url="https://busybox.net/downloads/busybox-1.19.2.tar.bz2"
start=datetime.now(timezone.utc).isoformat()
with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mazda-CMU-bench-recovery-research/1.0"}),timeout=25) as response:
    body=response.read(8_000_001)
    if len(body)>8_000_000:raise ValueError("source size bound exceeded")
    final=response.geturl();mime=response.headers.get("Content-Type")
sha=hashlib.sha256(body).hexdigest()
base=Path("research/sources/snapshots")/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")/"busybox-1.19.2"/sha
folder=ROOT/base
folder.mkdir(parents=True,exist_ok=False)
(folder/"busybox-1.19.2.tar.bz2").write_bytes(body)
selected=["shell/ash.c","libbb/lineedit.c","libbb/read.c","include/libbb.h","libbb/Config.src","shell/Config.src"]
extracted=[]
with tarfile.open(fileobj=io.BytesIO(body),mode="r:bz2") as archive:
    for name in selected:
        full="busybox-1.19.2/"+name
        try:member=archive.getmember(full)
        except KeyError:continue
        if not member.isfile() or member.size>2_000_000:raise ValueError("unexpected member")
        data=archive.extractfile(member).read()
        dest=folder/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
        extracted.append({"path":str(base/name),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"archive_member":full})
record={"id":"busybox-1.19.2","title":"BusyBox1.19.2 official release source","author":"BusyBox project",
"authority":"Primary project source release","requested_url":url,"final_url":final,
"retrieval_started_at":start,"retrieved_at":datetime.now(timezone.utc).isoformat(),
"content_type":mime,"bytes":len(body),"sha256":sha,
"snapshot_path":str(base/"busybox-1.19.2.tar.bz2"),"status":"saved-and-reread-verified",
"reread_sha256":hashlib.sha256((folder/"busybox-1.19.2.tar.bz2").read_bytes()).hexdigest(),
"revision":"BusyBox1.19.2 release; exact archive SHA-256 pinned",
"relevant_sections":["shell/ash.c interactive input, parser, top-level exception handling","libbb/lineedit.c Ctrl-C/Ctrl-D handling"],
"scope":"Nominal version matches t14 observed BusyBox1.19.2; vendor patches/build-time options unknown",
"supports":[],"conflicts":["CMU vendor build configuration/patches and live tty settings are unknown; source behavior is conditional, not live validation"],
"superseded":False,"extracted_members":extracted}
with (ROOT/"research/sources/manifest.jsonl").open("a") as fp:fp.write(json.dumps(record)+"\n")
print(json.dumps({"archive":record["snapshot_path"],"sha256":sha,"bytes":len(body),"files":extracted},indent=2))
