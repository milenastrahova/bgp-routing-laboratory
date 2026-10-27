# Validation matrix — v0.4 package, v0.2 runtime artifacts

**Evidence:** user-supplied four JSON files plus Windows PowerShell screenshots, generated on 2026-10-27. Independently parsed offline for v0.4. `docs/evidence-summary-2026-10-27.json` contains the original file checksums, selected observed values and limitations. Live tests were run by the workstation user against v0.2; v0.4 does **not** alter `compose.yaml`, FRR configs or core experiment controller behavior.

| Assertion | Status | Provenance |
|---|---|---|
| FRR 10.7.1 / four routers / four private ASNs | **CONFIRMED** | FRR `show version`, `show bgp summary json` in user snapshot |
| 8 directional BGP neighbor perspectives Established | **CONFIRMED (snapshot)** | 4 × FRR summary JSON, 2 expected peers each |
| Both primary paths best, Local Preference 200 vs 100 backup | **CONFIRMED (snapshot)** | edge/core FRR BGP paths and next hops |
| Selected primary paths reported installed | **CONFIRMED (snapshot)** | edge/core `show ip route json` |
| Sourced ICMP both ways, baseline | **PASS (workstation run)** | User PowerShell output; JSON has PASS result but not individual ping traces |
| Failover backup observed | **PASS (workstation run)** | Failover JSON and terminal logs from both endpoints; not a snapshot taken during outage |
| ICMP reachable after failover & primary restored | **PASS (workstation run)** | User PowerShell output; individual packets not preserved in supplied JSON |
| Unauthorized `198.18.0.1/32` absent at endpoints | **CONFIRMED (finite observation)** | Filter JSON plus post-test snapshot; does not prove universal prevention |
| Diagnostic snapshot gathered from all four routers | **CONFIRMED** | User supplied actual 4-node snapshot JSON |
| Offline v0.4 tests | **PASS (packaging runtime)** | unittest; synthetic verifier tests + static/logic tests |
| GitHub Actions static workflow | **NOT RUN** | Will run only after the project is pushed to GitHub |
| GitHub manual Docker integration workflow | **NOT RUN** | Requires manual GitHub workflow run |
| Continuous packet-loss interval / jitter / latency / throughput | **NOT MEASURED** | Not present in uploaded JSON |
| Production HFT infrastructure performance | **NOT CLAIMED** | Docker simulation only |

Run independent re-validation on the private original archive:

```powershell
py -3 .\scripts\verify_evidence.py .\BGP_Evidence_v0.2.zip
```

Place private evidence ZIP inside `artifacts/` instead of the repository root to benefit from `.gitignore`, and adjust the relative path in the command. Results are **not** digitally signed. Independent parsing establishes internal consistency, not incontrovertible authenticity.
