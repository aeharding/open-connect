#!/usr/bin/env python3
"""Seed this dated preservation catalog from saved evidence only, via hc.
One-shot: refuses to replace facts/hypotheses/decisions. Use new records later.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "research"
NOW = datetime.now(timezone.utc).isoformat()
def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
def put(path, data):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x") as fp:
        fp.write(data)
def jsonl(path, values):
    put(path, "".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values))
original_path = next((R / "manifests").glob("*-original-evidence.json"))
original = json.loads(original_path.read_text())
original_by_path = {v["path"]: v for v in original["files"]}
def ev(path, locator):
    return {"id": original_by_path[path]["id"] if path in original_by_path else "ev-" + hashlib.sha256(path.encode()).hexdigest()[:12],
            "path": path, "sha256": sha(path), "locator": locator}
status = "notes/status.txt"
operator = "notes/interim-operator-plan.txt"
plan = "notes/interim-plan.txt"
base = "notes/interim-baseline-plan.txt"
development = "notes/interim-development-research-plan.txt"
version = "inventory/20261112T2135-cmu-version.ini"
discovery = "logs/20261112T213524.771496-0600-system-discovery.bin"
capability = "runs/20261112T223253-0600-t14-afk-baseline/tool-capabilities.txt"
audit = "research/manifests/2026-11-12-saved-evidence-audit.json"
facts = []
def fact(fid, claim, category, refs, tags, scope="CMU 55.00.750B cmu150_NA; historical bench observations", limits="", conflicts=None):
    facts.append({"id":fid,"claim":claim,"classification":category,
                  "status":"active","recorded_at":NOW,
                  "observed_at":"2026-11-12 (host local America/Chicago)" if category.startswith("observed") else None,
                  "scope":scope,"tags":tags,"evidence":refs,
                  "limits":limits,"conflicts":conflicts or [],"superseded_by":None})
fact("F001","Saved inventory identifies the FTDI FT232R as VID:PID 0403:6001, serial A9048JM0; observed cu path /dev/cu.usbserial-A9048JM0.",
     "observed-in-saved-evidence",[ev("inventory/20261112T212931.578721-0600-inventory.json","serial_ports"),ev(status,"Attached bench devices")],
     ["uart","identity"],limits="A future owner must re-enumerate; this preservation task did not enumerate or open hardware.")
fact("F002","Historical UART sessions used 115200 8N1, all flow control off, and requested RTS/DTR inactive.",
     "observed-in-saved-evidence",[ev("logs/20261112T213105.531697-0600-uart.json","settings"),ev(operator,"Dialog identity and targeted cleanup")],
     ["uart","configuration"],limits="Requested line levels do not independently prove absence of open-time electrical transients.")
fact("F003","The passive capture has 24,233 raw RX bytes, 808 JSONL events and zero TX events; local JSONL reconstructs the raw bytes exactly.",
     "observed-host-integrity",[ev(audit,"checks: passive uart pair"),ev("logs/20261112T213105.531697-0600-uart.bin","all host raw bytes"),ev("logs/20261112T213105.531697-0600-uart.jsonl","all events")],
     ["uart","integrity"],limits="About 60 seconds of a running CMU; not full boot, full-wire completeness or transfer throughput.")
fact("F004","A carriage return at 21:32 produced the cmu login prompt, establishing two-way UART in that run.",
     "observed-in-saved-evidence",[ev("logs/20261112T213232.566785-0600-uart-prompt-probe.bin","prompt response"),ev("notes/20261112T2132-uart-observation.json","historical observation")],
     ["uart","prompt"],limits="Does not establish the current foreground state.")
fact("F005","The historical ordinary-user login returned uid=1000(user).",
     "observed-in-saved-evidence",[ev("logs/20261112T213428.427657-0600-console-login.bin","id output; private raw login capture"),ev("research/fixtures/identity-results.json","UID-only sanitized assertions")],
     ["identity","access"],limits="No credentials or TX contents are exported into the fixture or catalog.")
fact("F006","Direct root login returned uid=0(root); later identity and cleanup checks again reported root.",
     "observed-in-saved-evidence",[ev("logs/20261112T213816.865970-0600-console-root-login.bin","id output; private raw login capture"),ev("logs/20261112T214554.100346-0600-interim-dialog-identity.bin","fresh id output"),ev(operator,"Dialog identity and targeted cleanup")],
     ["identity","access"],limits="A shell may persist across Mac port closure; no current UID is inferred from a prompt.")
fact("F007","The prior privilege-discovery attempt reported that su must be setuid; direct root login was the working route.",
     "observed-in-saved-evidence",[ev("logs/20261112T213647.184470-0600-privilege-discovery.bin","su error response"),ev(status,"UART and authenticated console")],
     ["identity","permissions"],limits="No permission repair or account change is justified by this result.")
fact("F008","Installed metadata is JCI_SW_VER=MAZ_CMU-150_55.00.750, JCI_SW_VER_PATCH=B, JCI_SW_FLAVOR=cmu150_NA: 55.00.750B North America.",
     "observed-in-saved-evidence",[ev(discovery,"cat /jci/version.ini output"),ev(version,"installed version fields"),ev("research/fixtures/firmware-fields.json","four allowlisted fields")],
     ["firmware","baseline"],limits="Metadata is observed; the existing extracted artifact is not byte-exact backup evidence.")
fact("F009","JCI_SW_NEXT_VER=MAZ_CMU-150_55.00.800 is a separate metadata field and does not identify the installed firmware.",
     "interpretation-of-observed-fields",[ev(version,"JCI_SW_NEXT_VER alongside installed fields"),ev(base,"Verified facts and their limits")],
     ["firmware","metadata"],limits="No installed upgrade or available rollback is established by NEXT_VER or PRIOR_VER.")
fact("F010","Saved uname reports Linux cmu 3.0.35 ARMv7l, built March 15, 2015.",
     "observed-in-saved-evidence",[ev(discovery,"uname output"),ev(status,"Installed firmware")],
     ["kernel","baseline"],limits="Does not establish full kernel configuration, drivers or storage geometry.")
fact("F011","The root-launched /jci/tools/jci-dialog titled Mac Mini connected was visibly verified in the prior camera observation.",
     "observed-by-prior-operator",[ev("logs/20261112T213836.165677-0600-open-root-bench-dialog.bin","launch response"),ev("captures/20261112T213842.996395-0600-webcam.jpg","prior observed dialog frame"),ev("notes/20261112T2139-control-test.json","ui_test camera attestation")],
     ["ui","dialog","camera"],limits="Preservation worker did not inspect new pixels. This proves historical visible dialog control, not commander input, OK activation or boot/recovery.")
fact("F012","The operator checked the exact dialog argv twice, sent TERM only to its owned historical PID18090, confirmed the PID absent, and inspected a fresh frame showing home without that dialog.",
     "observed-by-prior-operator",[ev(operator,"What was actually checked, sections 1-2"),ev("research/fixtures/dialog-lifecycle.json","provenance and returned-marker assertions"),ev("captures/20261112T214650.188879-0600-webcam.jpg","operator-inspected post-cleanup frame")],
     ["ui","cleanup","lifecycle"],limits="PID18090 is historical and must never be reused as a cleanup target. This was targeted termination, not a test of software OK.",
     conflicts=["notes/20261112T2139-control-test.json ui_test.left_for_user_to_dismiss_with_ok is superseded by this cleanup evidence."])
fact("F013","The prior Herdr camera capture completed with FFmpeg exit0, one 1280x720 JPEG of 126507 bytes, and an operator visual assessment of home/Communication without the test dialog.",
     "observed-by-prior-operator",[ev("logs/20261112T214650.188879-0600-camera-capture.json","capture_ok, returncode, size"),ev(operator,"Camera evidence through normal Herdr execution")],
     ["camera","visibility"],limits="Angled with left edge cropped and bright highlights; requested 5fps differs from reported 24.75fps input. No current camera access or framing change.")
fact("F014","Input inventory lists event0 touch, event1 virtual keyboard, event2 virtual mouse, and event3-5 filtered keyboard/mouse/touch; these and /dev/uinput are root-only 0600.",
     "observed-in-saved-evidence",[ev("logs/20261112T214742.749982-0600-interim-input-readonly.txt","INPUT_PROC and INPUT_NODES"),ev("research/fixtures/input-listing.json","normalized sanitized inventory")],
     ["input","permissions"],limits="No event injection, grabbing or physical commander test occurred. No named commander does not imply commander absence.")
fact("F015","The read-only PATH query found dbus-send, dbus-monitor, timeout, strings, grep and find; evtest/getevent/sendevent/xdotool were not found in that PATH.",
     "observed-in-saved-evidence",[ev("logs/20261112T214742.749982-0600-interim-input-readonly.txt","TOOL_PATHS"),ev(operator,"Read-only input/navigation discovery")],
     ["input","tools"],limits="PATH absence does not prove filesystem absence; sockets and directory names do not prove service methods.")
fact("F016","The preserved inventory version.ini artifact is 13334 host bytes and contains trailing output from a separate /etc/version read; the remote source was listed as 13304 bytes.",
     "observed-host-plus-prior-operator",[ev(version,"entire original artifact; host length"),ev(base,"Prominent backup gap"),ev(capability,"Remote exact-file metadata")],
     ["backup","metadata","gap"],limits="Preserve unchanged. This artifact is a reference, not a byte-exact backup, regardless of any later capture.")
fact("F017","The reviewed baseline evidence does not demonstrate a full storage backup, verified restore, complete boot/recovery, or second host copy.",
     "evidence-gap",[ev(base,"Status and scope; deferred work"),ev(plan,"Verified starting point and baseline gate")],
     ["backup","recovery"],limits="This catalog and local Git add provenance only; they do not create a second raw-evidence copy or recovery set.")
fact("F018","The inherited handoff assigns CMU2S TX to FTDI RXI and CMU2T RX to FTDI TXO with common ground; connector viewing direction remains conflicted between Rev3 and spoken instructions.",
     "inherited-unresolved-hardware-reference",[ev(status,"Inherited hardware constraints; Rev3 library identifier")],
     ["hardware","uart","conflict"],limits="Working UART validates the electrical path used, not every connector view/contact association. Rev3 PDF was not retrieved in this task.")
fact("F019","Rev3 proposes hub1A ground while the inherited report says factory cavity1A is empty; hub1E/1G AUX donor extraction/fit was never established.",
     "inherited-unresolved-hardware-reference",[ev(status,"Inherited hardware constraints")],
     ["hardware","hub","conflict"],limits="No supply/contact changes are authorized; conflicting physical references remain unresolved.")
fact("F020","The existing inventory identified no USB relay; B+/ACC arrangement, relay model/channels and actual shutdown delay remain unverified.",
     "evidence-gap",[ev(status,"Attached bench devices; inherited hardware constraints"),ev(operator,"Dependencies software cannot currently complete")],
     ["power","relay","dependency"],limits="No switching, reboot or power-cycle evidence; no user physical intervention is available.")
fact("F021","Physical commander response, actual USB-media and SD navigation, and the retrofit hub's exact identity are unverified in the reviewed records.",
     "evidence-gap",[ev(status,"Remaining milestones"),ev(plan,"Priority4"),ev(operator,"Dependencies software cannot currently complete")],
     ["input","usb","sd","hub"],limits="Mac USB enumeration and synthetic input cannot validate these end-to-end functions.")
sources = [json.loads(line) for line in (R / "sources/manifest.jsonl").read_text().splitlines()]
by_source = {s["id"]:s for s in sources}
def source_ref(sid, section):
    s = by_source[sid]
    return {"id":sid,"path":s["snapshot_path"],"sha256":s["sha256"],
            "requested_url":s["requested_url"],"final_url":s["final_url"],"locator":section}
fact("F022","Mazda's 2018 retrofit packet specifies v70.00.21 or later before fitting the compatible hub and warns older firmware may not recognize it.",
     "reference-primary-manufacturer",[source_ref("mazda-retrofit-2018","PDF p9/20 Common-2; repeated p13/20 MAZDA6-1")],
     ["firmware","hub","retrofit"],scope="2018 Mazda retrofit packet, named compatible hub/cable kits; actual bench hub revision unknown",
     limits="Literal document form is v70.00.21; not silently normalized to the 2019 patch suffix.")
fact("F023","Mazda SA-001/19 p9/9 names 70.00.021B or later; p3/9 explains cases where an unrecognized new hub prevents USB software updating.",
     "reference-primary-manufacturer",[source_ref("mazda-sa00119-2019","p3/9 failure mode; p7-9 hardware recovery discussion; p9/9 step3")],
     ["firmware","hub","recovery"],scope="Mazda SA-001/19 issued 2019-04-05, described retrofit circumstances",
     limits="Literal form is 70.00.021B. Hardware recovery procedure is reference context; no recovery was attempted.")
fact("F024","The observed 55.00.750B is below both documented retrofit prerequisites, so this firmware/hub combination cannot be assumed a supported CarPlay retrofit baseline.",
     "inference-from-bench-and-primary-references",[ev(version,"55.00.750 and B fields"),source_ref("mazda-retrofit-2018","p9/20"),source_ref("mazda-sa00119-2019","p9/9")],
     ["firmware","hub","compatibility"],limits="Inference does not identify this hub, prove failure of every USB/SD function, prove bad wiring, or authorize flashing.")
fact("F025","The saved official pySerial API documents POSIX exclusive mode and cautions that drivers/OS may activate RTS/DTR on open, including possible glitches when requested levels differ.",
     "reference-primary-project",[source_ref("pyserial-api","serial.Serial exclusive parameter; open() RTS/DTR note")],
     ["uart","host-tooling"],scope="pySerial API reference snapshot; bench uses pySerial3.5",
     limits="exclusive=True supplements coordination; it is not proof every external tool honors ownership or that line levels never glitch.")
fact("F026","The community hardware author's notes explicitly label Sumitomo6098-5611 unverified and describe FlashFX/relfs storage layers.",
     "reference-community-author",[source_ref("hardware-silverchris","Connectors/Power-Communication; Storage/SPI-NOR,eMMC,NAND")],
     ["hardware","storage","reference"],scope="Author's hardware documentation; board/model/firmware applicability to this bench not established",
     limits="Not Mazda manufacturer wiring authority, a buying specification, a verified bench partition map or a generic dd-restore recipe.")
fact("F027","Offline auditing reconstructed all18 historical JSONL RX streams exactly against their raw .bin files; companion .txt files matched, and five prior-review hashes matched.",
     "observed-host-integrity",[ev(audit,"all checks and prior_review_hash_comparisons")],
     ["integrity","provenance"],scope="119-file initial local-evidence snapshot at 2026-11-13T04:33:56Z",
     limits="No raw file rewrite, no completeness/recovery/remote-checksum claim.")
fact("F028","Operator t14 reports BusyBox1.19.2, sha256sum absent from PATH with rc127, and available MD5/cksum/base64/od/wc/stat tools.",
     "observed-by-current-operator-report",[ev(capability,"Paths and advertised usage; explicit rc notes")],
     ["tools","baseline","transfer"],scope="t14 2026-11-12 22:33-22:34 CST, root CMU55.00.750B cmu150_NA",
     limits="Preservation worker reads saved report only; no device-side SHA-256. PATH absence is scoped.")
fact("F029","Operator t14 verified BusyBox timeout syntax requires -t SECS, unlike GNU positional seconds, and exercised timeout -t10 -s9 with outer rc0/end marker.",
     "observed-by-current-operator-report",[ev(capability,"timeout usage and exercised command")],
     ["tools","timeout"],scope="BusyBox1.19.2 on this firmware, t14 capability run",
     limits="Usage output from BusyBox --help may return1; do not invent GNU options.")
fact("F030","Operator t14 reports /jci/version.ini=13304 bytes, MD5=5488b62f403d5296f58566c8499f7d44, POSIX cksum=958101073/13304; /etc/version=31 bytes, MD5=10cac4792dbca7d886eb2d9ee80d0647, cksum=2910742528/31.",
     "observed-by-current-operator-report",[ev(capability,"Remote exact-file metadata; each wc/md5sum/cksum/stat rc0")],
     ["backup","transfer","metadata"],scope="t14 2026-11-12 22:33-22:34 CST source-file observations",
     limits="Metadata/probe output is not a verified copied backup. MD5/CRC are transfer checks, not device-side SHA-256 or recovery evidence.")
jsonl("research/facts.jsonl", facts)

hypotheses = []
def hypothesis(hid, question, test, deps, related):
    hypotheses.append({"id":hid,"status":"open","recorded_at":NOW,"question":question,
                       "proposed_test":test,"dependencies":deps,"related_ids":related,
                       "firmware_scope":"Preserve CMU55.00.750B cmu150_NA",
                       "result":None,"superseded_by":None})
hypothesis("H001","Does this exact retrofit hub retain required legacy USB/SD functionality on firmware55?",
           "Identify hub/cabling and distinguish CMU enumeration, mounted usable media, and visible legacy USB/SD behavior under an authorized operator run.",
           ["Actual hub identity","Existing media and agent-accessible controls; physical insertion is unavailable"],["F021","F022","F023","F024"])
hypothesis("H002","What connector view and hub1A supply assignment apply to the actual harness?",
           "Compare exact hardware labels, authoritative connector-view documentation and inspected harness evidence without inserting contacts or changing supply wiring.",
           ["Physical evidence or suitable automation fixture","Unretrieved Rev3 source"],["F018","F019","F026"])
hypothesis("H003","Can a framed read-only UART transfer produce one exact checksum-verified small file?",
           "Use validated decoder and observed BusyBox syntax; verify source size+MD5/cksum before/after, complete frames and host equality.",
           ["t12 offline decoder acceptance","t14 sole UART owner; bounded operator handoff"],["F016","F028","F029","F030"])
hypothesis("H004","Which discovered service or input path can navigate and return without persistent state changes?",
           "Inspect installed interface signatures and permissions first; propose one bounded reversible run with fresh before/after proof and software cleanup.",
           ["Operator-owned saved extracts","Verified input map and automatic return path"],["F014","F015"])
hypothesis("H005","What FlashFX/relfs acquisition layer and recovery procedure are actually usable for this CMU?",
           "Map storage and device-unique dependencies read-only; compare layer/tooling evidence before proposing any separately authorized restore study.",
           ["Verified storage map","Independent access/recovery strategy; no restore authorized"],["F017","F026"])
hypothesis("H006","Will the eventual Ethernet adapter have a compatible CMU driver/link and existing SSH capability?",
           "Compare actual adapter USB IDs to installed/builtin driver evidence and existing SSH state; do not load modules or change networking.",
           ["Hardware arrival/physical attachment via existing automation","Operator read-only inventory"],["F021","F028"])
hypothesis("H007","What are actual B+/ACC shutdown timing and safe relay channel behavior?",
           "After separately commissioned hardware exists, record actual shutdown without assuming DTR/RTS can control power.",
           ["Relay identity and wiring","Physical power automation; absent now","Separate authorization for power experiments"],["F020"])
hypothesis("H008","Where can a verified independent second raw-evidence copy be stored?",
           "Use an already available authorized destination, copy originals and verify hashes; record destination and limits.",
           ["No verified destination in present records"],["F017","F027"])
jsonl("research/hypotheses.jsonl", hypotheses)

decisions = [
 ("D001","Preserve firmware55 and current bench state","Continue host preservation, offline tooling and bounded read-only work within coordinator authorization.",
  "Do not change firmware, power, accounts, persistent settings, USB/SD or networking.",["F008","F017","F024"],["Upgrade now","Power-cycle for boot evidence"]),
 ("D002","Resolve historical manual-dismiss instructions through evidence precedence","The dialog is already cleared; no human intervention is pending.",
  "Later identity-guarded cleanup and visual attestation supersede ui_test.left_for_user_to_dismiss_with_ok and old README wiring/manual steps.",["F011","F012"],["Carry forward stale manual OK requirement"]),
 ("D003","Single hardware operator; preservation worker stays offline","t14 is sole UART/camera owner for the current assignment; route live requests through t6.",
  "No UART, camera, CMU access or further delegation by this worker; all programs/files/communication through Herdr hc.",["F001","F002"],["Second passive logger or helper on UART"]),
 ("D004","Local Git allowlist and private original retention","Track reviewed instructions, source/tools, plans, manifests, catalog and small sanitized derivatives.",
  "Ignore raw evidence, backups, state, original reference snapshots, environments/caches and private records; no remote and no identity change.",["F027"],["git add .","Publish or push raw originals"]),
 ("D005","Keep byte-exact and recovery claims gated","The original version.ini extraction remains a metadata reference; current remote metadata is a prerequisite only.",
  "New copied files need bounded frame completion, remote/host length+checksum and source stability. Full recovery and second-copy claims remain unproven.",["F016","F017","F030"],["Treat console-stripped extraction or host hash alone as verified backup"]),
 ("D006","Preserve literal Mazda version requirements and scope","Record 2018 v70.00.21 and 2019 70.00.021B distinctly.",
  "Documented retrofit mismatch does not prove legacy USB/SD failure, identify exact hub, justify rewiring or authorize upgrade.",["F022","F023","F024"],["Normalize both requirements silently","Diagnose all hub behavior as bad wiring"]),
 ("D007","Keep physical-reference conflicts unresolved","Preserve connector-view, hub1A, donor contact/fit and power dependencies in handoff.",
  "The AFK user will not press controls, move camera, insert media or wire anything; missing physical operations remain dependencies.",["F018","F019","F020","F021"],["Assign manual bench actions to user","Force wiring agreement with Rev3"])
]
jsonl("research/decisions/2026-11-12-preservation.jsonl",[
 {"id":i,"date":"2026-11-12","recorded_at":NOW,"title":title,"decision":choice,"rationale_and_scope":reason,
  "related_ids":related,"alternatives_not_selected":alternatives,"status":"active","superseded_by":None}
 for i,title,choice,reason,related,alternatives in decisions])

# Preserve exact download metadata, enrich applicability without changing source bytes.
for s in sources:
    s["cataloged_at"] = NOW
    s["revision"] = "content SHA-256; moving URL edition captured locally"
    s["prior_review_reference"] = ev(development,"Source integrity checked: 2018 and 2019 SHA-256/byte counts") if s["expected_sha256"] else None
    if s["expected_sha256"]:
        s["expected_from"] = development + (" line117" if s["id"] == "mazda-retrofit-2018" else " line118")
    if s["id"] == "mazda-retrofit-2018":
        s.update(author="Mazda",authority="Manufacturer-authored document, NHTSA mirror",
                 page_count=20,relevant_sections=["PDF p9/20 Common-2","PDF p13/20 MAZDA6-1"],
                 exact_version_forms=["v70.00.21"],supports=["F022","F024"],
                 scope="Compatible retrofit hub/cable kits identified by packet; actual bench revision unknown",
                 conflicts=["Preserve different literal version form from 2019 bulletin; no claim of universal legacy USB/SD failure."])
    elif s["id"] == "mazda-sa00119-2019":
        s.update(author="Mazda",authority="Manufacturer-authored document, NHTSA mirror",
                 document_date="2019-04-05",page_count=9,
                 relevant_sections=["p3/9 failure mode","p7-9/9 original-hub/cable recovery context","p9/9 step3"],
                 exact_version_forms=["70.00.021B"],supports=["F023","F024"],
                 scope="SA-001/19 described installation/update circumstances",
                 conflicts=["2018 packet uses v70.00.21; do not silently equate patch suffix requirements."])
    elif s["id"] == "hardware-silverchris":
        s.update(author="silverchris/mazda-cmu-documentation contributors",
                 authority="Primary author community hardware notes; not Mazda manufacturer documentation",
                 relevant_sections=["Storage","Connectors/Power-Communication"],
                 supports=["F026"],scope="Hardware/model applicability to this bench unverified",
                 conflicts=["Sumitomo6098-5611 explicitly unverified","No external connector diagram resolves inherited Rev3/1A conflicts in this task."])
    else:
        s.update(author="pySerial project",authority="Official project API documentation",
                 relevant_sections=["serial.Serial exclusive parameter","open() RTS/DTR note"],
                 supports=["F025"],scope="pySerial documented API, bench pySerial3.5",
                 conflicts=["Requested inactive RTS/DTR is not measured absence of glitches","exclusive mode is supplementary to one-owner coordination"])
    if s["id"].startswith("mazda-"):
        extracted = Path(s["snapshot_path"]).with_suffix(".pdf-text.txt")
        s["local_text_derivative"] = {"path":str(extracted),"sha256":sha(str(extracted)),
                                      "method":"hc-run Python wrapper -> /usr/bin/swift research/tools/extract-pdf-text.swift PDF; PDFKit text extraction, exit0",
                                      "kind":"ignored text derivative; original PDF remains authoritative"}
(R / "sources/manifest.jsonl").write_text("".join(json.dumps(s,ensure_ascii=False)+"\n" for s in sources))

# Supplemental current-operator evidence is separate from the initial manifest.
supplemental = [capability]
for prefix in ("20261112T223327.247687-0600-afk-t14-identity",
               "20261112T223344.922252-0600-afk-t14-toolpaths",
               "20261112T223408.808470-0600-afk-t14-capdetail"):
    supplemental.extend("logs/" + prefix + ext for ext in (".bin",".jsonl",".json",".txt")
                        if (ROOT / ("logs/"+prefix+ext)).is_file())
put("research/manifests/2026-11-12-current-capability-evidence.json",json.dumps({
 "created_at":NOW,"origin":"t6 Herdr message refers t14 tool-capabilities.txt; source report names raw prefixes",
 "scope":"Current operator report plus locally hashed supporting original files; no hardware access by preservation worker",
 "files":[{"path":p,"sha256":sha(p),"bytes":(ROOT/p).stat().st_size,"access":"local-only; potentially private raw output"} for p in supplemental],
 "limits":"No exact copied backup yet. Remote MD5/cksum metadata is reported, not device-side SHA-256. Raw source contents never committed."
},indent=2)+"\n")

put("research/context/SUMMARY.txt", """DERIVED HANDOFF SUMMARY — not an original user or hardware document
Prepared 2026-11-12 (America/Chicago); catalog uses UTC timestamps.
Coordinator: Herdr t6. Current sole hardware owner: t14. Research worker: t13.
Start: research/index.txt; searchable catalog: research/index.tsv.
Original records remain in their original paths. References carry host SHA-256.

