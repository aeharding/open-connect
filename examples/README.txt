CMU command/file-capture vertical slice — offline review guide

Code: ../cmu_bench/session.py, ../cmu_bench/files.py, ../scripts/cmu-session.py
Tests: ../tests/test_session.py, test_files.py, test_cli.py, run_offline.py
Coordinator handoff: ../notes/tooling-development-result.txt

Start with an offline plan (no enumeration, port open, TX or output files):
 hc exec --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B scripts/cmu-session.py --action command --command id
 hc exec --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B scripts/cmu-session.py --action export --path /etc/version --checksum md5 --encoder base64

Run all host-only tests through Herdr:
 hc run --bg --name cmu-tooling-tests --cwd /Users/aeharding/mazda-cmu-bench .venv/bin/python -B tests/run_offline.py
 hc wait cmu-tooling-tests
 hc read cmu-tooling-tests --lines 80
Test runner saves an immutable dated result and source hashes in tooling-runs/.
No dependency installs. .venv Python3.13.7, pySerial3.5, unittest, POSIX PTYs.

Live prerequisites and commands are in the handoff. Sole UART owner t14 must
coordinate with t6; old helpers do not honor this tool's advisory lock. The
latest operator report at22:52 CST confirms normal root/firmware after t6-approved
recovery (../notes/console-recovery-observation.txt). t14 then verified live identify
and both exact exports using the29-test source; ../notes/exact-file-capture-observation.txt
records the limited observed profile. A subsequent SystemExit-only exception fix
passes30 tests without changing wire semantics. Latest hashes are in
operator-ready-exception-fix.json; this worker remains offline.

Protocol and trust boundary:
 - One private /tmp/cmu-bench-locks-UID/ FTDI-keyed flock inode. Lock is never
   unlinked; fd remains held through serial.close and evidence finalization.
 - Production selects only unique 0403:6001/A9048JM0 at a macOS USB callout
   path, re-enumerates before/after open, exclusive=True,115200/8/N/1,no flow,
   RTS/DTR requested inactive. No CLI PTY/arbitrary-device override exists.
 - Default CLI dry-run; explicit --live defaults receive-only. No newline in
   receive mode. --solicit-prompt is an explicit assertion of a KNOWN IDLE
   shell, after a brief passive guard. Absence of a continuation prompt is
   not proof of an idle shell. A quiet preexisting foreground task cannot be
   identified by passive UART silence; the operator must reconcile it first.
 - Shell/login/password/continuation/unknown/uncertain are distinct states.
   A task requires a fresh nonce-framed root id and exact55.00.750B/cmu150_NA
   metadata. Any TX/read timeout, cancellation or framing damage after TX
   prevents further sends in that Session. No login, retry, reset/break,
   Ctrl-C, service stopping or automatic remote cleanup is implemented.
 - CMU1 <128-bit nonce> BEGIN and CMU1 <nonce> END <actual shell rc> are full
   lines; completion also requires a NEW shell prompt following END. TX builds
   markers from separate printf format/nonce args. Echo contains no expected
   full record. Nonces distinguish incidental console text; this is not a
   cryptographic authentication protocol. Command output includes unfiltered
   background logs and framing newline; it is an observation, not a file.
 - Each actual TX physical line including all quoting is <=600 bytes; total
   command <=32KiB. Multiline quoting is intentional. A host deadline does not
   guarantee arbitrary remote work stopped after port close. Export alone
   wraps its own script in verified BusyBox timeout -t20 -s9 /bin/sh -c.
 - File path allowlist: /etc/version, /jci/version.ini; <=16384 bytes, regular
   and not symlink.1024-byte decoded chunks. base64 or lowercase hex. Numbered
   contiguous offset/size records, exact BEGIN/END, source size and MD5+POSIX
   cksum before/after, strict decode, matching host size/MD5/CRC, host SHA256.
   Optional SHA256 profile exists but target sha256sum is absent. MD5+CRC are
   transfer-integrity checks, not adversarial authenticity. Matching pre/post
   checks do not prove atomic snapshot. No chunk checksums, resume or retry.
   Original mode/owner/timestamps are not exported by this minimal slice.
 - Partial/corrupt transfers remain in raw evidence and never create an exact
   artifact. Logs outside complete file records remain in raw evidence; bytes
   inside damaged/interleaved frames fail length/hash/sequence checks. No
   display-filtered console text is treated as exact data.

Bundles:
 Private new directory (0700), files0600. rx.bin/tx.bin are exact acknowledged
 transport bytes; events.jsonl has UTC+monotonic RX/TX hex and separate requested
 TX/unknown-delivery records. On write exception, bytes sent beyond the last
 acknowledged count are unknowable; outcome remains unknown. Original received
 bytes and command echoes stay untouched. Command/wire/output or partial output
 files and manifest include source SHA256, actual statuses, deadlines, identity,
 adapter observations, open/close state, hashes/counts and file provenance.
 live_requested is intent; adapter_observed and serial_port_opened are separate
 successful observations. No camera or restore/recovery validation is implied.
 Live bundles may contain private console data: keep out of versioned fixtures.

Evidence/source index:
 tooling-index.tsv links immutable test results, observed fixture and capability
 report. etc-version-observed.json is a provenance-linked nonsecret derivative
 of t14's31-byte hex/MD5/CRC report, not a new live transfer or complete backup.
 All nonce frames and fake identity responses in tests are synthetic. Raw login
 captures and credentials were never copied into fixtures. Original files in
 inventory/,logs/,captures/ and the two existing helper scripts were not edited.
 The first15-test run exposed an overescaped continuation regex; its failure
 is retained in tooling-runs/initial-test-failure.txt and fixed in later runs.
