"""Paced TX contract tests: no physical devices, protocol bytes unchanged."""

import collections
import contextlib
import io
import json
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_cli import LockStub, cli

from open_connect.session import TX_GAP_SECONDS, Bundle, Session, UnknownOutcome


class StreamingTransport:
    def __init__(self, max_write=64, noise=None, interrupt_at=None):
        self.tx = bytearray()
        self.rx = collections.deque()
        self.started = False
        self.max_write = max_write
        self.noise = noise
        self.interrupt_at = interrupt_at
        self.timeout = 0.01
        self.write_timeout = 1
        self.closed = False
        self.write_sizes = []

    def write(self, data):
        self.write_sizes.append(len(data))
        if self.interrupt_at is not None and len(self.tx) >= self.interrupt_at:
            raise KeyboardInterrupt()
        n = min(len(data), self.max_write)
        if self.interrupt_at is not None:
            n = min(n, self.interrupt_at - len(self.tx))
        self.tx.extend(data[:n])
        match = re.search(rb" ([a-f0-9]{32}); sh -c", self.tx)
        if match and not self.started:
            self.started = True
            self.token = match.group(1)
            if self.noise is not None:
                self.rx.append(self.noise)
            else:
                record = b"\r\nCMU1 " + self.token + b" BEGIN\r\n"
                self.rx.extend([record[:13], record[13:27], record[27:], b"early\x00\xff\r\n"])
        if self.tx.endswith(b"\r") and self.started:
            self.rx.append(b"\r\nCMU1 " + self.token + b" END 7\r\n/tmp/root # ")
        return n

    def read(self, n):
        if self.rx:
            return self.rx.popleft()
        time.sleep(min(self.timeout, 0.001))
        return b""

    def close(self):
        self.closed = True


class PacedTxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.bundle = Bundle(self.folder / "bundle", "offline paced TX", "unittest")

    def tearDown(self):
        self.bundle.finish("offline test finished")
        self.temp.cleanup()

    def session(self, port, timeout=0.6, cap=1048576):
        s = Session(port, self.bundle, timeout=timeout, output_cap=cap)
        s.state = "shell"
        s.identity = {"uid": 0}
        return s

    def test_rx_frames_and_binary_output_arriving_during_tx_reach_same_decoder(self):
        port = StreamingTransport()
        s = self.session(port)
        status, output = s.execute("printf " + ("x" * 250))
        self.assertEqual(status, 7)
        self.assertIn(b"early\x00\xff", output)
        self.assertLessEqual(max(port.write_sizes), 64)
        rows = [
            json.loads(line)
            for line in (self.bundle.path / "events.jsonl").read_text().splitlines()
        ]
        first_rx = next(i for i, e in enumerate(rows) if e.get("direction") == "rx")
        last_tx = max(i for i, e in enumerate(rows) if e.get("direction") == "tx")
        self.assertLess(first_rx, last_tx)
        for direction in ("rx", "tx"):
            reconstructed = b"".join(
                bytes.fromhex(e["hex"]) for e in rows if e.get("direction") == direction
            )
            self.assertEqual(reconstructed, (self.bundle.path / (direction + ".bin")).read_bytes())
        gaps = [e for e in rows if e["kind"] == "tx_gap"]
        self.assertTrue(any(e["rx_bytes"] for e in gaps))
        self.assertTrue(all(e["requested_seconds"] == TX_GAP_SECONDS for e in gaps))

    def test_partial_writes_finish_chunk_without_per_partial_gap_penalty(self):
        port = StreamingTransport(max_write=3)
        s = self.session(port, timeout=0.5)
        status, _ = s.execute("printf " + ("x" * 220))
        self.assertEqual(status, 7)
        request = self.bundle.meta["transmissions"][-1]
        self.assertEqual(request["gaps"], request["completed_chunks"] - 1)
        self.assertGreater(request["write_calls"], request["completed_chunks"] * 3)
        self.assertEqual((self.bundle.path / "tx.bin").read_bytes(), bytes(port.tx))
        self.assertEqual(request["acknowledged_bytes"], len(port.tx))

    def test_operation_deadline_applies_during_paced_tx_without_retry(self):
        port = StreamingTransport()
        s = self.session(port, timeout=0.035)
        with self.assertRaises(UnknownOutcome):
            s.execute("printf " + ("x" * 300) + "\n: " + (" " * 180))
        sent = bytes(port.tx)
        self.assertGreater(len(sent), 0)
        self.assertFalse(sent.endswith(b"\r"))
        self.assertEqual(s.state, "uncertain")
        with self.assertRaises(UnknownOutcome):
            s.execute("true")
        self.assertEqual(bytes(port.tx), sent)
        self.assertEqual(self.bundle.meta["operations"][-1]["outcome"], "unknown")
        self.assertEqual(self.bundle.meta["transmissions"][-1]["outcome"], "unknown")

    def test_submission_longer_than_one_second_is_allowed_within_total_deadline(self):
        port = StreamingTransport()
        s = self.session(port, timeout=2.5)
        started = time.monotonic()
        status, _ = s.execute(":\n" + (":" + (" " * 90) + "\n") * 38)
        self.assertEqual(status, 7)
        self.assertGreater(time.monotonic() - started, 1.0)
        self.assertTrue(port.tx.endswith(b"\r"))
        self.assertEqual(self.bundle.meta["transmissions"][-1]["outcome"], "acknowledged_by_host")

    def test_rx_cap_during_tx_stops_further_tx_preserves_all_received_bytes(self):
        noise = b"z" * 100
        port = StreamingTransport(noise=noise)
        s = self.session(port, cap=50)
        with self.assertRaises(UnknownOutcome):
            s.execute("printf " + ("x" * 400))
        self.assertEqual((self.bundle.path / "rx.bin").read_bytes(), noise)
        self.assertFalse(port.tx.endswith(b"\r"))
        self.assertEqual(s.state, "uncertain")
        self.assertLess(len(port.tx), 200)

    def test_cli_cancellation_after_paced_chunk_preserves_unknown_and_closes(self):
        port = StreamingTransport(interrupt_at=70)
        # Fresh initial prompt lets CLI enter its real identity transaction.
        port.rx.append(b"/tmp/root # ")
        path = self.folder / "cli-cancel"
        with (
            patch.object(cli, "AdapterLock", return_value=LockStub()),
            patch.object(cli, "open_adapter", return_value=port),
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                rc = cli.main(
                    [
                        "--live",
                        "--action",
                        "command",
                        "--command",
                        "id",
                        "--bundle",
                        str(path),
                        "--deadline",
                        "0.5",
                    ]
                )
        m = json.loads((path / "manifest.json").read_text())
        self.assertEqual(rc, 2)
        self.assertEqual(m["outcome"], "unknown")
        self.assertEqual(m["operations"][0]["outcome"], "unknown")
        self.assertTrue(port.closed)
        self.assertEqual(len(port.tx), 70)
        self.assertEqual((path / "tx.bin").read_bytes(), bytes(port.tx))

    def test_cli_rx_cap_during_tx_keeps_unknown_and_closes(self):
        port = StreamingTransport(noise=b"z" * 100)
        port.rx.append(b"/tmp/root # ")
        path = self.folder / "cli-cap"
        with (
            patch.object(cli, "AdapterLock", return_value=LockStub()),
            patch.object(cli, "open_adapter", return_value=port),
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                rc = cli.main(
                    [
                        "--live",
                        "--action",
                        "command",
                        "--command",
                        "id",
                        "--bundle",
                        str(path),
                        "--deadline",
                        "0.5",
                        "--output-cap",
                        "50",
                    ]
                )
        m = json.loads((path / "manifest.json").read_text())
        self.assertEqual(rc, 2)
        self.assertEqual(m["outcome"], "unknown")
        self.assertTrue(port.closed)
        self.assertEqual((path / "rx.bin").read_bytes(), b"/tmp/root # " + b"z" * 100)
        self.assertLess(len(port.tx), 335)


if __name__ == "__main__":
    unittest.main()