CONSTRAINTS AND SCOPE
No human bench interaction is available. Agents own software operation/cleanup.
No firmware change (keep55.00.750B/cmu150_NA), power change, account/permission
change, persistent-setting change, USB/SD change or networking change.
No UART/camera/CMU access by this research worker. All operations use Herdr hc.
No subagents. Physical actions unavailable through automation are dependencies.
Existing scripts are historical tools, not proof that a new command completed.
No recurring schedule, publishing, remote Git repository or firmware action.

OBSERVED AND REPORTED STATE
Stored evidence establishes 1152008N1 two-way UART, user uid1000, direct root uid0,
Linux3.0.35 ARMv7l, and installed55.00.750B. NEXT_VER55.00.800 is separate metadata.
FTDI identity0403:6001 A9048JM0; future acquisition must re-enumerate.
A root-launched native test dialog was visible, then its exact cmdline was checked
twice, only its owned process was terminated, absence was confirmed and a fresh
operator-inspected frame showed home without it. PID18090 is historical only.
The old left_for_user_to_dismiss_with_ok flag is superseded. No manual OK is due.
Input nodes were listed, not injected. Synthetic input cannot validate commander.
Camera framing is angled/cropped; no assumption of complete control visibility.
The last reported shell is root; a future operator must confirm actual state/uid.

