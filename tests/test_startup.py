"""Startup record parsing is pure and independent of historical live profiles."""

import unittest

from open_connect.startup import persistence_fields

RECORDS = (
    b"SWST|META|64785:123:1:94058:755:1018:3015:1\n"
    b"SWST|HASH|0123456789abcdef0123456789abcdef  -\n"
    b"SWST|CRC|123 94058\n"
    b"SWST|ROOT|/dev/ffx01p1 / relfs ro,noatime 0 0\n"
    b"SWST|UPTIME|10.25 20.5\n"
    b"SWST|BOOT_ID|11111111-1111-1111-1111-111111111111\n"
)


class StartupRecords(unittest.TestCase):
    def test_logger_prefix_and_crlf(self):
        fields = persistence_fields(b"logger-prefix" + RECORDS.replace(b"\n", b"\r\n"))
        self.assertEqual(fields["META"], "64785:123:1:94058:755:1018:3015:1")
        self.assertEqual(fields["UPTIME"], "10.25 20.5")

    def test_invalid_records_refused(self):
        cases = {
            "duplicate": RECORDS + RECORDS.splitlines(keepends=True)[0],
            "unterminated": RECORDS[:-1],
            "missing": b"\n".join(RECORDS.split(b"\n")[1:]),
            "partial": RECORDS.replace(b"64785:123:1:94058:755:1018:3015:1", b"64785:123"),
            "unknown": RECORDS.replace(b"|META|", b"|OTHER|"),
            "interleaved": RECORDS.replace(b"SWST|META|", b"SWST|SWST|META|"),
            "quoted": RECORDS.replace(b"SWST|CRC|123 94058", b'SWST|CRC|123 94058"'),
        }
        for name, data in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                persistence_fields(data)


if __name__ == "__main__":
    unittest.main()
