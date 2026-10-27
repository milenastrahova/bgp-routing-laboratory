#!/usr/bin/env python3
"""Control an isolated four-AS FRRouting lab using Docker Compose.

Standard library only; no configuration of Windows, WSL2 or host routing.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "gravity-bgp-lab"
SERVICES = ("edge", "transit_primary", "transit_backup", "core")
TARGET = "10.40.40.1/32"
RETURN_TARGET = "10.10.10.1/32"
PRIMARY_NH = "10.255.10.3"
BACKUP_NH = "10.255.20.3"
CORE_PRIMARY_NH = "10.255.30.2"
CORE_BACKUP_NH = "10.255.40.2"
ROGUE = "198.18.0.1/32"


class LabError(RuntimeError):
    """Something needed by the lab did not work."""


def command(argv: list[str], timeout: int = 45) -> str:
    try:
        result = subprocess.run(
            argv, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise LabError(f"Executable not found: {argv[0]}. Is Docker Desktop installed and running?") from exc
    except subprocess.TimeoutExpired as exc:
        raise LabError(f"Command timed out after {timeout}s: {' '.join(argv)}") from exc
    if result.returncode:
        raise LabError(
            f"Command failed (exit {result.returncode}): {' '.join(argv)}\n"
            f"stdout: {result.stdout.strip()}\nstderr: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def compose(*args: str, timeout: int = 90) -> str:
    return command(
        ["docker", "compose", "--project-name", PROJECT,
         "-f", str(ROOT / "compose.yaml"), *args], timeout=timeout
    )


def inside(router: str, *argv: str, timeout: int = 30) -> str:
    if router not in SERVICES:
        raise LabError(f"Unknown router {router!r}")
    return compose("exec", "-T", router, *argv, timeout=timeout)


def vtysh(router: str, *commands: str) -> str:
    args = ["vtysh"]
    for item in commands:
        args.extend(["-c", item])
    return inside(router, *args)


def vtyjson(router: str, cli: str) -> dict[str, Any]:
    raw = vtysh(router, cli)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LabError(f"Unexpected non-JSON FRR response on {router}: {raw[:1000]}") from exc
    if not isinstance(data, dict):
        raise LabError(f"Unexpected FRR response type on {router}: {type(data).__name__}")
    return data


def route_paths(payload: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    """FRR prefix JSON may be a direct entry or under 'routes'."""
    candidates: list[Any] = [payload]
    if isinstance(payload.get("routes"), dict):
        candidates.append(payload["routes"].get(prefix))
    candidates.append(payload.get(prefix))
    for data in candidates:
        if isinstance(data, dict) and isinstance(data.get("paths"), list):
            return [path for path in data["paths"] if isinstance(path, dict)]
        if isinstance(data, list):
            return [path for path in data if isinstance(path, dict)]
    return []


def best_nexthop(payload: dict[str, Any], prefix: str) -> str | None:
    paths = route_paths(payload, prefix)
    for path in paths:
        bp = path.get("bestpath")
        is_best = (isinstance(bp, dict) and bp.get("overall") is True) or bp is True
        if is_best or (len(paths) == 1 and path.get("valid") is True):
            hops = path.get("nexthops", [])
            for hop in hops:
                if isinstance(hop, dict):
                    ip = hop.get("ip") or hop.get("ip4")
                    if ip:
                        return str(ip)
            # Locally originated entries use 0.0.0.0 and may omit nexthops.
            if path.get("local") or path.get("sourced"):
                return "local"
    return None


def all_peers(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Handle JSON layouts with peers at top level or below address family."""
    if not isinstance(payload, dict):
        return {}
    direct = payload.get("peers")
    if isinstance(direct, dict):
        return {str(ip): details for ip, details in direct.items() if isinstance(details, dict)}
    for value in payload.values():
        if isinstance(value, dict):
            nested = all_peers(value)
            if nested:
                return nested
    return {}


def established(peer: dict[str, Any]) -> bool:
    state = peer.get("state") or peer.get("bgpState") or peer.get("peerState")
    return isinstance(state, str) and state.lower() == "established"


def wait_until(label: str, predicate, timeout: int = 90, interval: float = 1.0) -> float:
    began = time.monotonic()
    last_error = "no result"
    while time.monotonic() - began < timeout:
        try:
            if predicate():
                elapsed = time.monotonic() - began
                print(f"[PASS] {label} ({elapsed:.2f}s observed)")
                return elapsed
            last_error = "condition not yet met"
        except LabError as exc:
            last_error = str(exc).splitlines()[0]
        time.sleep(interval)
    raise LabError(f"[FAIL] {label}: timeout {timeout}s; last detail: {last_error}")