NEW OPERATOR CAPABILITIES (t14,22:33–22:34CST; F028–F030)
BusyBox1.19.2; sha256sum not found in PATH/rc127; MD5+cksum and encoding tools
available. timeout requires -t SECS. Remote version.ini13304B; /etc/version31B.
Exact hashes/counts and raw support paths are in the supplemental manifest.
This is metadata/probe evidence, not a copied or verified backup.

SOURCE AND HARDWARE LIMITS
Saved Mazda2018 PDFp9/20 says v70.00.21; Mazda2019p9/9 says70.00.021B.
Both PDF byte counts/hashes match prior reviews. Current55 is below those
retrofit prerequisites; actual hub identity and legacy USB/SD function stay unknown.
The version strings remain literal; no silent patch-equivalence or flash advice.
Community hardware notes are reference context, not manufacturer wiring proof.

UNRESOLVED PHYSICAL REFERENCE CONFLICTS AND DEPENDENCIES
- Rev3 versus spoken2S/2T connector viewing direction remains conflicted.
  Working UART proves the used path, not every harness mapping/contact.
- Rev3 hub1A-ground conflicts with reported factory-empty cavity1A.
- Hub1E/1G AUX donor extraction/contact fit remains unknown.
- Sumitomo6098-5611 is explicitly unverified, not a purchase specification.
- Actual hub/cables, physical commander, usable USB media and SD navigation are
  unverified. Preserve USB/SD; AUX is not required.
