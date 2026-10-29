# BGP Routing Laboratory

**A reproducible four-autonomous-system eBGP routing, policy and failover lab.**  
FRRouting 10.7.1 · Docker Compose · Python 3.10+ · Windows/WSL2 or Linux

This is an independent, working networking laboratory—not a production HFT deployment. It demonstrates **the route selected, the reason it was selected, what happens when the primary transit fails, and how the observation was validated**.

## At a glance

| Capability | Implementation / evidence |
| --- | --- |
| Four BGP autonomous systems | Edge **65010**, Primary **65020**, Backup **65030**, Core **65040** |
| Redundant routes | Two distinct transit ASes between Edge and Core |
| Deterministic route policy | Inbound Local Preference **200** for Primary; **100** for Backup |
| Route filtering | Explicit inbound/outbound prefix-list and route-map allowlists; unauthorized prefix injection test |
| Operational checks | FRR BGP state, Linux route observations, bidirectional sourced ICMP |
| Resilience exercise | Bounded primary-container outage, backup path observation and recovery |
| CI | [Static validation](https://github.com/milenastrahova/bgp-routing-laboratory/actions/workflows/ci.yml) and [real Docker integration](https://github.com/milenastrahova/bgp-routing-laboratory/actions/workflows/integration.yml) — both passed on the latest tested revision |

## Topology

```text
                transit_primary (AS65020)
                 /                     \
edge (AS65010)                              core (AS65040)
                 \                     /
                 transit_backup  (AS65030)

Edge loopback: 10.10.10.1/32
Core loopback: 10.40.40.1/32
```

Both routes can be present in BGP; Edge prefers the Primary next hop because of **Local Preference**. BGP does not measure the faster physical path. The Linux forwarding table and the application must be checked separately.

## Reproduce in an isolated Docker environment

**Prerequisites:** Docker Desktop with Linux containers / WSL2 on Windows 11, or Docker Engine and Compose on Linux. No host routes or Windows system settings are modified.

From the repository root in PowerShell:

```powershell
py -3 scripts/labctl.py preflight
py -3 scripts/labctl.py up
py -3 scripts/labctl.py check --timeout 120

# Inspect protocol and actual Linux routes:
docker compose -f compose.yaml exec edge vtysh -c "show bgp ipv4 unicast summary"
docker compose -f compose.yaml exec edge vtysh -c "show bgp ipv4 unicast 10.40.40.1/32"
docker compose -f compose.yaml exec edge ip -4 route get 10.40.40.1

# Only after the healthy baseline passes, and only in this isolated lab:
py -3 scripts/labctl.py failover --timeout 120
py -3 scripts/labctl.py filter --timeout 120
py -3 scripts/labctl.py collect
py -3 scripts/labctl.py down
```

`failover` stops only the known `transit_primary` container and attempts restoration in a `finally` block. Do not run fault-injection tools against shared or production infrastructure. Results are stored locally under ignored `artifacts/`.

## Validation and engineering evidence

- **GitHub Docker integration:** live four-router baseline, controlled outage and recovery, unauthorized-prefix rejection, diagnostic collection and cleanup. [Successful CI run](https://github.com/milenastrahova/bgp-routing-laboratory/actions/runs/40930552963).
- **GitHub static CI:** config invariants, JSON validation, unit tests and Compose schema. [Successful CI run](https://github.com/milenastrahova/bgp-routing-laboratory/actions/runs/40930552962).
- **Operator field evidence (27 October 2026):** eight directional neighbor states observed Established; primary Local Preference and path preference observed; sourced ICMP baseline and recovery checks; blocked test prefix absent at endpoints. [Validation matrix](docs/validation.md) · [Field report](docs/field-report-2026-10-27.md).
- **Architecture exercise:** two-venue colocation connectivity, physical diversity, cross-connect planning, security and rollback. [Data Center Connectivity Design Case](docs/datacenter-connectivity-design.md). This is a documented exercise, **not** installed physical infrastructure.

## Repository guide

| Read next | Purpose |
| --- | --- |
| [Topology and route policy](docs/architecture.md) | Addresses, peers, policy and design rationale |
| [Operational runbook](docs/runbook.md) | Commands, diagnostics, expected results, recovery |
| [Validation and real field evidence](docs/validation.md) | What has and has not been observed |
| [Technical interview defense](docs/interview-defense.md) | Failure reasoning, RIB/FIB, path-selection tradeoffs |
| [FRR configuration](configs/edge/frr.conf) | Actual Edge BGP policy, not screenshots |
| [Controller source](scripts/labctl.py) | Real Docker/FRR orchestration and evidence collection |
| [Tests](tests/) | Offline parser and configuration tests |

## Honest engineering boundaries

This is a **Docker namespace simulation**, not a physical router fabric. A successful BGP session does not itself prove forwarding; a polled bestpath timestamp is not packet-level outage duration or HFT convergence. The project does not claim NIC hardware latency, PTP, DPDK, provider cross-connects, or production exchange connectivity.

The legacy Docker project identifier `gravity-bgp-lab` is retained for compatibility with bounded safety checks in the connected toolkit; it does not indicate employer affiliation. Its rename requires coordinated testing across repositories.

*Independent engineering portfolio project. All reported experiments are controlled laboratory observations.*