def current_nexthop(router: str, prefix: str) -> str | None:
    return best_nexthop(
        vtyjson(router, f"show bgp ipv4 unicast {prefix} json"), prefix
    )


def expected_peers() -> dict[str, set[str]]:
    return {
        "edge": {"10.255.10.3", "10.255.20.3"},
        "transit_primary": {"10.255.10.2", "10.255.30.3"},
        "transit_backup": {"10.255.20.2", "10.255.40.3"},
        "core": {"10.255.30.2", "10.255.40.2"},
    }


def check_peer_sessions() -> bool:
    for router, ips in expected_peers().items():
        result = vtyjson(router, "show bgp ipv4 unicast summary json")
        peers = all_peers(result)
        if not all(ip in peers and established(peers[ip]) for ip in ips):
            return False
    return True


def connectivity() -> None:
    print("Checking sourced ICMP both directions inside the isolated routers...")
    inside("edge", "ping", "-c", "2", "-W", "2", "-I", "10.10.10.1", "10.40.40.1")
    inside("core", "ping", "-c", "2", "-W", "2", "-I", "10.40.40.1", "10.10.10.1")
    print("[PASS] Two-way ICMP with loopback source addresses")


def require_baseline(timeout: int) -> None:
    wait_until("all 8 eBGP neighbor perspectives Established", check_peer_sessions, timeout)
    wait_until("edge prefers primary transit for core loopback",
               lambda: current_nexthop("edge", TARGET) == PRIMARY_NH, timeout)
    wait_until("core prefers primary transit for edge loopback",
               lambda: current_nexthop("core", RETURN_TARGET) == CORE_PRIMARY_NH, timeout)
    connectivity()


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def save_result(stem: str, result: dict[str, Any]) -> Path:
    out_dir = ROOT / "artifacts"
    out_dir.mkdir(exist_ok=True)
    file = out_dir / f"{stem}-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}.json"
    file.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Saved local evidence: {file.relative_to(ROOT)}")
    return file


def check_command(timeout: int) -> None:
    started = time.monotonic()
    require_baseline(timeout)
    result = {
        "experiment": "baseline", "observed_at_utc": timestamp(),
        "source": "Docker Desktop FRR lab", "status": "PASS",
        "edge_core_best_nexthop": current_nexthop("edge", TARGET),
        "core_edge_best_nexthop": current_nexthop("core", RETURN_TARGET),
        "elapsed_check_seconds": round(time.monotonic() - started, 3),
        "measurement_note": "Elapsed check time includes polling and CLI overhead; not packet latency.",
    }
    save_result("baseline", result)


def failover_command(timeout: int) -> None:
    require_baseline(timeout)
    print("Stopping ONLY the transit_primary service in this Compose project...")
    started = time.monotonic()
    success = False
    failure_message: str | None = None
    observed_seconds: float | None = None
    try:
        compose("stop", "-t", "2", "transit_primary", timeout=45)
        wait_until(
            "edge moved core prefix to backup transit",
            lambda: current_nexthop("edge", TARGET) == BACKUP_NH, timeout,
            interval=0.5,
        )
        observed_seconds = time.monotonic() - started
        wait_until("core moved edge prefix to backup transit",
                   lambda: current_nexthop("core", RETURN_TARGET) == CORE_BACKUP_NH, timeout)
        connectivity()
        success = True
    except (LabError, KeyboardInterrupt) as exc:
        failure_message = str(exc)
        raise
    finally:
        # Always recover the topology, even on test failure or interruption.
        print("Restoring transit_primary...")
        try:
            compose("start", "transit_primary", timeout=60)
            require_baseline(timeout)
            print("[PASS] Preferred primary path restored")
        except LabError as exc:
            print(f"[WARN] Automatic restore failed: {exc}", file=sys.stderr)
        save_result("failover", {
            "experiment": "primary_transit_container_stop",
            "observed_at_utc": timestamp(),
            "backup_path_observed": success,
            "observed_failover_seconds": round(observed_seconds, 3) if observed_seconds is not None else None,
            "start_to_end_seconds": round(time.monotonic() - started, 3),
            "poll_interval_seconds": 0.5,
            "failure_detail": failure_message,
            "method": "Wall clock from before Docker Compose stop through observed BGP bestpath via Docker exec/vtysh",
            "limitations": "Includes Docker stop scheduling and polling; not a hardware forwarding outage measurement.",
        })