- Relay model, channels, B+/ACC wiring and shutdown timing are unverified.
- Ethernet arrival/attachment/chipset/driver/link/SSH remain dependencies.
- Camera missing edges cannot be recovered by physical movement in this task.
- Rev3 Library identifier is retained in notes/status.txt; no Rev3 PDF was
  retrieved or independently validated here. No generic Linux restore assumed.

PRESERVATION AND HANDOFF
119 initial original/context files are hashed;18 historical RX streams reconstruct
exactly from JSONL, and five previously published evidence hashes match.
Four small allowlisted sanitized summaries contain no login/TX credentials,
Bluetooth identities or FGSN. They are derived assertions, not complete transcripts.
Original evidence and source snapshots are ignored and remain local.
inventory/20261112T2135-cmu-version.ini is13334B with unrelated trailing output:
preserve unchanged as metadata, never call it a byte-exact backup.
Local Git/manifests are not an independent second copy, full backup or recovery.
No verified second destination or demonstrated restore is known.
Next work is H003: accept offline framed tooling, then operator-capture one exact
small file using remote/host count+checksum and source stability. Index future
run results without rewriting originals, old claims or source editions.
Review notes/research-preservation-result.txt for commit and final exclusions.
""")

put("research/SCHEMA.txt", """Canonical research records
index.tsv is the searchable catalog; index.txt is its human entry point.
facts.jsonl stores atomic claims with classification, scope, limits and evidence.
Classification keeps observed local bytes, prior/current operator observations,
manufacturer references, community references, interpretation/inference,
inherited unresolved references, and evidence gaps distinct.
Every evidence ref has original path and host SHA-256 plus a relevant locator.
A host hash proves local byte identity only. It is not a remote comparison.
Sources/manifest.jsonl records exact requested/final URL, retrieval UTC, hash,
size, content metadata, relevant page/section, applicability, support, conflicts,
prior-review match and superseded status. Original snapshots/text stay ignored.
Hypotheses retain open questions, test, dependencies and disposition; no result
means unknown. Decisions are dated append-only records with rationale and
alternatives. Supersede by new IDs rather than silently rewriting history.
The initial original manifest is a point-in-time inventory, not an archive.
New operator evidence has a separate supplemental manifest; do not merge an
ongoing run into an old snapshot or claim original immutability from a path alone.
Fixtures are small explicitly sanitized derivatives. Their kind/transformation
and original hashes are recorded; they are not raw login or replay transcripts.
Do not place credentials, TX login data, FGSN, BT identities, private keys,
copied CMU configuration or original photos inside tracked fixtures.
Use explicit staging allowlists. Never assume .gitignore removes tracked data.
Run index rebuild after appending records:
  hc exec --cwd /Users/aeharding/mazda-cmu-bench python3 research/tools/rebuild_index.py
New source editions get new immutable paths and new records. Do not rerun the
one-shot seed/download scripts over existing catalog files.
""")
print(json.dumps({"facts":len(facts),"hypotheses":len(hypotheses),"decisions":len(decisions),
                  "sources":len(sources),"supplemental_evidence_files":len(supplemental)}))
