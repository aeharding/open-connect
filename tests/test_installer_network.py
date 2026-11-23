"""Equivalent WCP firewall commit and OEM fallback before network side effects."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ASSET = Path(__file__).resolve().parents[1] / "cmu/installer/network.sh"


class InstallerNetwork(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls"
        self.modules = self.root / "modules"
        self.modules.write_text("")
        self.ready = self.root / "ready"
        stub = self.bin / "command"
        stub.write_text(
            '#!/bin/sh\nname=${0##*/}\nprintf "%s %s\\n" "$name" "$*" >> "$CALLS"\n'
            'if test "$name" = restore; then cat > "$RULES"; fi\n'
            'test "$name" != "${FAIL_COMMAND:-}"\n'
        )
        stub.chmod(0o700)
        for name in ("insmod", "ifplugd", "restore", "oem", "dhcp", "sshd"):
            (self.bin / name).symlink_to(stub.name)
        source = ASSET.read_text().replace(
            "PATH=/sbin:/usr/sbin:/bin:/usr/bin", f"PATH={self.bin}:/usr/bin:/bin"
        )
        for original, replacement in {
            "/proc/modules": self.modules,
            "/data/integration/developer_mode_on_flag": self.root / "developer",
            "/data/integration/eth0_on_flag": self.root / "eth0",
            "/usr/sbin/iptables-restore": self.bin / "restore",
            "/jci/scripts/start_network.sh": self.bin / "oem",
            "/jci/scripts/start_eth1_dhcp.sh": self.bin / "dhcp",
            "/usr/sbin/sshd": self.bin / "sshd",
            "/var/run/start_network_ready": self.ready,
        }.items():
            source = source.replace(original, str(replacement))
        self.script = self.root / "network.sh"
        self.script.write_text(source)

    def invoke(self, *args, failure=""):
        result = subprocess.run(
            ["sh", self.script, *args],
            env={
                **os.environ,
                "CALLS": str(self.log),
                "RULES": str(self.root / "rules"),
                "FAIL_COMMAND": failure,
            },
            capture_output=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.output = result.stdout
        return self.log.read_text().splitlines()

    def test_commit_precedes_interfaces_daemons_and_ready(self):
        (self.root / "eth0").touch()
        calls = self.invoke()
        restore = calls.index("restore ")
        self.assertEqual(sum(line.startswith("restore ") for line in calls), 1)
        self.assertEqual(sum(line.startswith("insmod ") for line in calls[:restore]), 11)
        self.assertTrue(any("xt_hashlimit.ko" in line for line in calls[:restore]))
        self.assertTrue(any("ipt_REJECT.ko" in line for line in calls[:restore]))
        self.assertTrue(all("drivers/net/" not in line for line in calls[:restore]))
        self.assertIn("ifplugd -M -I -i eth0", calls[restore + 1 :])
        self.assertIn("dhcp ", calls[restore + 1 :])
        self.assertIn("sshd ", calls[restore + 1 :])
        self.assertTrue(self.ready.exists())
        self.assertIn(b"atomic WCP firewall committed", self.output)
        self.assertFalse(any(line.startswith("oem ") for line in calls))
        rules = (self.root / "rules").read_text()
        self.assertTrue(
            rules.startswith(
                "*filter\n:INPUT DROP [0:0]\n:FORWARD DROP [0:0]\n:OUTPUT ACCEPT [0:0]\n"
            )
        )
        self.assertTrue(rules.endswith("COMMIT\n"))
        self.assertEqual(sum(line.startswith("-A wcp_packets ") for line in rules.splitlines()), 7)
        self.assertEqual(sum(line.startswith("-A INPUT ") for line in rules.splitlines()), 10)
        # Native wcpset owns insertion at INPUT position 3 after association.
        self.assertNotIn("-j wcp_packets", rules)
        self.assertIn("--hashlimit 1667/sec", rules)
        self.assertLess(
            rules.index("--dport 36000 -m state --state NEW,ESTABLISHED -j DROP"),
            rules.index("--dport 36000 -m state --state NEW,ESTABLISHED -j ACCEPT"),
        )

    def test_loaded_modules_skip_duplicate_insmod(self):
        names = "x_tables ip_tables iptable_filter nf_conntrack xt_state nf_defrag_ipv4 nf_conntrack_ipv4 xt_tcpudp xt_limit xt_hashlimit ipt_REJECT".split()
        self.modules.write_text("".join(f"{name} 1 0 - Live 0\n" for name in names))
        calls = self.invoke()
        self.assertEqual(calls[0], "restore ")
        self.assertEqual(sum(line.startswith("insmod ") for line in calls), 2)

    def test_preload_or_commit_failure_execs_oem_before_network(self):
        for failure in ("insmod", "restore"):
            with self.subTest(failure=failure):
                self.log.unlink(missing_ok=True)
                calls = self.invoke(failure=failure)
                self.assertEqual(calls[-1], "oem ")
                self.assertNotIn(b"atomic WCP firewall committed", self.output)
                self.assertFalse(self.ready.exists())
                self.assertFalse(
                    any(line.startswith(("dhcp ", "sshd ", "ifplugd ")) for line in calls)
                )
                self.assertFalse(any("drivers/net/" in line for line in calls))

    def test_developer_and_ucp_use_unchanged_oem_entry(self):
        self.assertEqual(self.invoke("UCP"), ["oem UCP"])
        self.log.unlink()
        (self.root / "developer").touch()
        self.assertEqual(self.invoke(), ["oem "])
        self.assertFalse(self.ready.exists())
