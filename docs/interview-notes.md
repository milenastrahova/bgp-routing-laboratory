# Interview defense notes — BGP Routing Laboratory

This is a hands-on portfolio exercise. Be transparent about which tests you executed yourself. The goal is to show you can reason from the configuration and real diagnostics, not to claim production experience.

## 60-second project description

> I built a four-AS eBGP diamond using Docker and FRRouting. The edge and core each have an advertised loopback service address. They can reach each other through either a primary or backup transit AS. I configure explicit inbound/outbound prefix filters at every peering and higher inbound Local Preference for the primary route. The Python controller verifies all BGP neighbors, chooses bestpaths from FRR JSON, tests loopback-sourced ICMP, stops the primary transit to observe failover, restores the preferred path, and injects an unauthorized prefix to demonstrate filtering. CI checks offline invariants, while integration checks require a running Docker environment.

## Typical follow-up questions

**Why eBGP instead of static routing?** BGP's AS_PATH, per-neighbor filtering, and Local Preference policies let me reproduce path-selection and external network failures. Static routes alone wouldn't exercise these attributes.

**What makes your primary path win?** The edge and core independently assign Local Preference 200 to routes learned from the primary transit and 100 to backup. Both paths traverse two external ASNs, so the higher Local Preference wins before AS_PATH length is considered.

**Is Local Preference propagated between eBGP neighbors?** No. In this lab it is assigned by an inbound route map and used *locally* for bestpath selection.

**What happens when primary transit disappears?** The edge and core should stop selecting that path after the routes are withdrawn or the relevant peering sessions expire. They then choose the already learned backup, with different next-hop addresses. I validate this at both endpoints and with sourced pings.

**Why can a route exist in the BGP RIB but not forward packets?** The kernel may lack an installed route, the next-hop might be unreachable, IP forwarding could be disabled in a transit router, or loopback address installation could fail. I compare `show bgp`, `show ip route` and `ip route get`.

**Why source ping from loopback?** It validates reachability to the advertised /32 prefixes in *both* directions, rather than succeeding only because transit link subnets are directly connected.

**What does your route leak test prove?** A locally originated unapproved route at one transit router is rejected by explicit outbound policy, so it does not enter the edge/core BGP RIBs. It does not prove RPKI validation or Internet-scale leak protection.

**How does this map to HFT engineering?** The relevant skills are routing protocol analysis, fault isolation, reproducible change validation, route-policy safety and disciplined incident evidence. The lab does not reproduce an exchange network or quantify HFT trading latency.

**What are the main limits?** Docker network scheduling, lack of hardware timestamping, no precise data-plane capture, and artificially small topology. Failover time is a control-plane observation bound by polling and container shutdown overhead; I would never call it wire latency.

**What would you change next?** Add BFD for faster detection, a one-link flap experiment, longer soak testing, latency probes with clock and measurement caveats, and automated PCAP collection. On actual hardware I would account for NIC/driver behavior and timestamping accuracy.

## Commands to know without notes

```text
show bgp ipv4 unicast summary
show bgp ipv4 unicast 10.40.40.1/32
show bgp ipv4 unicast 10.40.40.1/32 json
show ip route 10.40.40.1/32
show running-config
ip -4 route get 10.40.40.1
ip -4 addr
```

## How to discuss results truthfully

If Docker integration has not yet been executed: *"The topology and policies are implemented and Python unit tests pass, but I have not yet validated live peering on Docker Desktop."* Once tested, bring actual dated logs and explain any failed runs as well as successes.
