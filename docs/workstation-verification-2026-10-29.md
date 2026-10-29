# Workstation BGP verification — 29 October 2026

**Project:** BGP Routing Laboratory  
**Environment:** Windows 11 PowerShell + Docker Desktop Linux engine, running four FRRouting containers.  
**Evidence provenance:** The operator supplied PowerShell screenshots from the 29 October 2026 local run. The original JSON artifacts are retained in the workstation's ignored `artifacts/` directory and **have not been uploaded or independently inspected for this entry**. This document reports what is visible in the terminal output; it is not a cryptographic verification of source files.

## Commands executed and observed results

| Stage | Command / evidence file | Observation visible in the supplied terminal output |
| --- | --- | --- |
| Docker preflight | `py -3 scripts/labctl.py preflight` | Docker engine reachable; Compose configuration validated — PASS |
| Start | `py -3 scripts/labctl.py up` | Containers started |
| Baseline | `py -3 scripts/labctl.py check --timeout 120` | Eight directional eBGP sessions Established, both endpoints selected primary next hops, sourced ICMP succeeded in both directions — PASS |
| Live snapshot | `py -3 scripts/labctl.py collect` | All four routers collected to `snapshot-20261029T203836Z.json` |
| Independent analysis | `py -3 -m netops bgp-triage --snapshot <local-snapshot>` in Network Operations Toolkit | `control_plane_audit_status: PASS`, `issues_found: 0`, `status: PASS`; snapshot observed_at_utc `2026-10-29T20:38:33+00:00` |
| Controlled primary stop | `py -3 scripts/labctl.py failover --timeout 120` | After stopping only `transit_primary`, both edge and core selected backup paths; sourced two-way ICMP succeeded — PASS |
| Restore | Same `failover` command | Primary container restarted, eight eBGP sessions Established again, primary paths restored, sourced ICMP succeeded — PASS; result saved as `failover-20261029T205323Z.json` |
| Independent recovery baseline | `py -3 scripts/labctl.py check --timeout 120` | All baseline assertions PASS; saved `baseline-20261029T205338Z.json` |
| Unauthorized-prefix experiment | `py -3 scripts/labctl.py filter --timeout 120` | Test prefix `198.18.0.1/32` originated on transit_primary, export filtering prevented its appearance on edge/core during the finite check — PASS; cleanup was invoked; saved `filter-20261029T205515Z.json` |
| Post-filter baseline | `py -3 scripts/labctl.py check --timeout 120` | All eight eBGP sessions Established, primary routes and two-way sourced ICMP PASS; saved `baseline-20261029T205530Z.json` |

Earlier baseline snapshot also appeared as `baseline-20261029T203657Z.json`. Only filenames, printed assertions, and displayed results are documented here. **A subsequent read-only inspection confirmed removal of the test address and absence of its BGP route on the three inspected routers.** The exact checks are documented below.

## Additional read-only post-cleanup verification

Run against the same named *isolated* Docker Compose project after successful filtering:

```powershell
docker compose -f compose.yaml exec -T transit_primary ip -4 addr show dev lo
docker compose -f compose.yaml exec -T transit_primary vtysh -c "show bgp ipv4 unicast 198.18.0.1/32"
docker compose -f compose.yaml exec -T edge vtysh -c "show bgp ipv4 unicast 198.18.0.1/32"
docker compose -f compose.yaml exec -T core vtysh -c "show bgp ipv4 unicast 198.18.0.1/32"
```

**Observed in a later workstation PowerShell screenshot (29 October 2026):** `transit_primary` loopback displayed only `127.0.0.1/8`; the temporary address `198.18.0.1/32` was absent. FRRouting replied `% Network not in table` for `198.18.0.1/32` on `transit_primary`, `edge` and `core`. This directly supports cleanup and policy checks at those three routers at inspection time. `transit_backup` was not separately queried for this prefix. A fresh `labctl.py collect` could preserve the post-cleanup state in structured JSON, but that additional capture has not been provided.

## Interpretation and measurement boundaries

- **Verified from screenshots:** a working isolated multi-AS FRRouting baseline; BGP preference and return-path reachability via sourced ICMP; an observed switch to the backup path during controlled primary stop; primary restored; finite control-plane route filtering; observed post-cleanup absence of the test address and prefix on the three inspected routers; live cross-project control-plane auditing.
- **Not established:** physical network/NIC performance, production link redundancy, actual packet-level BGP convergence or outage duration, p99 RTT under load, zero packet loss over a continuous interval, or physical network behavior outside the inspected Docker routers.
- The roughly 5.39-second observation printed while waiting for all neighbors to become Established after restart includes polling/scheduling; it is **not a packet loss interval**.
- This run did **not** reconfigure Windows routes or Linux host networking; fault injection was limited to the specified isolated Docker laboratory.
- All data here concern a **self-contained educational laboratory**, not a commercial HFT or real exchange network.

## Reproducibility

The run can be reproduced with the commands above and the detailed [runbook](runbook.md). Raw JSON evidence is deliberately ignored from Git to avoid exposing local runtime configuration. For repeatable third-party confirmation, the operator may review and share a scrubbed evidence summary after inspecting the original files. Do not claim verified hashes or file contents for this 29 October run until they have actually been checked.
