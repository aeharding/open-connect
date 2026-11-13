#!/usr/bin/env python3
"""Rebuild the canonical search index from research records, without hardware."""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "research"
def records(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def evidence_id(path):
    return "ev-" + hashlib.sha256(path.encode()).hexdigest()[:12]
def main():
    facts = records(R / "facts.jsonl")
    hypotheses = records(R / "hypotheses.jsonl")
    sources = records(R / "sources/manifest.jsonl")
    decisions = [r for p in sorted((R/"decisions").glob("*.jsonl")) for r in records(p)]
    rows = []
    headers = ["id","kind","status","tags","firmware_scope","summary","path",
               "locator","sha256","related_ids","recorded_at","superseded_by","conflicts"]
    def add(**r):
        rows.append({k:r.get(k,"") or "-" for k in headers})
    for f in facts:
        add(id=f["id"],kind="fact",status=f["classification"],tags=",".join(f["tags"]),
            firmware_scope=f["scope"],summary=f["claim"],path="research/facts.jsonl",
            locator=f["id"],sha256=digest(R/"facts.jsonl"),
            related_ids=",".join(e["id"] for e in f["evidence"]),
            recorded_at=f["recorded_at"],superseded_by=f.get("superseded_by") or "",
            conflicts=" | ".join(f.get("conflicts",[])))
    for h in hypotheses:
        add(id=h["id"],kind="hypothesis",status=h["status"],summary=h["question"],
            firmware_scope=h["firmware_scope"],path="research/hypotheses.jsonl",
            locator=h["id"],sha256=digest(R/"hypotheses.jsonl"),
            related_ids=",".join(h["related_ids"]),recorded_at=h["recorded_at"])
    for d in decisions:
        path="research/decisions/2026-11-12-preservation.jsonl"
        add(id=d["id"],kind="decision",status=d["status"],summary=d["title"]+": "+d["decision"],
            path=path,locator=d["id"],sha256=digest(ROOT/path),
            related_ids=",".join(d["related_ids"]),recorded_at=d["recorded_at"])
    for s in sources:
        add(id=s["id"],kind="source",status=s["status"],summary=s["title"],
            firmware_scope=s["scope"],path=s["snapshot_path"],
            locator="; ".join(s["relevant_sections"]),sha256=s["sha256"],
            related_ids=",".join(s["supports"]),recorded_at=s["retrieved_at"],
            superseded_by=str(s["superseded"]),conflicts=" | ".join(s["conflicts"]))
    manifest_files = sorted((R/"manifests").glob("*.json"))
    seen = set()
    for path in manifest_files:
        m=json.loads(path.read_text())
        for e in m.get("files",[]):
            eid=e.get("id",evidence_id(e["path"]))
            if eid in seen: continue
            seen.add(eid)
            add(id=eid,kind="original-evidence" if e["path"].startswith(("logs/","captures/","inventory/","runs/","notes/")) else "workspace-context",
                status="host-hashed-local-only",summary=e["path"],
                path=e["path"],sha256=e["sha256"],recorded_at=m["created_at"],
                locator="all host bytes; contents not included in Git")
    for f in facts:
        for e in f["evidence"]:
            if e["id"] in seen or e["id"] in {s["id"] for s in sources}: continue
            seen.add(e["id"])
            add(id=e["id"],kind="derived-artifact",status="sanitized-or-manifest",
                summary=e["path"],path=e["path"],locator=e["locator"],sha256=e["sha256"],
                recorded_at=f["recorded_at"])
    extra = [ROOT/"notes/console-recovery-research.txt"]
    for path in [R/"context/SUMMARY.txt",R/"SCHEMA.txt",R/"sources/manifest.jsonl",*manifest_files,*[p for p in extra if p.is_file()]]:
        rel=str(path.relative_to(ROOT))
        eid=evidence_id(rel)
        if eid in seen: continue
        seen.add(eid)
        add(id=eid,kind="context-or-manifest",status="derived",summary=rel,path=rel,
            sha256=digest(path),recorded_at=datetime.now(timezone.utc).isoformat())
    ids=[r["id"] for r in rows]
    if len(ids)!=len(set(ids)): raise ValueError("Duplicate index IDs")
    output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=headers,delimiter="\t",lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (R/"index.tsv").write_text(output.getvalue())
    text = [
        "MAZDA CMU RESEARCH INDEX — canonical entry point",
        "Derived catalog; original evidence stays local and unchanged.",
        "",
        f"{len(facts)} facts/claims; {len(hypotheses)} open hypotheses; {len(decisions)} decisions; {len(sources)} saved sources.",
        "Search index.tsv by ID/topic/firmware/path; records retain scope and limits.",
        "Read context/SUMMARY.txt for handoff, constraints and physical-reference conflicts.",
        "Schema and update rules: SCHEMA.txt. Final preservation report: ../notes/research-preservation-result.txt.",
        "",
        "CURRENT AUTHORITY AND SAFETY CONSTRAINTS",
        "Coordinator t6; current hardware owner t14; research worker t13 has no hardware access.",
        "Keep firmware55.00.750B, power/accounts/persistent settings/USB/SD/networking unchanged.",
        "AFK user performs no physical operations. No subdelegation; all operations use Herdr hc.",
        "Historical manual dialog dismissal instructions are superseded by F012/D002.",
        "",
        "SAVED SOURCES (ignored originals; tracked manifest with hash, URL, page and applicability)"
    ]
    for s in sources:
        text.extend([s["id"]+": "+s["title"],
                     "  "+s["requested_url"],
                     "  "+str(s["bytes"])+" bytes; SHA-256 "+s["sha256"],
                     "  "+s["snapshot_path"],
                     "  "+ "; ".join(s["relevant_sections"])])
    text += ["","FACTS AND LIMITS"]
    for f in facts:
        text.extend([f["id"]+" ["+f["classification"]+"] "+f["claim"],"  Limit: "+f["limits"]])
    text += ["","OPEN QUESTIONS (tests and dependencies in hypotheses.jsonl)"]
    text.extend(h["id"]+" "+h["question"] for h in hypotheses)
    text += ["","DECISIONS (dated rationale in decisions/)"]
    text.extend(d["id"]+" "+d["title"] for d in decisions)
    text += ["","PROVENANCE AND LIMITS",
             "Initial original evidence: manifests/20261113T043356Z-original-evidence.json (119 files).",
             "New t14 capability and recovery records are supplemental; no exact copied backup is claimed.",
             "Recovery note: ../notes/console-recovery-research.txt; no live recovery action by research worker.",
             "18 historical raw/event pairs reconstructed exactly; five prior hashes matched.",
             "Raw credentials/login TX/private identities stay out of Git. Fixtures are allowlisted derivatives.",
             "A local hash/commit is not a second copy, full backup, boot observation or verified recovery.",
             "Both Mazda PDFs match prior hashes. Literal requirements: 2018 v70.00.21; 2019 70.00.021B.",
             "Those prerequisites do not prove actual bench hub identity or legacy USB/SD failure.",
             ""]
    (R/"index.txt").write_text("\n".join(text))
    print(json.dumps({"rows":len(rows),"facts":len(facts),"hypotheses":len(hypotheses),"decisions":len(decisions),"sources":len(sources)}))
if __name__=="__main__":
    main()
