"""Synthetic candidate-binding/labels only; no real UART, camera or reboot."""
from contextlib import nullcontext, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock
import observe as candidate

BOOT = Path(__file__).resolve().parent
NONCE = "a" * 32
OP = "b" * 32
CID = "64785:20001:9876:94055:755:1018:3015:1"
OLD_BOOT = "11111111-1111-1111-1111-111111111111"
NEW_BOOT = "22222222-2222-2222-2222-222222222222"


def marker(cid=CID, kind="C", readiness="1"):
    return ("CANDIDATE_BOOT_BIND|%s|%s|%s|94055|%s|776631029|ro|%s|candidate_verified\n"
            % (NONCE, kind, cid, candidate.CMD5, readiness)).encode()


def source_output(cid=CID, md5=candidate.CMD5, crc=candidate.CCRC,
                  boot=OLD_BOOT, uptime=100.0):
    return ("\n".join(("SWST|META|" + cid, "SWST|HASH|" + md5 + "  -",
                      "SWST|CRC|" + crc, "SWST|ROOT|/dev/ffx01p1 / relfs ro,noatime 0 0",
                      "SWST|UPTIME|%s 10.0" % uptime, "SWST|BOOT_ID|" + boot)) + "\n").encode()


class BindingTests(unittest.TestCase):
    def setUp(self):
        (BOOT / "checks").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=BOOT / "checks")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bundle = self.root / "runs" / "synthetic-apply"
        self.bundle.mkdir(parents=True)
        self.evidence = self.root / "apply.json"

    def fixture(self, raw=None, rx=None, change_manifest=None):
        raw = marker() if raw is None else raw
        rx = (b"\r\nCMU1 " + OP.encode() + b" END 0\r\n/tmp/root # ") if rx is None else rx
        files = {OP + ".output.bin": raw, "rx.bin": rx}
        for name, value in files.items():
            (self.bundle / name).write_bytes(value)
        manifest = dict(mode="live", outcome="completed", serial_port_opened=True,
                        port_closed=True, identity=dict(uid=0, user="root",
                        firmware="55.00.750B", flavor="cmu150_NA"),
                        adapter=dict(vid=0x0403, pid=0x6001, serial_number="A9048JM0"),
                        operations=[dict(nonce=OP, identity_probe=False, outcome="completed",
                        exit_status=0, output_sha256=candidate.digest(raw))],
                        artifacts={name: dict(bytes=len(data), sha256=candidate.digest(data))
                                   for name, data in files.items()})
        if change_manifest:
            change_manifest(manifest)
        (self.bundle / "manifest.json").write_text(json.dumps(manifest))
        self.evidence.write_text(json.dumps(dict(schema=1, core_bundle=str(self.bundle),
                                                 trial_nonce=NONCE)))
        return self.evidence

    def binding(self):
        return candidate.apply_binding(self.evidence, root=self.root)

    def test_actual_framed_marker_binds_exact_C_identity(self):
        self.fixture(raw=b"unrelated \xe2\x98\x83 logger noise\n" + marker())
        got = self.binding()
        self.assertEqual((got["source_kind"], got["source_identity"]), ("C", CID))
        self.assertEqual((got["bytes"], got["md5"], got["crc"]), (94055, candidate.CMD5, candidate.CCRC))
        self.assertTrue(got["recovery_ready_before_publish"])
        self.assertEqual(got["output_sha256"], candidate.digest((self.bundle / (OP + ".output.bin")).read_bytes()))

    def test_candidate_binding_refusals(self):
        cases = (b"no actual binding marker\n", marker(kind="O"), marker(readiness="0"),
                 marker(cid=CID.replace("64785", "45826")),  # isolated-copy proof
                 marker().replace(b"94055|", b"94058|", 1),
                 marker().replace(candidate.CMD5.encode(), b"0" * 32),
                 marker().replace(b"|ro|", b"|rw|"),
                 marker().replace(b"candidate_verified", b"original_restored"),
                 marker().replace(NONCE.encode(), b"c" * 32), marker() + marker())
        for raw in cases:
            with self.subTest(raw=raw):
                self.fixture(raw=raw)
                with self.assertRaises(ValueError):
                    self.binding()

    def test_core_unknown_nonzero_no_prompt_or_bad_integrity_refused(self):
        changes = (lambda m: m.update(outcome="unknown"),
                   lambda m: m["operations"][0].update(exit_status=73),
                   lambda m: m.update(port_closed=False),
                   lambda m: m["identity"].update(firmware="73.00.000"),
                   lambda m: m["adapter"].update(serial_number="OTHER"))
        for change in changes:
            with self.subTest(change=change):
                self.fixture(change_manifest=change)
                with self.assertRaises(ValueError):
                    self.binding()
        self.fixture(rx=b"\r\nCMU1 " + OP.encode() + b" END 0\r\n> ")
        with self.assertRaises(ValueError):
            self.binding()
        self.fixture()
        (self.bundle / (OP + ".output.bin")).write_bytes(marker() + b"modified")
        with self.assertRaises(ValueError):
            self.binding()

    def test_duplicate_json_is_not_a_binding_override(self):
        self.fixture()
        self.evidence.write_text('{"schema":1,"schema":1,"core_bundle":"x","trial_nonce":"' + NONCE + '"}')
        with self.assertRaises(ValueError):
            self.binding()

    def test_exact_C_preflight_postboot_and_C_labels(self):
        self.fixture()
        binding = self.binding()
        before = candidate.checked_candidate_output(0, source_output(), binding)
        after = candidate.checked_candidate_output(0, source_output(
            cid=CID, boot=NEW_BOOT, uptime=8), binding, before)
        self.assertEqual((before["source_kind"], after["source_kind"]), ("C", "C"))
        self.assertEqual(after["META"], CID)
        with self.assertRaises(ValueError):
            candidate.checked_candidate_output(0, source_output(cid=CID.replace(":20001:", ":20002:")), binding)
        for raw in (source_output(boot=OLD_BOOT, uptime=8),
                    source_output(boot=NEW_BOOT, uptime=100),
                    source_output(cid=CID.replace(":9876:", ":9877:"), boot=NEW_BOOT, uptime=8),
                    source_output(cid="64785:9457:1433953097:94058:755:1018:3015:1",
                                  md5="584c67f7186ada6bae9aae1be59b5cd0", crc="376717896 94058",
                                  boot=NEW_BOOT, uptime=8)):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    candidate.checked_candidate_output(0, raw, binding, before)

    def test_logger_attached_META_is_complete_and_raw_is_unchanged(self):
        self.fixture()
        binding = self.binding()
        before = candidate.checked_candidate_output(0, source_output(), binding)
        fixture = (BOOT / "fixtures/logger-attached-fields.txt").read_bytes()
        for raw in (fixture, fixture.replace(b"\n", b"\r\n")):
            with self.subTest(CRLF=b"\r\n" in raw):
                original = bytes(raw)
                after = candidate.checked_candidate_output(0, raw, binding, before)
                self.assertEqual(after["META"], CID)
                self.assertEqual(after["source_kind"], "C")
                self.assertTrue(after["recovery_identity_matches"])
                self.assertEqual(raw, original)
        # Same observed prefix through the front door, not merely the helper.
        rc, manifest, sent, starts, printed, bundle = self.fake_run(after_bytes=fixture)
        self.assertEqual((rc, manifest["outcome"]), (0, candidate.SUCCESS))
        self.assertEqual(sent.count(candidate.stock.REBOOT), 1)
        self.assertEqual(json.loads((bundle / "after.json").read_text())["META"], CID)

    def test_attached_records_reject_duplicates_malformed_and_partial_values(self):
        self.fixture()
        binding = self.binding()
        before = candidate.checked_candidate_output(0, source_output(), binding)
        raw = (BOOT / "fixtures/logger-attached-fields.txt").read_bytes()
        duplicates = (raw + b"SWST|META|" + CID.encode() + b"\n",
                      raw + b"noise(0xbeefSWST|META|" + CID.encode() + b"\n",
                      raw.replace(CID.encode(), CID.encode() + b"SWST|META|" + CID.encode()))
        malformed = (
            raw[:-1],  # complete-looking value but no record terminator
            raw.replace(CID.encode(), CID.rsplit(":", 1)[0].encode()),
            raw.replace(CID.encode(), CID.encode() + b" trailing logger text"),
            raw.replace(candidate.CMD5.encode(), candidate.CMD5[:-1].encode()),
            raw.replace(b"776631029 94055", b"776631029"),
            raw.replace(b"8.0 10.0", b"8.0 10.0 logger text"),
            raw.replace(b"8.0 10.0", b"8.0 nan"),
            raw.replace(b"ro,noatime 0 0", b"ro,noatime 0 0 extra"),
            raw.replace(NEW_BOOT.encode(), NEW_BOOT[:-1].encode()),
            raw + b"SWST|META",  # incomplete marker may not be silently ignored
            raw + b"noiseSWST|UNKNOWN|value\n",
            raw.replace(b"SWST|META|" + CID.encode(),
                        b"printf 'SWST|META|" + CID.encode() + b"'"),
        )
        for bad in duplicates + malformed:
            with self.subTest(raw=bad):
                with self.assertRaises(ValueError):
                    candidate.checked_candidate_output(0, bad, binding, before)

    def test_review_live_flag_never_reaches_devices(self):
        profile = self.root / "review.json"
        profile.write_text(json.dumps(candidate.make_profile()))
        with mock.patch.object(candidate.stock, "open_adapter") as opened, \
                mock.patch.object(candidate, "Video") as video, \
                mock.patch.object(candidate.stock, "private_credentials") as credentials:
            with self.assertRaises(ValueError):
                candidate.main(["--live", "--profile", str(profile)])
            opened.assert_not_called()
            video.assert_not_called()
            credentials.assert_not_called()

    def test_saved_logger_fixture_uses_exact_corrected_stock_gate(self):
        self.assertIs(candidate.BootGate, candidate.stock.BootGate)
        self.assertIs(candidate.Video, candidate.stock.Video)
        fixture = (candidate.ROOT / "experiments/stock-warm-start/fixtures/logger-boot.txt").read_bytes()
        gate = candidate.BootGate()
        events = []
        for offset in range(0, len(fixture), 7):
            event = gate.feed(fixture[offset:offset + 7])
            if event:
                events.append(event)
        self.assertTrue(gate.kernel_seen)
        self.assertEqual(events, ["login"])
        self.assertEqual(gate.feed(b"\r\nPassword: "), "password")
        self.assertEqual(gate.feed(b"\r\n/tmp/root # "), "shell")
        with self.assertRaises(RuntimeError):
            gate.feed(b"\r\nLinux version 3.0.35 (second synthetic kernel)\n")

    def fake_run(self, before_bytes=None, after_bytes=None):
        self.fixture()
        binding = self.binding()
        clock = types.SimpleNamespace(now=0.0)
        def monotonic():
            clock.now += .001
            return clock.now
        fake_time = types.SimpleNamespace(monotonic=monotonic)
        sent, starts = [], []
        parent = self
        class Port:
            def close(self):
                pass
        class Session:
            def __init__(self, port, bundle, **kw):
                self.bundle, self.timeout, self.identity = bundle, 20, None
                self.checks = 0
                self.initial = True
            def observe_prompt(self, **kw):
                pass
            def identify(self):
                self.identity = dict(uid=0, user="root", firmware="55.00.750B", flavor="cmu150_NA")
                self.bundle.meta["identity"] = self.identity
            def execute(self, command):
                parent.assertEqual(command, candidate.stock.CHECK)
                self.checks += 1
                return 0, ((before_bytes or source_output()) if self.checks == 1 else
                           (after_bytes or source_output(cid=CID,
                                                        boot=NEW_BOOT, uptime=8)))
            def _send(self, data, received, on_rx=None, **kw):
                sent.append(data)
                if data == b"root\r":
                    on_rx(b"\r\nPassword: ")
                elif data == b"synthetic-only\r":
                    on_rx(b"\r\n/tmp/root # ")
            def _read(self, received, until):
                if self.initial:
                    self.initial = False
                    return (candidate.ROOT / "experiments/stock-warm-start/fixtures/logger-boot.txt").read_bytes()
                clock.now = until
                return b""
        class Video:
            def __init__(self, bundle, index):
                pass
            def start(self):
                starts.append(1)
            def stop(self):
                pass
        args = types.SimpleNamespace(credentials=self.root / "not-a-real-credential",
            bundle=self.root / "synthetic-observer", owner="synthetic-offline-test",
            camera_index=0, solicit_prompt=True)
        with mock.patch.object(candidate, "time", fake_time), \
                mock.patch.object(candidate.stock, "AdapterLock", return_value=nullcontext()), \
                mock.patch.object(candidate.stock, "open_adapter", return_value=Port()) as opened, \
                mock.patch.object(candidate.stock, "Session", Session), \
                mock.patch.object(candidate.stock, "private_credentials",
                                  return_value=(b"root\r", b"synthetic-only\r")), \
                mock.patch.object(candidate, "Video", Video), redirect_stdout(io.StringIO()) as printed:
            rc = candidate.observe(args, {"synthetic_test_only": True}, binding)
        manifest = json.loads((args.bundle / "manifest.json").read_text())
        return rc, manifest, sent, starts, printed.getvalue(), args.bundle

    def test_fake_end_to_end_success_labels_candidate_C(self):
        rc, manifest, sent, starts, printed, bundle = self.fake_run()
        self.assertEqual(rc, 0)
        self.assertEqual(manifest["outcome"], candidate.SUCCESS)
        self.assertEqual(sent, [candidate.stock.REBOOT, b"root\r", b"synthetic-only\r"])
        self.assertEqual(json.loads(printed)["post_source_kind"], "C")
        after = json.loads((bundle / "after.json").read_text())
        self.assertEqual(after["source_kind"], "C")
        events = [json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()]
        verified = [x for x in events if x["kind"] == "post_restart_verified"]
        self.assertTrue(verified[0]["source_C"])
        self.assertNotIn("source_O", verified[0])

    def test_fake_wrong_C_preflight_stops_before_camera_and_request(self):
        raw = source_output(cid=CID.replace(":20001:", ":20002:"))
        rc, manifest, sent, starts, printed, _ = self.fake_run(before_bytes=raw)
        self.assertEqual((rc, manifest["outcome"], sent, starts), (2, "failed_before_request", [], []))
        self.assertIsNone(json.loads(printed)["post_source_kind"])

    def test_fake_O_after_boot_is_unknown_without_C_success_label(self):
        raw = source_output(cid="64785:9457:1433953097:94058:755:1018:3015:1",
                            md5="584c67f7186ada6bae9aae1be59b5cd0", crc="376717896 94058",
                            boot=NEW_BOOT, uptime=8)
        rc, manifest, sent, starts, printed, _ = self.fake_run(after_bytes=raw)
        self.assertEqual((rc, manifest["outcome"]), (2, "unknown_after_request"))
        self.assertEqual(sent.count(candidate.stock.REBOOT), 1)
        self.assertIsNone(json.loads(printed)["post_source_kind"])


    def test_every_changed_full_C_identity_is_conflict_OTHER_without_adoption(self):
        self.fixture()
        binding = self.binding()
        before = candidate.checked_candidate_output(0, source_output(), binding)
        changes = {0: "64786", 1: "20009", 2: "9877", 3: "94058",
                   4: "644", 5: "0", 6: "0", 7: "2"}
        for field, value in changes.items():
            parts = CID.split(":")
            parts[field] = value
            actual = ":".join(parts)
            with self.subTest(field=field):
                with self.assertRaises(candidate.RecoveryIdentityConflict) as raised:
                    candidate.checked_candidate_output(0, source_output(cid=actual, boot=NEW_BOOT, uptime=8),
                                                       binding, before)
                observation = raised.exception.observation
                self.assertEqual(observation["META"], actual)
                self.assertEqual(observation["source_bytes_kind"], "C")
                self.assertEqual(observation["source_kind"], "OTHER")
                self.assertFalse(observation["restore_ready"])
                self.assertFalse(observation["automatic_adoption"])
                self.assertEqual(binding["source_identity"], CID)

    def test_fake_changed_postboot_CID_preserves_conflict_and_never_reports_C_success(self):
        raw = source_output(cid=CID.replace(":20001:", ":20009:"), boot=NEW_BOOT, uptime=8)
        rc, manifest, sent, starts, printed, bundle = self.fake_run(after_bytes=raw)
        self.assertEqual((rc, manifest["outcome"]), (2, candidate.CONFLICT))
        self.assertEqual(sent.count(candidate.stock.REBOOT), 1)
        self.assertIsNone(json.loads(printed)["post_source_kind"])
        self.assertEqual(manifest["recovery_classification"], "OTHER")
        self.assertFalse(manifest["restore_ready"])
        observed = json.loads((bundle / "after-conflict.json").read_text())
        self.assertIn(":20009:", observed["META"])
        self.assertFalse((bundle / "after.json").exists())
        self.assertEqual(observed["applied_source_identity"], CID)


if __name__ == "__main__":
    unittest.main()