def filter_command(timeout: int) -> None:
    require_baseline(timeout)
    print(f"Injecting one TEST-NET benchmarking prefix {ROGUE} at primary transit...")
    began = time.monotonic()
    try:
        vtysh("transit_primary", "configure terminal", "interface lo",
              "ip address 198.18.0.1/32", "exit", "router bgp 65020",
              "address-family ipv4 unicast", f"network {ROGUE}", "end")
        wait_until("injected route exists on transit_primary",
                   lambda: bool(route_paths(vtyjson("transit_primary", f"show bgp ipv4 unicast {ROGUE} json"), ROGUE)), timeout)
        # The rogue prefix is not covered by any export route-map on either transit.
        # Give BGP a small observation interval, then assert denied downstream.
        time.sleep(5)
        leaked_to = [node for node in ("edge", "core")
                     if route_paths(vtyjson(node, f"show bgp ipv4 unicast {ROGUE} json"), ROGUE)]
        if leaked_to:
            raise LabError(f"ROUTE LEAK: {ROGUE} observed on {', '.join(leaked_to)}")
        print("[PASS] Unapproved BGP prefix denied at both neighbor export policies")
        save_result("filter", {
            "experiment": "unauthorized_prefix_injection",
            "observed_at_utc": timestamp(), "origin": "transit_primary",
            "prefix": ROGUE, "received_by_edge": False,
            "received_by_core": False, "observation_seconds": round(time.monotonic() - began, 3),
            "status": "PASS",
        })
    finally:
        print("Removing injected prefix and loopback address...")
        try:
            vtysh("transit_primary", "configure terminal", "router bgp 65020",
                  "address-family ipv4 unicast", f"no network {ROGUE}",
                  "exit-address-family", "interface lo", "no ip address 198.18.0.1/32", "end")
        except LabError as exc:
            print(f"[WARN] Cleanup failed; run 'python scripts/labctl.py up' after 'down': {exc}", file=sys.stderr)



def probe(router: str, *argv: str, timeout: int = 20) -> dict[str, Any]:
    """Capture command output even when the command reports failure.

    This makes failed ping and failed kernel lookups useful troubleshooting
    evidence. The command runs solely INSIDE a lab container.
    """
    try:
        output = inside(router, *argv, timeout=timeout)
        return {"ok": True, "output": output}
    except LabError as exc:
        return {"ok": False, "output": str(exc)}


def diagnose_command() -> None:
    """Capture control-plane, forwarding-plane, and link-local probes.

    Does not change routes, firewall settings, sysctls, or Docker state.
    """
    print("Diagnosing BGP control plane and Linux forwarding plane (read-only)...")
    diagnostic: dict[str, Any] = {
        "experiment": "read_only_diagnostics",
        "observed_at_utc": timestamp(),
        "source": "FRR 10.7.1, Docker Compose",
        "routers": {},
        "interpretation": "A BGP bestpath alone does not prove Linux FIB or ICMP forwarding.",
    }
    expected_remote = {
        "edge": "10.40.40.1",
        "transit_primary": "10.40.40.1",
        "transit_backup": "10.40.40.1",
        "core": "10.10.10.1",
    }
    for router in SERVICES:
        print(f"\n--- {router} ---")
        results: dict[str, Any] = {}
        tasks = {
            "ipv4_addresses": ("ip", "-4", "addr", "show"),
            "ipv4_routes": ("ip", "-4", "route", "show"),
            "route_lookup": ("ip", "-4", "route", "get", expected_remote[router]),
            "ipv4_forwarding": ("sysctl", "net.ipv4.ip_forward"),
            "frr_ipv4_routes": ("vtysh", "-c", "show ip route"),
            "frr_bgp_summary": ("vtysh", "-c", "show bgp ipv4 unicast summary"),
        }
        for label, argv in tasks.items():
            result = probe(router, *argv)
            results[label] = result
            print(f"  {label}: {'OK' if result['ok'] else 'ERROR'}")
            if label in ('ipv4_routes', 'route_lookup', 'ipv4_forwarding'):
                for line in result['output'].splitlines()[:30]:
                    print(f"    {line}")
        diagnostic["routers"][router] = results
    link_probes = (
        ("edge_to_primary", "edge", "10.255.10.3"),
        ("primary_to_core", "transit_primary", "10.255.30.3"),
        ("edge_to_backup", "edge", "10.255.20.3"),
        ("backup_to_core", "transit_backup", "10.255.40.3"),
        ("edge_to_core_loopback", "edge", "10.40.40.1"),
        ("core_to_edge_loopback", "core", "10.10.10.1"),
    )
    diagnostic["icmp_probes"] = {}
    print("\n--- ICMP results ---")
    for label, router, address in link_probes:
        result = probe(router, "ping", "-c", "2", "-W", "2", address, timeout=15)
        diagnostic["icmp_probes"][label] = result
        print(f"  {label}: {'PASS' if result['ok'] else 'FAIL'}")
    evidence_file = save_result("diagnostic", diagnostic)
    print(f"Send the file {evidence_file} (or paste the command output) to investigate.")


