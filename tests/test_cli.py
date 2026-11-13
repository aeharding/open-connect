"""Front-door tests patch only hardware acquisition; no production PTY option."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_session import FakeTransport

from open_connect import uart as cli
from open_connect.session import BenchError


class LockStub:
    def __enter__(self):
        return SimpleNamespace(path="synthetic-test-lock")

    def __exit__(self, *_):
        pass


class FailingTransport(FakeTransport):
    def __init__(self, error, partial=False, prompt=True):
        super().__init__([b"/tmp/root # "] if prompt else [])
        self.error = error
        self.partial = partial
        self.closed = False
        self.calls = 0

    def write(self, data):
        self.calls += 1
        if self.partial and self.calls == 1:
            self.tx.extend(data[:3])
            return 3
        raise self.error

    def close(self):
        self.closed = True


class CliTests(unittest.TestCase):
    def invoke(self, path, port=None, open_error=None, lock_error=None, extra=()):
        with patch.object(cli, "AdapterLock") as lock, patch.object(cli, "open_adapter") as opener:
            lock.return_value = LockStub()
            if lock_error:
                # Class-level mock context handles enter failure explicitly.
                lock.return_value = unittest.mock.MagicMock()
                lock.return_value.__enter__.side_effect = lock_error
            if open_error:
                opener.side_effect = open_error
            else:
                opener.return_value = port
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
                        "--owner",
                        "synthetic CLI test",
                        "--deadline",
                        "0.04",
                        *extra,
                    ]
                )
            return rc, json.loads((path / "manifest.json").read_text()), opener.call_count

    def test_failed_open_is_requested_not_observed_hardware(self):
        with tempfile.TemporaryDirectory() as temp:
            rc, manifest, _ = self.invoke(
                Path(temp) / "run", open_error=BenchError("synthetic open refused")
            )
            self.assertEqual(rc, 1)
            self.assertEqual(manifest["outcome"], "failed")
            self.assertTrue(manifest["live_requested"])
            self.assertFalse(manifest["adapter_observed"])
            self.assertFalse(manifest["serial_port_opened"])

    def test_failed_lock_never_opens_and_never_claims_hardware(self):
        with tempfile.TemporaryDirectory() as temp:
            rc, manifest, calls = self.invoke(
                Path(temp) / "run", lock_error=BlockingIOError("busy test lock")
            )
            self.assertEqual(rc, 1)
            self.assertEqual(calls, 0)
            self.assertFalse(manifest["adapter_observed"])
            self.assertFalse(manifest["serial_port_opened"])

    def test_partial_tx_error_top_level_unknown_and_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "run"
            port = FailingTransport(OSError("synthetic partial write error"), partial=True)
            rc, manifest, _ = self.invoke(path, port)
            self.assertEqual(rc, 2)
            self.assertEqual(manifest["outcome"], "unknown")
            self.assertEqual(manifest["operations"][0]["outcome"], "unknown")
            self.assertEqual((path / "tx.bin").read_bytes(), bytes(port.tx))
            self.assertEqual(len(port.tx), 3)
            self.assertTrue(port.closed)

    def test_keyboard_interrupt_after_tx_keeps_unknown_and_closes(self):
        with tempfile.TemporaryDirectory() as temp:
            port = FailingTransport(KeyboardInterrupt(), partial=True)
            rc, manifest, _ = self.invoke(Path(temp) / "run", port)
            self.assertEqual(rc, 2)
            self.assertEqual(manifest["outcome"], "unknown")
            self.assertEqual(manifest["operations"][0]["outcome"], "unknown")
            self.assertTrue(port.closed)

    def test_system_exit_after_partial_tx_keeps_unknown_and_closes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "run"
            port = FailingTransport(SystemExit(7), partial=True)
            rc, manifest, _ = self.invoke(path, port)
            self.assertEqual(rc, 2)
            self.assertEqual(manifest["outcome"], "unknown")
            self.assertEqual(manifest["operations"][0]["outcome"], "unknown")
            self.assertEqual((path / "tx.bin").read_bytes(), bytes(port.tx))
            self.assertEqual(len(port.tx), 3)
            self.assertTrue(port.closed)

    def test_probe_write_failure_preserves_unknown_without_task(self):
        with tempfile.TemporaryDirectory() as temp:
            port = FailingTransport(OSError("synthetic probe write error"), prompt=False)
            rc, manifest, _ = self.invoke(Path(temp) / "run", port, extra=("--solicit-prompt",))
            self.assertEqual(rc, 2)
            self.assertEqual(manifest["outcome"], "unknown")
            self.assertEqual(manifest["operations"], [])
            self.assertTrue(port.closed)


if __name__ == "__main__":
    unittest.main()
