"""Synthetic fixtures only: offline evidence-verifier tests, not live BGP tests."""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_evidence as ve  # noqa: E402


def synthetic_documents():
    """Minimal imaginary mock data for structural validation; NOT measured data."""
    routers = {}
    for node, (asn, ips) in ve.NODES.items():
        paths = {}
        fib = {}
        if node in ve.PRIMARY:
            dest, primary, backup = ve.PRIMARY[node]
            paths[dest] = [
                {"bestpath": True, "locPrf": 200, "nexthops": [{"ip": primary}]},
                {"locPrf": 100, "nexthops": [{"ip": backup}]},
            ]
            fib[dest] = [{"protocol": "bgp", "selected": True, "installed": True,
                          "nexthops": [{"ip": primary}]}]
        routers[node] = {
            "show bgp ipv4 unicast summary json": json.dumps({
                "as": asn, "peers": {ip: {"state": "Established"} for ip in ips}}),
            "show bgp ipv4 unicast json": json.dumps({"routes": paths}),
            "show ip route json": json.dumps(fib),
            "show version": "FRRouting 10.7.1_git on Linux",
        }
    return {
        "baseline": {"experiment": "baseline", "status": "PASS",
                     "edge_core_best_nexthop": "10.255.10.3",
                     "core_edge_best_nexthop": "10.255.30.2", "elapsed_check_seconds": 3.5},
        "failover": {"experiment": "primary_transit_container_stop", "backup_path_observed": True,
                     "failure_detail": None, "observed_failover_seconds": 0.5,
                     "poll_interval_seconds": 0.5, "start_to_end_seconds": 12},
        "filter": {"experiment": "unauthorized_prefix_injection", "status": "PASS",
                   "origin": "transit_primary", "prefix": "198.18.0.1/32",
                   "received_by_edge": False, "received_by_core": False, "observation_seconds": 5.5},
        "snapshot": {"observed_at_utc": "synthetic", "routers": routers},
    }


class TestOfflineVerifier(unittest.TestCase):
    def test_synthetic_good_case(self):
        result = ve.verify_documents(synthetic_documents(), {})
        self.assertEqual(result["verification"], "PASS")
        self.assertEqual(result["snapshotted_bgp_peer_perspectives_established"], 8)

    def test_rejects_peer_down(self):
        docs = synthetic_documents()
        snapshot = docs["snapshot"]["routers"]["core"]
        info = json.loads(snapshot["show bgp ipv4 unicast summary json"])
        info["peers"]["10.255.30.2"]["state"] = "Idle"
        snapshot["show bgp ipv4 unicast summary json"] = json.dumps(info)
        with self.assertRaisesRegex(ve.EvidenceError, "not Established"):
            ve.verify_documents(docs, {})

    def test_rejects_wrong_local_preference(self):
        docs = synthetic_documents()
        edge = docs["snapshot"]["routers"]["edge"]
        info = json.loads(edge["show bgp ipv4 unicast json"])
        info["routes"]["10.40.40.1/32"][0]["locPrf"] = 100
        edge["show bgp ipv4 unicast json"] = json.dumps(info)
        with self.assertRaisesRegex(ve.EvidenceError, "local-preference mismatch"):
            ve.verify_documents(docs, {})

    def test_rejects_forbidden_prefix_leak(self):
        docs = synthetic_documents()
        docs["filter"]["received_by_core"] = True
        with self.assertRaisesRegex(ve.EvidenceError, "reached Edge/Core"):
            ve.verify_documents(docs, {})

    def test_zip_reader_accepts_four_flat_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "fixture.zip"
            with zipfile.ZipFile(dest, "w") as arc:
                for name, document in synthetic_documents().items():
                    arc.writestr(f"{name}-fixtureZ.json", json.dumps(document))
            data, hashes = ve.read_evidence_zip(dest)
            self.assertEqual(set(data), set(ve.KINDS))
            self.assertEqual(len(hashes), 4)

    def test_zip_reader_rejects_nested_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "fixture.zip"
            with zipfile.ZipFile(dest, "w") as arc:
                for name, document in synthetic_documents().items():
                    path = f"nested/{name}-fixtureZ.json" if name == "baseline" else f"{name}-fixtureZ.json"
                    arc.writestr(path, json.dumps(document))
            with self.assertRaisesRegex(ve.EvidenceError, "Invalid ZIP member"):
                ve.read_evidence_zip(dest)


if __name__ == "__main__":
    unittest.main()
