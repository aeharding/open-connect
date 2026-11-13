#!/usr/bin/env python3
"""Host-only immutable evidence/source preservation. Run through Herdr hc.
Never imports serial, opens devices, or modifies original bench evidence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "research"
def now():
    return datetime.now(timezone.utc).isoformat()
def digest(data):
    return hashlib.sha256(data).hexdigest()
def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as out:
        json.dump(value, out, indent=2, ensure_ascii=False)
        out.write("\n")
def snapshot():
    # Explicit original evidence roots, original summaries, and reviewed code.
    paths = []
    for name in ("logs", "captures", "inventory"):
        paths.extend(p for p in (ROOT / name).rglob("*") if p.is_file() and not p.is_symlink())
    paths.extend(p for p in (ROOT / "notes").glob("*") if p.is_file()
                 and p.name != "research-preservation-result.txt")
    paths.extend(ROOT / s for s in ("AGENTS.md", "README.txt", "requirements.txt",
                 "scripts/bench.py", "scripts/console-command.py"))
    records = []
    for path in sorted(set(paths)):
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError("File changed during snapshot: " + str(path.relative_to(ROOT)))
        rel = str(path.relative_to(ROOT))
        records.append({
            "id": "ev-" + digest(rel.encode())[:12],
            "path": rel, "bytes": len(data), "sha256": digest(data),
            "mtime_ns": before.st_mtime_ns,
            "kind": "original-local-evidence" if rel.startswith(("logs/", "captures/", "inventory/", "notes/")) else "initial-workspace-context",
            "access": "local-only; potentially private contents" if rel.startswith(("logs/", "captures/", "inventory/")) else "review-before-staging",
            "hash_scope": "host bytes only; no remote checksum or completeness claim"
        })
    token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESEARCH / "manifests" / (token + "-original-evidence.json")
    write_json(out, {"schema": 1, "created_at": now(),
                    "method": "hc exec python3 research/tools/preserve.py snapshot",
                    "policy": "No originals modified or copied. Local hash manifest is not a second copy, full backup, or restore validation.",
                    "files": records})
    print(json.dumps({"manifest": str(out.relative_to(ROOT)), "files": len(records)}))
def download():
    definitions = [
        ("mazda-retrofit-2018", "Mazda CSP02 retrofit installation packet",
         "https://static.nhtsa.gov/odi/tsbs/2018/MC-10144323-9999.pdf",
         "0e8d022212049408e49453718806dfeb7c608faa2271e2b71e3e98f75b0b3494", 4217760, 8_000_000, ".pdf"),
        ("mazda-sa00119-2019", "Mazda SA-001/19, 2019-04-05",
         "https://static.nhtsa.gov/odi/tsbs/2019/MC-10159198-0001.pdf",
         "0c8996c9df0f24c117534aebfe3cbc1017c1d522f5fccae9b46be9729883a57d", 851674, 2_000_000, ".pdf"),
        ("hardware-silverchris", "silverchris Mazda CMU hardware notes (author's community research)",
         "https://raw.githubusercontent.com/silverchris/mazda-cmu-documentation/gh-pages/hardware.md",
         None, None, 250_000, ".md"),
        ("pyserial-api", "pySerial official API documentation",
         "https://pyserial.readthedocs.io/en/latest/pyserial_api.html",
         None, None, 1_000_000, ".html")
    ]
    token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESEARCH / "sources" / "manifest.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise RuntimeError("Source manifest already exists; do not overwrite editions")
    records = []
    for sid, title, url, expected, expected_size, limit, ext in definitions:
        record = {"id": sid, "title": title, "requested_url": url,
                  "retrieval_started_at": now(), "max_bytes": limit,
                  "expected_sha256": expected, "expected_bytes": expected_size,
                  "expected_from": "notes/interim-development-research-plan.txt:118" if expected else None,
                  "superseded": False}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mazda-CMU-bench-preservation/1.0"})
            with urllib.request.urlopen(req, timeout=25) as response:
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise ValueError("source exceeds bounded size")
                record.update(final_url=response.geturl(), http_status=response.status,
                              content_type=response.headers.get("Content-Type"),
                              etag=response.headers.get("ETag"),
                              last_modified=response.headers.get("Last-Modified"))
            if ext == ".pdf" and not body.startswith(b"%PDF-"):
                raise ValueError("expected PDF signature missing")
            sha = digest(body)
            rel = Path("research/sources/snapshots") / token / sid / (sha + ext)
            target = ROOT / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as fp:
                fp.write(body)
            if digest(target.read_bytes()) != sha:
                raise ValueError("saved source failed reread hash")
            record.update(retrieved_at=now(), bytes=len(body), sha256=sha,
                          snapshot_path=str(rel), status="saved-and-reread-verified",
                          prior_review_match=(sha == expected and len(body) == expected_size) if expected else None,
                          changed_source=(sha != expected or len(body) != expected_size) if expected else None)
            if expected and record["changed_source"]:
                record["status"] = "changed-source-preserved-for-review"
        except Exception as exc:
            record.update(status="failed", error=str(exc), retrieved_at=now())
        records.append(record)
        print(json.dumps({k: record.get(k) for k in ("id", "status", "bytes", "sha256", "prior_review_match")}), flush=True)
    with out.open("x") as fp:
        for record in records:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")
    if any(r["status"] == "failed" for r in records):
        raise SystemExit(1)
def verify():
    manifests = sorted((RESEARCH / "manifests").glob("*-original-evidence.json"))
    if len(manifests) != 1:
        raise RuntimeError("select exactly one original snapshot")
    manifest = json.loads(manifests[0].read_text())
    differences = []
    for item in manifest["files"]:
        path = ROOT / item["path"]
        if not path.is_file() or digest(path.read_bytes()) != item["sha256"]:
            differences.append(item["path"])
    result = {"checked_at": now(), "original_manifest": str(manifests[0].relative_to(ROOT)),
              "checked": len(manifest["files"]), "differences": differences,
              "note": "README research entry and later worker code may intentionally change; raw originals must not."}
    print(json.dumps(result, indent=2))
    return result
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "download", "verify"))
    args = parser.parse_args()
    globals()[args.action]()
