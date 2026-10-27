# Architecture and design decisions

## Goal and threat model

Demonstrate controlled **routing policy**, eBGP adjacency management, failover, and evidence-driven network troubleshooting. The topology exists entirely in isolated container network namespaces and Docker bridges, never on the Internet. It is not an HFT latency benchmark.

## AS graph

```text
                          AS65020 primary
                  10.255.10.3  10.255.30.2
                    ┌─────────────────┐
 AS65010 edge       │                 │          AS65040 core
 10.10.10.1/32 ─────┤                 ├────────── 10.40.40.1/32
                    │                 │
                    └─────────────────┘
                  10.255.20.3  10.255.40.2
                          AS65030 backup
```

**Actual wiring** is a diamond, not a shared subnet. Link addresses:

| Docker network | Subnet | Left endpoint | Right endpoint | Docker gateway |
|---|---|---|---|---|
| edge_primary | 10.255.10.0/29 | edge `.2` | transit_primary `.3` | `.1` |
| edge_backup | 10.255.20.0/29 | edge `.2` | transit_backup `.3` | `.1` |
| primary_core | 10.255.30.0/29 | transit_primary `.2` | core `.3` | `.1` |
| backup_core | 10.255.40.0/29 | transit_backup `.2` | core `.3` | `.1` |

Docker dynamically names container interfaces (`eth0`/`eth1`) according to attachment order. FRR peers on stable IPv4 addresses, not interface names. The four Docker bridge networks have NAT/masquerading explicitly disabled so
loopback-originated packets can be forwarded inside this routing laboratory.
There are no published ports or host networking settings, and Windows routes
are not modified. Unlike Docker `internal` networks these bridges are
accessible from the Docker host; avoid treating disabled masquerade as a strong
network security barrier.

## Control plane vs data plane

`bgpd` speaks TCP port 179 **between containers** and maintains a BGP table. `zebra` programs selected IPv4 routes into the **container's** Linux kernel. On edge/core, `zebra` also configures the /32 loopback address from `frr.conf`, allowing a ping sourced at the local loopback to reach the remote one once BGP routing works. Enable IPv4 forwarding only per container via Compose `sysctls`.

Use:

```shell
vtysh -c 'show bgp ipv4 unicast 10.40.40.1/32 json'  # BGP bestpath
ip -4 route get 10.40.40.1                         # Linux selected forwarding route
```

These two outputs answer different questions; BGP can have a valid route without a usable forwarding entry if next-hop resolution or kernel installation fails.

## Route origination

- `edge` originates **only** `10.10.10.1/32` (AS65010).
- `core` originates **only** `10.40.40.1/32` (AS65040).
- Both transit routers originate no prefixes by default.
- No redistribution of Docker/connected routes into BGP.
- Service /32s require the corresponding interface route to exist. There is no dummy blackhole route posing as an end host.

## Import/export policies

At every peer, an inbound **and** an outbound route map is attached. All route maps have an implicit deny at the end:

| Router | Neighbor | Accepted inbound | Permitted outbound | Local Preference inbound |
|---|---|---|---|---|
| edge | primary transit | core /32 | edge /32 | 200 |
| edge | backup transit | core /32 | edge /32 | 100 |
| core | primary transit | edge /32 | core /32 | 200 |
| core | backup transit | edge /32 | core /32 | 100 |
| primary transit | edge | edge /32 | core /32 | unchanged |
| primary transit | core | core /32 | edge /32 | unchanged |
| backup transit | edge | edge /32 | core /32 | unchanged |
| backup transit | core | core /32 | edge /32 | unchanged |

This configuration deliberately uses eBGP policy enforcement: it does not disable the `bgp ebgp-requires-policy` requirement. If all sessions establish but no prefixes arrive, inspect route map attachment in both directions before troubleshooting basic connectivity.

## Bestpath expectation

The edge learns `10.40.40.1/32` from AS65020 and AS65030; each path has two ASNs in AS_PATH. The inbound route map assigns higher local preference to AS65020, so the preferred route should point to `10.255.10.3`. The core independently prefers `10.255.30.2` towards AS65010. Only if the primary path is lost should both route tables select the backup transit's next-hop.

FRR's Local Preference governs decisions *inside the router's AS*; these route maps set it upon import from eBGP. Local Preference should not be presented as a signal advertised to an eBGP neighbor.

## Failover experiment

1. Establish baseline adjacency, expected bestpaths and sourced ICMP.
2. Stop the `transit_primary` **container** (not Windows networking).
3. Poll the BGP JSON on the edge until the bestpath becomes `10.255.20.3`.
4. Confirm the core selects `10.255.40.2`, and ICMP works in both directions.
5. Restore `transit_primary` in a `finally` block and wait for preferred routes to return.
6. Save a UTC-stamped JSON observation in `artifacts/`.

Observation measures wall clock from before invoking Docker Compose stop until the Python process first sees backup BGP bestpath; Docker stop overhead, subprocess launches and polling are included. This is **not** line-rate packet convergence, production recovery or a reliable HFT SLA. Repeated runs may differ.

## Route leak experiment

After a validated baseline, temporarily inject `198.18.0.1/32` (part of RFC 2544 benchmarking address space) into primary transit's loopback and BGP RIB. It should exist locally on primary transit but **not** appear on either edge or core because transit's outbound route maps allow only one explicitly approved service prefix per neighbor. The Python controller removes the injected prefix/address even when the test fails.

## Scope boundaries

- No production routing, public BGP, routing hardware, real exchanges, cross-connects, optical links, PTP/chrony, kernel bypass or NIC tuning.
- No traffic generation, PPS claims, nanosecond or microsecond latency claims.
- No BFD in v0.1. Fast detection uses BGP timers `3 9` (lab-only; production values depend on network design). A container stop may still take up to the hold timeout to converge.
- No secret credentials. Avoid connecting this lab to production networks.
