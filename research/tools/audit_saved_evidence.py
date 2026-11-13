#!/usr/bin/env python3
"""Audit original saved records offline and emit small allowlisted derivatives.
No serial/camera access. Original bytes are never rewritten.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
def sha(data):
    return hashlib.sha256(data).hexdigest()
def save(path, value):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as fp:
        json.dump(value, fp, indent=2)
        fp.write("\n")
def ref(path, locator):
    data = (ROOT / path).read_bytes()
    return {"path": path, "sha256": sha(data), "bytes": len(data), "locator": locator}
def main():
    original = next((ROOT / "research/manifests").glob("*-original-evidence.json"))
    manifest = json.loads(original.read_text())
    pairs = []
    for item in manifest["files"]:
        path = ROOT / item["path"]
        if path.suffix != ".jsonl" or not path.with_suffix(".bin").is_file():
            continue
        events = [json.loads(line) for line in path.read_text().splitlines()]
        received = b"".join(bytes.fromhex(e["hex"]) for e in events
                            if e.get("direction", "rx").lower() == "rx")
        raw = path.with_suffix(".bin").read_bytes()
        pairs.append({
            "events_path": str(path.relative_to(ROOT)), "events_sha256": sha(path.read_bytes()),
            "raw_path": str(path.with_suffix(".bin").relative_to(ROOT)), "raw_sha256": sha(raw),
            "rx_bytes": len(received), "events": len(events),
            "tx_events": sum(e.get("direction", "rx").lower() == "tx" for e in events),
            "rx_reconstruction_matches_raw": received == raw,
            "txt_matches_raw": path.with_suffix(".txt").read_bytes() == raw if path.with_suffix(".txt").is_file() else None
        })
    # A host checksum only proves the relationship of local representations.
    expected = {
        "inventory/20261112T2135-cmu-version.ini": "64cd98721f7ef65023ad894e0acf36ce80929720343f2ce27b785548c8956acd",
        "logs/20261112T213105.531697-0600-uart.bin": "4d7f59192a0a83ad199f139297df5ae1f3c91e3330ff1f7bca814285830a0c47",
        "logs/20261112T213105.531697-0600-uart.jsonl": "63040f321832b62964fe3b0413b75eed2914e6207ea687786817805174eea84c",
        "logs/20261112T213524.771496-0600-system-discovery.bin": "a20fafb1bf820fcc02b4b4d32976c939dd9c8507fba4d9991d8594e87347f2c1",
        "logs/20261112T213816.865970-0600-console-root-login.bin": "839a514cdd1e430d823c0692c9cbd5a482f02e0a67fdea4b9a8ced2ae4528282"
    }
    prior = [{"path": p, "expected_sha256": h,
              "actual_sha256": sha((ROOT / p).read_bytes()),
              "matches_prior_review": sha((ROOT / p).read_bytes()) == h}
             for p,h in expected.items()]
    version_path = "inventory/20261112T2135-cmu-version.ini"
    version = (ROOT / version_path).read_text()
    fields = {}
    for key in ("JCI_SW_VER", "JCI_SW_VER_PATCH", "JCI_SW_FLAVOR", "JCI_SW_NEXT_VER"):
        matches = re.findall(r"^" + key + r'="([^"]*)"', version, re.M)
        if len(matches) != 1: raise ValueError("Expected one firmware field: " + key)
        fields[key] = matches[0]
    assert fields["JCI_SW_VER"] == "MAZ_CMU-150_55.00.750"
    assert fields["JCI_SW_VER_PATCH"] == "B"
    assert fields["JCI_SW_FLAVOR"] == "cmu150_NA"
    source = ref(version_path, "four explicit firmware metadata keys only")
    fixture = {
        "kind": "derived-sanitized-metadata; not byte-exact device file",
        "source": source, "transformation": "Copy only four allowlisted quoted field values; discard all other source lines.",
        "fields": fields, "installed_version": "55.00.750B",
        "limit": "Source contains unrelated trailing console output; NEXT_VER is metadata, not installed version."
    }
    save("research/fixtures/firmware-fields.json", fixture)

    identity_checks = []
    for path, uid in [
        ("logs/20261112T213428.427657-0600-console-login.bin",1000),
        ("logs/20261112T213816.865970-0600-console-root-login.bin",0)]:
        data = (ROOT / path).read_bytes()
        needle = b"uid=" + str(uid).encode() + (b"(root)" if uid == 0 else b"(user)")
        assert needle in data
        identity_checks.append({"source": ref(path,"fresh id response after historical login"),
                                "uid": uid, "response_present": True})
    save("research/fixtures/identity-results.json", {
        "kind": "derived-sanitized-assertions; no replayable login/TX data",
        "transformation": "Check exact uid response bytes in raw RX; export only UID and boolean.",
        "checks": identity_checks, "limit": "Historical evidence only; no claim about current shell state."
    })
    paths = {
        "identity": "logs/20261112T214554.100346-0600-interim-dialog-identity.bin",
        "cleanup": "logs/20261112T214618.244266-0600-interim-dialog-cleanup.bin",
        "postcheck": "logs/20261112T214645.784072-0600-interim-dialog-postcheck.bin"
    }
    clean = (ROOT / paths["cleanup"]).read_bytes()
    post = (ROOT / paths["postcheck"]).read_bytes()
    # Require a returned standalone marker, rather than just command echo.
    def response_marker(data, marker):
        return re.search(rb"(?:^|[\r\n])" + re.escape(marker) + rb"[\r\n]", data) is not None
    assert response_marker(clean,b"TERM_SENT_ONLY_PID18090")
    assert response_marker(post,b"PID18090_ABSENT_CONFIRMED")
    save("research/fixtures/dialog-lifecycle.json", {
        "kind": "derived-sanitized-lifecycle-summary; not a new experiment",
        "transformation": "Export allowlisted process identity, marker assertions, and operator visual attestation; omit unrelated runtime logs.",
        "sources": [ref(p,k+" historical console capture") for k,p in paths.items()] +
                   [ref("notes/interim-operator-plan.txt","What was actually checked, sections 1-2"),
                    ref("captures/20261112T214650.188879-0600-webcam.jpg","historical post-cleanup frame; operator inspected")],
        "historical_owned_pid": 18090, "pid_reuse_forbidden": True,
        "expected_executable": "/jci/tools/jci-dialog",
        "expected_title": "Mac Mini connected",
        "termination_marker_returned": True, "absence_marker_returned": True,
        "visual_result": "Prior operator reports home menu with Communication selected and no test dialog.",
        "visibility_limits": "Angled, left edge cropped, highlights bright; no new image inspection in preservation task."
    })
    input_path = "logs/20261112T214742.749982-0600-interim-input-readonly.txt"
    input_data = (ROOT / input_path).read_text()
    mapping = [
        ("event0","LVDS TouchScreen"), ("event1","Virtual Keyboard"),
        ("event2","Virtual Mouse"), ("event3","filtered-keyboard"),
        ("event4","filtered-mouse"), ("event5","filtered-touchscreen")]
    for node, name in mapping:
        assert node in input_data and name in input_data
    save("research/fixtures/input-listing.json", {
        "kind": "derived-sanitized-input-inventory",
        "source": ref(input_path,"INPUT_PROC and INPUT_NODES output"),
        "transformation": "Export only node names, normalized device labels and documented mode; strip virtual-device address suffixes and all runtime logs.",
        "devices": [{"node": "/dev/input/"+node,"label":name,"mode":"0600","owner":"root"} for node,name in mapping],
        "uinput": {"path":"/dev/uinput","major":10,"minor":223,"mode":"0600","owner":"root"},
        "limit": "Listing only; no event injection or physical commander validation."
    })
    audit = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": "hc exec python3 research/tools/audit_saved_evidence.py",
        "source_manifest": str(original.relative_to(ROOT)),
        "originals_modified": False,
        "checks": pairs, "prior_review_hash_comparisons": prior,
        "identity_checks_exported": len(identity_checks),
        "limit": "Checks verify stored representation consistency only; not full-wire capture, byte-exact remote files, backup completeness or recovery."
    }
    save("research/manifests/2026-11-12-saved-evidence-audit.json",audit)
    failures = [p["raw_path"] for p in pairs if not p["rx_reconstruction_matches_raw"] or p["txt_matches_raw"] is False]
    failures += [p["path"] for p in prior if not p["matches_prior_review"]]
    print(json.dumps({"pairs_checked":len(pairs),"prior_hashes_checked":len(prior),"failures":failures,
                      "fixtures":4}))
    if failures: raise SystemExit(1)
if __name__ == "__main__":
    main()
