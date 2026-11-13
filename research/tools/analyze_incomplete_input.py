#!/usr/bin/env python3
"""Host-only provenance and analysis of the saved incomplete command. No UART."""
from datetime import datetime,timezone
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(data):return hashlib.sha256(data).hexdigest()
def file_ref(path,locator):
    data=(ROOT/path).read_bytes()
    return {"id":"ev-"+sha(path.encode())[:12],"path":path,"sha256":sha(data),"bytes":len(data),"locator":locator}
def write_new(path,value):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x") as fp:json.dump(value,fp,indent=2);fp.write("\n")
def main():
    run="runs/20261112T223253-0600-t14-afk-baseline/"
    prefix="logs/20261112T223613.143917-0600-afk-t14-network"
    events=[json.loads(x) for x in (ROOT/(prefix+".jsonl")).read_text().splitlines()]
    tx=[bytes.fromhex(e["hex"]) for e in events if e["direction"]=="tx"]
    raw=(ROOT/(prefix+".bin")).read_bytes()
    reconstructed=b"".join(bytes.fromhex(e["hex"]) for e in events if e["direction"]=="rx")
    assert reconstructed==raw
    command=tx[-1]
    assert command.endswith(b"\r")
    command=command[:-1]
    clean=re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]",b"",raw)
    start=clean.find(command[:60])
    end=clean.find(b"\r\n> ",start)
    assert start>=0 and end>start
    echo=clean[start:end].replace(b"\r\r\n",b"")
    assert len(command)==1363 and len(echo)==1022 and command.startswith(echo)
    state="unquoted";open_at=None;i=0
    while i<len(echo):
        c=echo[i]
        if state=="single":
            if c==39:state="unquoted";open_at=None
        elif state=="double":
            if c==34:state="unquoted";open_at=None
            elif c==92 and i+1<len(echo) and echo[i+1] in b'$\x60"\\\n':i+=1
        else:
            if c==39:state="single";open_at=i
            elif c==34:state="double";open_at=i
            elif c==92:i+=1
        i+=1
    cancel=[json.loads(x) for x in (ROOT/(run+"continuation-cancel.jsonl")).read_text().splitlines()]
    cancel_rx=b"".join(bytes.fromhex(e["hex"]) for e in cancel if e["direction"]=="rx")
    cancel_tx=[bytes.fromhex(e["hex"]) for e in cancel if e["direction"]=="tx"]
    assert cancel_rx==(ROOT/(run+"continuation-cancel.bin")).read_bytes()
    assert cancel_tx==[b"\x03"]
    source=json.loads((ROOT/"research/sources/manifest.jsonl").read_text().splitlines()[-1])
    assert source["id"]=="busybox-1.19.2"
    evidence_paths=[prefix+ext for ext in (".bin",".jsonl",".json",".txt")]
    evidence_paths += [run+"network-input-failure.json"]+[run+"continuation-cancel"+ext for ext in (".py",".bin",".jsonl",".json")]
    evidence=[file_ref(p,"saved original recovery evidence; potentially private contents") for p in evidence_paths]
    now=datetime.now(timezone.utc).isoformat()
    result={"created_at":now,"method":"hc exec python3 research/tools/analyze_incomplete_input.py",
        "scope":"Offline saved-evidence analysis only; no live bench access",
        "network_rx_reconstructs_raw":True,"sent_command_bytes_excluding_CR":len(command),
        "tx_event_lengths":[len(t) for t in tx],"echo_before_continuation_bytes":len(echo),
        "echo_is_exact_sent_command_prefix":True,"echo_sha256":sha(echo),
        "sanitization":"Remove ANSI CSI for locating echo, then only observed CRCRLF soft-wraps; export counts/hashes/quote state, not command or runtime identities.",
        "limited_ascii_quote_scan":{"end_state":state,"last_open_quote_zero_based":open_at,
            "has_here_doc_operator":b"<<" in echo,"contains_literal_newline":b"\n" in echo,
            "limit":"Static lexical scan only, not a BusyBox execution/reproduction or complete shell grammar proof."},
        "stock_source_limit_comparison":{"FEATURE_EDITING_MAX_LEN_default":1024,"lineedit_input_cap_expression":"maxsize - 2",
            "default_maximum_printable_input_chars":1022,"matches_observed_echo_length":True,
            "limit":"CMU vendor config/patches not acquired; matching cap is strong supporting inference, not proof of exact build configuration."},
        "cancel_tx_hex":[t.hex() for t in cancel_tx],"cancel_rx_hex":cancel_rx.hex(),
        "cancel_rx_exactly_CRLF_PS2_0":cancel_rx==b"\r\n> 0",
        "empty_current_edit_line_confirmed":False,
        "current_edit_line_limit":"Trailing received0 is not proof of a typed0 or an empty buffer; its source is unknown.",
        "primary_source":{k:source[k] for k in ("id","requested_url","final_url","bytes","sha256","snapshot_path","retrieved_at")},
        "ranked_source_supported_options":[
            {"rank":1,"name":"Clear current edit line then one EOF","bytes_hex":"051504",
             "controls":"Ctrl-E, Ctrl-U, Ctrl-D",
             "preconditions":"Same incomplete quoted interactive parse, stock-compatible editor, VEOF=04, single owner, no intervening sends, coordinator approval.",
             "expected":"Current line cleared without CR/LF; EOF causes syntax error and interactive parser reset before pending evaltree.",
             "live_verified":False},
            {"rank":2,"name":"One EOF alone if current edit line certified empty","bytes_hex":"04",
             "preconditions":"Same unmatched quote AND certified empty edit line AND VEOF=04; current saved evidence does not certify emptiness.",
             "expected":"Same EOF syntax-error path; EOF on nonempty line may merely delete a character.",
             "live_verified":False},
            {"rank":3,"name":"Retain stop state and obtain independent diagnostic context",
             "preconditions":"Use only an already verified independent channel if available; none demonstrated here.",
             "expected":"Read actual shell identity/tty control settings/build evidence before deciding another recovery action.",
             "live_verified":False}],
        "not_recommended":["Repeat ETX","Repeated EOF after prompt could exit shell","CR/LF or guessed quote closures","exit/login/id text in continuation","BREAK/tty reset/reboot/power/network/service changes"],
        "verification_gate":"No text commands until actual syntax error plus expected primary prompt; then separate coordinator-reviewed short identity transaction with explicit completion. Otherwise stop and preserve unknown.",
        "evidence":evidence}
    path="research/recovery/2026-11-12-incomplete-input-analysis.json"
    write_new(path,result)
    write_new("research/manifests/2026-11-12-console-recovery-evidence.json",{
        "created_at":now,"origin":"t6 scoped recovery research request and t14 saved evidence",
        "files":[{"path":e["path"],"sha256":e["sha256"],"bytes":e["bytes"],"access":"local-only; private contents not exported"} for e in evidence],
        "limit":"No live action, restored prompt, backup, or same-version executable reproduction is claimed."})
    evidence_ref=file_ref(path,"counts, sanitization, quote scan, source comparison and candidate limits")
    source_ref={k:source[k] for k in ("id","snapshot_path","sha256","requested_url","final_url")}
    source_ref["path"]=source_ref.pop("snapshot_path")
    source_ref["locator"]="ash.c9641-9661,9746-9752,11288-11299,12157-12174,13056-13072,13109-13139; lineedit.c2228-2243,2295-2303,2496-2519,2542; Config.src63-69"
    newfacts=[
      ("F031","After exactly one saved ETX03 transmission, RX was0d0a3e2030 (CRLF > 0); no verified primary root prompt was restored.",
       "observed-saved-recovery-evidence","The received0 has unknown origin; current edit-buffer emptiness and foreground state remain unverified."),
      ("F032","The network request sent1363 command bytes, but its normalized echo before continuation is exactly its first1022 bytes and ends in single-quote state by a limited ASCII quote scan.",
       "observed-host-recovery-analysis","Removing only observed soft-wraps yields SHA256f78637347bba1854df88a0069dad5349a327e245d1cc1bfb785a5d8f62f74aa7. Matching default1024/maxsize-2 cap supports, but does not prove, stock editor truncation."),
      ("F033","Stock BusyBox1.19.2 ash with editing retries a Ctrl-C-returned zero-length input when no SIGINT trap is installed, preserving the accumulated parser state.",
       "reference-primary-source-code","Nominal release source matches reported BusyBox version, but vendor patches, exact shell identity/build options and traps are unknown."),
      ("F034","Stock BusyBox1.19.2 turns empty-line configured EOF into parser EOF; an unterminated quote raises a syntax error before the pending command is evaluated, and an interactive top-level shell resets to its command loop.",
       "reference-primary-source-code","Conditional source result, not CMU recovery validation. Nonempty Ctrl-D is deletion; EOF at a primary prompt may exit; other continuation contexts differ.")
    ]
    with (ROOT/"research/facts.jsonl").open("a") as fp:
        for fid,claim,kind,limit in newfacts:
            refs=[evidence_ref]+([source_ref] if fid in ("F033","F034") else [])
            fp.write(json.dumps({"id":fid,"claim":claim,"classification":kind,"status":"active",
             "recorded_at":now,"scope":"Saved t14 failure on55.00.750B; official BusyBox1.19.2 conditional source behavior",
             "tags":["uart","parser","recovery"],"evidence":refs,"limits":limit,"conflicts":[],"superseded_by":None})+"\n")
    with (ROOT/"research/hypotheses.jsonl").open("a") as fp:
        fp.write(json.dumps({"id":"H009","status":"open","recorded_at":now,
         "question":"Can one coordinator-approved clear-current-line plus EOF transaction abandon this saved incomplete quote without executing the pending request?",
         "proposed_test":"Review source/limits and actual current state first; source-supported candidate051504 has no CR/LF. Sole operator only; require syntax-error+primary-prompt evidence and separate fresh identity proof.",
         "dependencies":["t6 approval","t14 sole owner","Actual pending parser remains same; VEOF and vendor behavior uncertain"],
         "related_ids":["F031","F032","F033","F034"],"firmware_scope":"Keep55.00.750B/current persistent state","result":None,"superseded_by":None})+"\n")
    with (ROOT/"research/decisions/2026-11-12-preservation.jsonl").open("a") as fp:
        fp.write(json.dumps({"id":"D008","date":"2026-11-12","recorded_at":now,
         "title":"Stop uncertain continuation sends; recovery recommendations remain offline",
         "decision":"Rank a source-supported clear-current-line plus one EOF candidate for coordinator review; do not perform live recovery from this role.",
         "rationale_and_scope":"One ETX failed; source shows retry can preserve parser state. Do not append quotes/newlines/commands, repeat EOF, use BREAK, reboot or change services/network/power.",
         "related_ids":["F031","F032","F033","F034","H009"],
         "alternatives_not_selected":["Repeated ETX","Blind newline/quote closure","Treating a > prompt as safe shell readiness"],"status":"active","superseded_by":None})+"\n")
    sources=[json.loads(x) for x in (ROOT/"research/sources/manifest.jsonl").read_text().splitlines()]
    sources[-1]["supports"]=["F033","F034"]
    (ROOT/"research/sources/manifest.jsonl").write_text("".join(json.dumps(s)+"\n" for s in sources))
    print(json.dumps({"analysis":path,"evidence_originals":len(evidence),"echo_bytes":len(echo),
                      "quote_state":state,"new_facts":4,"total_facts":34,"live_actions":0}))
if __name__=="__main__":main()