def collect_command() -> None:
    info: dict[str, Any] = {"observed_at_utc": timestamp(), "routers": {}}
    commands = (
        "show version", "show bgp ipv4 unicast summary json",
        "show bgp ipv4 unicast json", "show ip route json",
        "show running-config",
    )
    for node in SERVICES:
        print(f"Collecting {node}...")
        info["routers"][node] = {}
        for cli in commands:
            try:
                info["routers"][node][cli] = vtysh(node, cli)
            except LabError as exc:
                info["routers"][node][cli] = {"error": str(exc)}
    save_result("snapshot", info)



def bundle_command() -> Path:
    """Package existing local runtime evidence without synthesizing any measurements.

    This is a read-only operation on artifacts/*.json. The ZIP is created
    inside artifacts/ (which is ignored by Git) for optional private review.
    """
    evidence_dir = ROOT / "artifacts"
    files = sorted(evidence_dir.glob("*.json")) if evidence_dir.is_dir() else []
    if not files:
        raise LabError("No artifacts/*.json exist. First run check, failover, filter and collect on Docker Desktop.")
    manifest: dict[str, Any] = {
        "generated_at_utc": timestamp(),
        "warning": "Original local results. Review files before public upload. ZIP generation does not validate the reported experiments.",
        "files": [],
    }
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise LabError(f"Cannot include invalid evidence JSON {path.name}: {exc}") from exc
        if not isinstance(payload, dict):
            raise LabError(f"Expected JSON object in evidence file {path.name}")
        raw = path.read_bytes()
        manifest["files"].append({
            "filename": path.name,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    zip_path = evidence_dir / f"BGP_Evidence_{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, arcname=path.name)
        bundle.writestr("evidence-manifest.json", json.dumps(manifest, indent=2) + "\n")
    print(f"Bundled {len(files)} authentic local JSON file(s): {zip_path}")
    print("Review the data for private information before sharing publicly. No packets were measured during bundling.")
    return zip_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=[
        "preflight", "up", "down", "status", "check", "failover", "filter", "collect", "diagnose", "bundle"])
    parser.add_argument("--timeout", type=int, default=90,
                        help="maximum seconds per expected convergence state (default: 90)")
    args = parser.parse_args(argv)
    if args.timeout < 5:
        parser.error("--timeout must be at least 5")
    try:
        if args.action == "preflight":
            if shutil.which("docker") is None:
                raise LabError("Docker CLI absent; install/start Docker Desktop on YOUR machine.")
            print(command(["docker", "version", "--format", "{{.Server.Version}}"], timeout=20))
            print(compose("config", "-q", timeout=30) or "Compose syntax OK")
            print("[PASS] Docker server reachable; Compose configuration validated")
        elif args.action == "up":
            print(compose("up", "-d", timeout=180))
            print("Containers started. Run 'python scripts/labctl.py check' to validate.")
        elif args.action == "down":
            print(compose("down", "--remove-orphans", timeout=120))
            print("Only gravity-bgp-lab project containers/networks removed.")
        elif args.action == "status":
            print(compose("ps"))
            for node in SERVICES:
                print(f"\n=== {node} ===")
                print(vtysh(node, "show bgp ipv4 unicast summary"))
        elif args.action == "check":
            check_command(args.timeout)
        elif args.action == "failover":
            failover_command(args.timeout)
        elif args.action == "filter":
            filter_command(args.timeout)
        elif args.action == "collect":
            collect_command()
        elif args.action == "diagnose":
            diagnose_command()
        elif args.action == "bundle":
            bundle_command()
    except (LabError, KeyboardInterrupt) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
