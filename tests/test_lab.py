"""Static topology/config tests and FRR JSON parser unit tests.

These tests do NOT claim to test real BGP peering: Docker integration is separate.
"""
import ipaddress
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import labctl  # noqa: E402

ROLES = {
    "edge": (65010, "10.10.10.1/32", ("10.255.10.3", "10.255.20.3")),
    "transit_primary": (65020, None, ("10.255.10.2", "10.255.30.3")),
    "transit_backup": (65030, None, ("10.255.20.2", "10.255.40.3")),
    "core": (65040, "10.40.40.1/32", ("10.255.30.2", "10.255.40.2")),
}


def cfg(role):
    return (ROOT / "configs" / role / "frr.conf").read_text(encoding="utf-8")


class TestConfigFiles(unittest.TestCase):
    def test_frr_and_daemon_files_exist_for_all_routers(self):
        for role in ROLES:
            with self.subTest(role=role):
                for filename in ("frr.conf", "daemons", "vtysh.conf"):
                    self.assertTrue((ROOT / "configs" / role / filename).is_file())

    def test_router_asns_and_neighbors(self):
        for role, (asn, _, neighbors) in ROLES.items():
            with self.subTest(role=role):
                data = cfg(role)
                self.assertIn(f"router bgp {asn}", data)
                self.assertEqual(data.count(" remote-as "), 2)
                for neighbor in neighbors:
                    self.assertIn(f"neighbor {neighbor} remote-as ", data)
                    self.assertIn(f"neighbor {neighbor} activate", data)
                    self.assertIn(f"neighbor {neighbor} route-map ", data)
                    self.assertIn(f"neighbor {neighbor} timers 3 9", data)

    def test_explicit_import_and_export_policies(self):
        for role, (_, _, neighbors) in ROLES.items():
            with self.subTest(role=role):
                data = cfg(role)
                self.assertNotIn("no bgp ebgp-requires-policy", data)
                for neighbor in neighbors:
                    self.assertRegex(data, rf"neighbor {neighbor.replace('.', '[.]')} route-map [A-Z-]+ in")
                    self.assertRegex(data, rf"neighbor {neighbor.replace('.', '[.]')} route-map [A-Z-]+ out")

    def test_no_catch_all_prefix_policy(self):
        for role in ROLES:
            with self.subTest(role=role):
                data = cfg(role)
                self.assertNotIn("0.0.0.0/0 le 32", data)
                self.assertNotIn("0.0.0.0/0 ge 0", data)
                self.assertNotIn("route-map ONLY-CORE permit 20", data)
                self.assertNotIn("route-map ONLY-EDGE permit 20", data)

    def test_service_prefixes_only_originated_at_edge_or_core(self):
        for role, (_, source, _) in ROLES.items():
            with self.subTest(role=role):
                data = cfg(role)
                originated = [line.strip().split(" ", 1)[1] for line in data.splitlines()
                              if line.strip().startswith("network ")]
                self.assertEqual(originated, [source] if source else [])
                if source:
                    self.assertIn(f"ip address {source}", data)

    def test_prefer_primary_on_both_ends(self):
        for role in ("edge", "core"):
            data = cfg(role)
            self.assertEqual(data.count("set local-preference 200"), 1)
            self.assertEqual(data.count("set local-preference 100"), 1)

    def test_daemons_enabled_with_minimum_protocols(self):
        for role in ROLES:
            data = (ROOT / "configs" / role / "daemons").read_text()
            self.assertIn("zebra=yes", data)
            self.assertIn("bgpd=yes", data)
            self.assertIn("ospfd=no", data)

    def test_no_host_network_or_privileged_container(self):
        data = (ROOT / "compose.yaml").read_text()
        self.assertNotIn("privileged:", data)
        self.assertNotIn("network_mode: host", data)
        self.assertNotIn("ports:", data)
        self.assertNotIn("internal: true", data)
        self.assertEqual(data.count('enable_ip_masquerade: "false"'), 4)
        self.assertEqual(data.count("driver: bridge"), 4)
        self.assertIn("quay.io/frrouting/frr:10.7.1", data)
        self.assertIn("net.ipv4.ip_forward: \"1\"", data)

    def test_network_subnets_non_overlapping(self):
        data = (ROOT / "compose.yaml").read_text()
        import re
        nets = [ipaddress.ip_network(x) for x in re.findall(r"subnet:\s+([0-9./]+)", data)]
        self.assertEqual(len(nets), 4)
        for idx, subnet in enumerate(nets):
            self.assertEqual(subnet.prefixlen, 29)
            for other in nets[idx + 1:]:
                self.assertFalse(subnet.overlaps(other))

    def test_all_network_endpoints_have_unique_ips(self):
        import re
        from collections import Counter
        compose = (ROOT / "compose.yaml").read_text()
        addresses = re.findall(r"ipv4_address:\s+([0-9.]+)", compose)
        self.assertEqual(len(addresses), 8)
        self.assertTrue(all(count == 1 for count in Counter(addresses).values()))
        for addr in addresses:
            self.assertTrue(ipaddress.ip_address(addr).is_private)

    def test_no_public_network_prefix_advertisement(self):
        for role in ROLES:
            data = cfg(role)
            announced = [line.split()[-1] for line in data.splitlines()
                         if line.lstrip().startswith("network ")]
            for prefix in announced:
                self.assertTrue(ipaddress.ip_network(prefix).is_private)

    def test_real_loopback_probes_configured_both_directions(self):
        script = (ROOT / "scripts" / "labctl.py").read_text()
        self.assertIn('"-I", "10.10.10.1", "10.40.40.1"', script)
        self.assertIn('"-I", "10.40.40.1", "10.10.10.1"', script)

    def test_integration_ci_is_triggered_for_push_and_manual_review(self):
        workflow = (ROOT / ".github" / "workflows" / "integration.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("  push:", workflow)
        self.assertIn("    branches: [main]", workflow)
        self.assertIn("failover --timeout", workflow)
        self.assertIn("filter --timeout", workflow)
        self.assertIn("if: always()", workflow)

    def test_service_names_match_controller(self):
        import re
        data = (ROOT / "compose.yaml").read_text()
        for role in labctl.SERVICES:
            self.assertRegex(data, rf"(?m)^  {role}:$")


class TestBGPParsers(unittest.TestCase):
    def test_direct_prefix_json(self):
        data = {
            "prefix": labctl.TARGET,
            "paths": [
                {"bestpath": {"overall": False}, "nexthops": [{"ip": labctl.BACKUP_NH}]},
                {"bestpath": {"overall": True}, "nexthops": [{"ip": labctl.PRIMARY_NH}]},
            ],
        }
        self.assertEqual(labctl.best_nexthop(data, labctl.TARGET), labctl.PRIMARY_NH)

    def test_routes_mapping_json(self):
        data = {"routes": {labctl.TARGET: [{"bestpath": {"overall": True},
                                            "nexthops": [{"ip": labctl.BACKUP_NH}]}]}}
        self.assertEqual(labctl.best_nexthop(data, labctl.TARGET), labctl.BACKUP_NH)

    def test_no_route_no_nexthop(self):
        self.assertIsNone(labctl.best_nexthop({}, labctl.TARGET))

    def test_single_valid_path(self):
        data = {"paths": [{"valid": True, "nexthops": [{"ip": "1.2.3.4"}]}]}
        self.assertEqual(labctl.best_nexthop(data, labctl.TARGET), "1.2.3.4")

    def test_summary_parser_nested(self):
        data = {"ipv4Unicast": {"peers": {"10.0.0.1": {"state": "Established", "pfxRcd": 1}}}}
        self.assertTrue(labctl.established(labctl.all_peers(data)["10.0.0.1"]))

    def test_summary_parser_rejects_idle(self):
        self.assertFalse(labctl.established({"state": "Idle"}))

    def test_json_payloads_from_fixture(self):
        fixture = json.loads((ROOT / "tests" / "fixtures" / "route-primary.json").read_text())
        self.assertEqual(labctl.best_nexthop(fixture, labctl.TARGET), labctl.PRIMARY_NH)

    def test_expected_neighbor_symmetry(self):
        neighbors = labctl.expected_peers()
        self.assertEqual([len(val) for val in neighbors.values()], [2, 2, 2, 2])
        self.assertEqual(len(set.union(*neighbors.values())), 8)




class TestDiagnostics(unittest.TestCase):
    def test_diagnostic_subcommand_registered(self):
        script = (ROOT / "scripts" / "labctl.py").read_text()
        self.assertIn('"diagnose"', script)
        self.assertIn('def diagnose_command()', script)

    def test_probe_captures_command_failures(self):
        from unittest.mock import patch
        with patch.object(labctl, 'inside', side_effect=labctl.LabError('packet loss')):
            result = labctl.probe('edge', 'ping', '10.40.40.1')
        self.assertFalse(result['ok'])
        self.assertIn('packet loss', result['output'])



class TestEvidenceBundling(unittest.TestCase):
    def test_bundle_contains_unmodified_evidence_and_manifest(self):
        """Archive must preserve raw JSON bytes with both Unix and Windows newlines."""
        import tempfile
        import zipfile
        import hashlib
        from unittest.mock import patch

        for newline in (b"\n", b"\r\n"):
            with self.subTest(newline=newline):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    evidence_dir = root / "artifacts"
                    evidence_dir.mkdir()
                    filename = "baseline-20261027T153254Z.json"
                    # Write bytes explicitly: Path.write_text normalizes LF to CRLF
                    # on Windows, which made this test fail there.
                    data = b'{"status":"PASS","observation":"fixture, not field result"}' + newline
                    (evidence_dir / filename).write_bytes(data)
                    with patch.object(labctl, "ROOT", root):
                        archive = labctl.bundle_command()
                    with zipfile.ZipFile(archive) as zf:
                        self.assertEqual(zf.read(filename), data)
                        manifest = json.loads(zf.read("evidence-manifest.json"))
                        self.assertEqual(manifest["files"][0]["filename"], filename)
                        self.assertEqual(manifest["files"][0]["bytes"], len(data))
                        self.assertEqual(manifest["files"][0]["sha256"], hashlib.sha256(data).hexdigest())

    def test_bundle_errors_without_local_evidence(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(labctl, "ROOT", Path(tmp)):
                with self.assertRaises(labctl.LabError):
                    labctl.bundle_command()

    def test_bundle_errors_on_invalid_json(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "artifacts"
            folder.mkdir()
            (folder / "corrupted.json").write_text('{oops', encoding="utf-8")
            with patch.object(labctl, "ROOT", Path(tmp)):
                with self.assertRaises(labctl.LabError):
                    labctl.bundle_command()

if __name__ == "__main__":
    unittest.main()
