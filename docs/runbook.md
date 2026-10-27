# Operations runbook — Windows 11 + Docker Desktop

## 1. Preflight, with no Windows configuration changes

Open PowerShell, navigate to the extracted project folder, and run:

```powershell
docker version
docker compose version
docker compose -f compose.yaml config --quiet
```

Docker must be using **Linux containers**. Docker Desktop's already configured WSL2 backend is supported. The project neither installs WSL2 nor modifies Windows routes, adapter properties, firewall rules or registry entries. Python is only needed for automated validation.

If Docker Desktop is off, start it normally; no PowerShell elevation is required. If PowerShell execution policy blocks `.ps1` wrappers, use the direct Docker/Python commands instead — **do not change execution policy globally**.

## 2. Start the topology

```powershell
docker compose -f compose.yaml up -d
docker compose -f compose.yaml ps
```

With Python 3.10+ available:

```powershell
py -3 .\scripts\labctl.py preflight
py -3 .\scripts\labctl.py check --timeout 120
```

Initial image pulls depend on network speed; preflight does not pull images. During first run, allow time for FRR daemons to become ready before declaring a peering failure.

## 3. Inspect the control plane

```powershell
docker compose -f compose.yaml exec edge vtysh -c "show bgp ipv4 unicast summary"
docker compose -f compose.yaml exec edge vtysh -c "show bgp ipv4 unicast 10.40.40.1/32"
docker compose -f compose.yaml exec edge vtysh -c "show bgp ipv4 unicast 10.40.40.1/32 json"
docker compose -f compose.yaml exec edge vtysh -c "show ip route 10.40.40.1/32"
docker compose -f compose.yaml exec edge ip -4 route get 10.40.40.1
```

`show bgp` asks what the routing protocol knows. `show ip route` and the Linux `ip route` command verify installation into the forwarding table. Under normal conditions expect edge's BGP best next-hop to be **10.255.10.3**.

## 4. Execute real fault and route policy checks

```powershell
py -3 .\scripts\labctl.py failover --timeout 120
py -3 .\scripts\labctl.py filter --timeout 120
py -3 .\scripts\labctl.py collect
```

The failover test restores primary transit even after most errors. If interrupted by a power failure, restarting the lab is safe:

```powershell
docker compose -f compose.yaml up -d
```

For manual experimentation:

```powershell
# Stop one lab router only
docker compose -f compose.yaml stop transit_primary
# Observe backup
docker compose -f compose.yaml exec edge vtysh -c "show bgp ipv4 unicast 10.40.40.1/32"
# Restore it
docker compose -f compose.yaml start transit_primary
```

Do not stop `edge` or `core` during this test: those contain the test loopback endpoints.

## 5. Diagnose reachability (read-only)

```powershell
py -3 .\scripts\labctl.py diagnose
```

The command reports Linux forwarding enabled/disabled, kernel IPv4 routes,
Zebra's selected routes, and link-local / end-to-end ping results. It captures
both successful and failed probes in `artifacts/diagnostic-*.json`.
This is intentionally read-only. If all eBGP peers are Established yet ICMP
fails, compare the FRR BGP table, Zebra RIB and Linux kernel FIB before editing
policies. The source and destination service /32s must be routable both ways.

### Upgrade from v0.1

The four Docker network definitions change. **Recreate the project's lab
networks** from inside your original v0.1 folder before starting v0.2:

```powershell
docker compose down
```

Then open a new terminal in the newly extracted v0.2 folder:

```powershell
docker compose up -d
py -3 .\scripts\labctl.py diagnose
py -3 .\scripts\labctl.py check --timeout 120
```

`docker compose down` affects the Compose project named `gravity-bgp-lab` only;
it does not remove any other Docker projects or change Windows settings.

## 6. Troubleshooting matrix

| Symptom | Inspect | Likely cause / next action |
|---|---|---|
| `docker` not found | `docker version` | Docker Desktop or CLI not installed/on PATH. This environment needs Docker Desktop on the user's machine. |
| Docker daemon not responding | `docker info` | Start Docker Desktop and verify Linux container engine. |
| Can't create Docker network | `docker network ls` | Collision with existing Docker subnet. Do not alter host routing; change lab's four subnet definitions and all peer IPs consistently. |
| FRR containers exit immediately | `docker compose logs edge` | Configuration mount, process startup, or kernel-capability error. Review `/etc/frr/daemons` and image version. |
| BGP Idle/Active | `show bgp ipv4 unicast summary`, `docker compose logs` | IP mismatch, bridge network, TCP reachability, FRR daemon not running, or ASN mismatch. |
| BGP Established but no prefixes | `show running-config`, `show bgp ipv4 unicast` | Policy mismatch, missing route for the originated /32, or route map attached in wrong direction. |
| BGP path present but ping fails | `ip -4 route`, `ip -4 addr`, `sysctl net.ipv4.ip_forward` **inside container** | Missing kernel forwarding route, loopback address, or per-container IP forwarding. |
| Primary failover appears slow | route JSON snapshots, hold timers, Docker stop logs | Timers, polling interval, Docker Desktop scheduling. Do not describe this as hardware switching latency. |
| PowerShell script denied | use direct Docker commands | No need to modify Windows-wide execution policy. |
| Py command not found | `python --version` | Use `python` instead of `py -3`, or install Python independently; direct Docker commands work without Python. |

### View diagnostics

```powershell
docker compose -f compose.yaml logs --no-color --tail 100 edge
docker compose -f compose.yaml exec transit_primary vtysh -c "show bgp ipv4 unicast summary"
docker compose -f compose.yaml exec edge ip -4 addr
```

### WSL2-specific note

All commands run against Docker Desktop, which uses an existing WSL2 backend. There is no need to open a WSL terminal, install Linux to another disk, change default distributions, or modify Windows routes. Do not assume the Windows host can reach BGP loopback /32s: no Windows host route is installed. Ping **from inside the router**.

## 6. Clean up

```powershell
py -3 .\scripts\labctl.py down
# or
docker compose -f compose.yaml down --remove-orphans
```

This removes only the project's four containers and four Docker networks, not images, other Compose projects, Windows routes, user files or Docker volumes. JSON results under `artifacts/` remain on disk; delete them manually if needed.
