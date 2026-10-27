#!/usr/bin/env python3
"""Offline validation of a supplied BGP Routing Laboratory runtime-evidence ZIP.

Never starts Docker, changes FRR configuration, or synthesizes measurements.
Produces a machine-readable account of what the evidence does and does not prove.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

NODES = {
    "edge": (65010, ("10.255.10.3", "10.255.20.3")),
    "transit_primary": (65020, ("10.255.10.2", "10.255.30.3")),
    "transit_backup": (65030, ("10.255.20.2", "10.255.40.3")),
    "core": (65040, ("10.255.30.2", "10.255.40.2")),
}
PRIMARY = {
    "edge": ("10.40.40.1/32", "10.255.10.3", "10.255.20.3"),
    "core": ("10.10.10.1/32", "10.255.30.2", "10.255.40.2"),
}
KINDS = ("baseline", "failover", "filter", "snapshot")
FORBIDDEN = "198.18.0.1/32"


class EvidenceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_evidence_zip(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Accept exactly one named JSON per experiment; only flat JSON members.

    Guard extraction-free reading against path traversal and pathological size.
    """
    data: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    with zipfile.ZipFile(path) as arc:
        infos = [i for i in arc.infolist() if not i.is_dir()]
        require(len(infos) == len(KINDS), f"Expected exactly 4 JSON files; got {len(infos)}")
        require(sum(i.file_size for i in infos) <= 2_000_000, "ZIP contents exceed size limit")
        for item in infos:
            require(item.file_size <= 500_000, f"Oversized evidence member: {item.filename}")
            require(item.filename == Path(item.filename).name and item.filename.endswith(".json"),
                    f"Invalid ZIP member path/type: {item.filename}")
            kind = next((k for k in KINDS if item.filename.startswith(k + "-") and
                         item.filename.endswith("Z.json")), None)
            require(kind is not None and kind not in data, f"Unknown/duplicate evidence member: {item.filename}")
            raw = arc.read(item)
            try:
                obj = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise EvidenceError(f"Invalid JSON in {item.filename}: {exc}") from exc
            require(isinstance(obj, dict), f"JSON root must be object: {item.filename}")
            data[kind] = obj
            hashes[item.filename] = sha256(raw)
        require(set(data) == set(KINDS), f"Missing evidence kinds: {set(KINDS) - set(data)}")
    return data, hashes


def parsed_command(router: dict[str, Any], command: str, node: str) -> dict[str, Any]:
    value = router.get(command)
    require(isinstance(value, str), f"{node}: command missing/string output expected: {command}")
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"{node}: invalid FRR JSON from {command}") from exc
    require(isinstance(data, dict), f"{node}: unexpected JSON root: {command}")
    return data


def selected_hop(route: dict[str, Any]) -> str | None:
    for path in route.get("nexthops", []):
        if isinstance(path, dict) and path.get("ip"):
            return path["ip"]
    return None


def verify_documents(docs: dict[str, dict[str, Any]], hashes: dict[str, str]) -> dict[str, Any]:
    base, fail, filt, snapshot = (docs[k] for k in KINDS)
    require(base.get("experiment") == "baseline" and base.get("status") == "PASS", "Baseline status is not PASS")
    require(base.get("edge_core_best_nexthop") == PRIMARY["edge"][1], "Baseline edge primary hop mismatch")
    require(base.get("core_edge_best_nexthop") == PRIMARY["core"][1], "Baseline core primary hop mismatch")
    require(isinstance(base.get("elapsed_check_seconds"), (int, float)) and
            0 < base["elapsed_check_seconds"] < 3600, "Baseline check duration missing/out of range")

    require(fail.get("experiment") == "primary_transit_container_stop", "Unknown failover experiment")
    require(fail.get("backup_path_observed") is True, "Failover backup path not observed")
    require(fail.get("failure_detail") is None, "Failover failure_detail present")
    for k in ("observed_failover_seconds", "start_to_end_seconds", "poll_interval_seconds"):
        require(isinstance(fail.get(k), (int, float)) and 0 < fail[k] < 3600,
                f"Failover observation {k} absent/invalid")
    require(fail["observed_failover_seconds"] <= fail["start_to_end_seconds"],
            "Failover observation longer than full experiment")

    require(filt.get("experiment") == "unauthorized_prefix_injection", "Unknown filter experiment")
    require(filt.get("status") == "PASS", "Filter status not PASS")
    require(filt.get("prefix") == FORBIDDEN and filt.get("origin") == "transit_primary",
            "Unexpected injected prefix/source")
    require(filt.get("received_by_edge") is False and filt.get("received_by_core") is False,
            "Unauthorized prefix reached Edge/Core according to JSON")
    require(isinstance(filt.get("observation_seconds"), (int, float)) and filt["observation_seconds"] > 0,
            "Invalid route filter observation duration")

    nodes = snapshot.get("routers")
    require(isinstance(nodes, dict) and set(nodes) == set(NODES), "Snapshot must include all four router roles")
    peers_verified = 0
    summary_nexthops: dict[str, Any] = {}
    for node, (asn, peer_ips) in NODES.items():
        require(isinstance(nodes[node], dict), f"{node} snapshot data missing")
        summ = parsed_command(nodes[node], "show bgp ipv4 unicast summary json", node)
        require(summ.get("as") == asn, f"{node}: AS mismatch")
        peers = summ.get("peers")
        require(isinstance(peers, dict) and set(peer_ips).issubset(peers), f"{node}: peer list mismatch")
        for ip in peer_ips:
            require(isinstance(peers[ip], dict) and peers[ip].get("state") == "Established",
                    f"{node}: peer {ip} not Established")
            peers_verified += 1
        routes = parsed_command(nodes[node], "show bgp ipv4 unicast json", node)
        route_data = routes.get("routes")
        require(isinstance(route_data, dict), f"{node}: route table absent")
        if node in ("edge", "core"):
            require(FORBIDDEN not in route_data, f"{node}: forbidden prefix in post-test snapshot")
            dest, preferred, alternate = PRIMARY[node]
            paths = route_data.get(dest)
            require(isinstance(paths, list) and len(paths) >= 2, f"{node}: expected both candidate paths")
            selected = [p for p in paths if p.get("bestpath") is True or (
                isinstance(p.get("bestpath"), dict) and p["bestpath"].get("overall") is True)]
            require(len(selected) == 1, f"{node}: exactly one BGP bestpath expected")
            require(selected[0].get("locPrf") == 200 and selected_hop(selected[0]) == preferred,
                    f"{node}: primary bestpath or local-preference mismatch")
            require(any(p.get("locPrf") == 100 and selected_hop(p) == alternate for p in paths),
                    f"{node}: alternative bestpath not present/local-preference mismatch")
            fib = parsed_command(nodes[node], "show ip route json", node)
            fib_routes = fib.get(dest)
            require(isinstance(fib_routes, list), f"{node}: kernel/FRR route missing")
            installed = [p for p in fib_routes if p.get("protocol") == "bgp" and
                         p.get("selected") is True and p.get("installed") is True]
            require(any(selected_hop(p) == preferred for p in installed),
                    f"{node}: selected installed route does not match BGP primary")
            summary_nexthops[node] = {
                "remote_prefix": dest,
                "primary": {"nexthop": preferred, "local_preference": 200, "bestpath": True},
                "backup": {"nexthop": alternate, "local_preference": 100, "bestpath": False},
                "route_reported_installed": True,
            }
        version = nodes[node].get("show version", "")
        require(isinstance(version, str) and "FRRouting 10.7.1" in version,
                f"{node}: unexpected FRR image version")

    return {
        "verification": "PASS",
        "provenance": "User-supplied Windows 11 Docker Desktop runtime JSON; verified offline against declared invariants",
        "raw_file_sha256": hashes,
        "snapshotted_bgp_peer_perspectives_established": peers_verified,
        "snapshot_timestamp_utc": snapshot.get("observed_at_utc"),
        "observed_bestpaths_after_recovery": summary_nexthops,
        "baseline": {"status": base["status"], "elapsed_check_seconds": base["elapsed_check_seconds"],
                     "observed_at_utc": base.get("observed_at_utc")},
        "failover": {"backup_path_observed": fail["backup_path_observed"],
                     "observed_failover_seconds": fail["observed_failover_seconds"],
                     "poll_interval_seconds": fail["poll_interval_seconds"],
                     "start_to_end_seconds": fail["start_to_end_seconds"],
                     "observed_at_utc": fail.get("observed_at_utc")},
        "filter": {"status": filt["status"], "prefix": filt["prefix"],
                   "received_by_edge": filt["received_by_edge"],
                   "received_by_core": filt["received_by_core"],
                   "observation_seconds": filt["observation_seconds"],
                   "observed_at_utc": filt.get("observed_at_utc")},
        "scope_limitations": [
            "Input JSON is a user-supplied artifact, not a cryptographically authenticated sensor measurement.",
            "Snapshot shows restored/normal state, not the forwarding table during outage.",
            "Failover timing includes Docker/CLI overhead and 0.5 s polling; not packet loss or outage duration.",
            "A finite-period forbidden-prefix absence does not establish universal route-leak resistance.",
            "Neither packet latency, jitter, throughput nor hardware HFT characteristics were measured.",
            "Two-way ICMP and primary recovery were verified by workstation console output; detailed ping transcript not in JSON.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", type=Path, help="ZIP containing baseline, failover, filter and snapshot JSON files")
    parser.add_argument("--output", type=Path, help="Optional derived JSON report path (does not alter original evidence)")
    args = parser.parse_args(argv)
    try:
        docs, hashes = read_evidence_zip(args.zip_path)
        report = verify_documents(docs, hashes)
        report["source_zip_sha256"] = sha256(args.zip_path.read_bytes())
    except (OSError, zipfile.BadZipFile, EvidenceError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print("[PASS] Four original JSON documents validated")
    print("[PASS] Eight established directional BGP peer perspectives in snapshot")
    print("[PASS] Dual BGP paths with local-pref 200 / 100; primary FIB routes installed")
    print("[PASS] Failover observation recorded, filter status recorded, post-test forbidden prefix absent")
    print("[CAUTION] Timings are control-plane/CLI observations, not data-plane outage measurements")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Derived report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
