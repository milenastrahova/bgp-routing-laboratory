# Data Center Connectivity Design Case — Two Trading Venues

**Status: architectural exercise; no provider ordered, no cross-connect installed, no real exchange connected, and no measured production latency.** The case supplements the four-AS Docker lab with operational thinking required for real colocated infrastructure.

## 1. Scenario and requirements

A hypothetical trading company operates two Linux trading hosts in two different colocation facilities, DC-A and DC-B, with market-data and order-gateway connections at Venue-X and Venue-Y. Names are intentionally fictional. The objective is to avoid single points of failure while keeping routing, timing, monitoring, and security observable. No numerical latency SLA is assumed.

Acceptance requirements:
- Independent primary and secondary paths for each venue, with separate physical demarcation points and diverse carriers where feasible.
- Documented IP addressing, VRFs, VLANs, routing policies, management isolation, and change control.
- End-to-end monitoring of application success, BGP, interface counters, optical diagnostics and time sync.
- A documented rollback for every routing/cross-connect change, and pre-arranged escalation ownership.
- No claim of microsecond stability until actually demonstrated with suitable physical equipment and synchronized clocks.

## 2. Logical and physical topology

```text
                          Venue-X                  Venue-Y
                         /       \                /       \
                  X-carrier-A  X-carrier-B   Y-carrier-A  Y-carrier-B
                      |           |             |           |
                  DC-A cross   DC-B cross   DC-A cross    DC-B cross
                      |           |             |           |
                  DC-A border-router      DC-B border-router
                         \                   /
                           private backbone
                          /                  \
                   trading-host-A        trading-host-B
```

**Physical diversity is a separate condition from BGP diversity.** Two BGP sessions carried over the same patch panel, provider or duct are not independent failure domains. During design review, explicitly identify shared power, racks, meet-me-rooms, ports, optics and carriers.

A real topology will also require redundant top-of-rack switching, dedicated out-of-band management, PTP grandmasters/time sources where appropriate, and clear separation of management and trading plane traffic.

## 3. Cross-connect provisioning checklist

1. Confirm each exchange/provider's delivery location (facility, meet-me room, demarc, port and media) and ordering process.
2. Obtain and review actual Letter of Authorization / Customer Facility Assignment (LOA/CFA) where the facility requires one.
3. Record connector/media type, wavelength, optic power budget, speed, FEC requirements, polarity, fiber pair and expected light levels. Do not assume any of these values.
4. Verify patching end to end and conduct physical link tests with both counterparties before enabling production protocol peering.
5. Define interface name, VLAN tagging, IP subnet, peer ASN, MTU, ACL requirements, BGP session protection and allowed advertised/received prefixes.
6. Apply route policies in a maintenance window with documented operator approval. Verify the provider-side config agrees with ours.
7. Archive provider ticket IDs and change history in an access-controlled system, not in a public Git repository.

## 4. Routing-policy design

- Use explicit BGP import/export prefix filters and max-prefix thresholds appropriate to real peer contracts.
- Model the intended route decision with local preference or routing policy; do **not** assume BGP measures or automatically prefers lower latency.
- Record both chosen RIB path and installed FIB path. Monitor session state, route acceptance and actual application reachability separately.
- Consider unequal path performance, asymmetric return paths, ECMP effects on flow hashing, and session stickiness when designing failover.
- Confirm timers and BFD support with both endpoints before enabling; aggressive timers can introduce false flap events.
- Use safe route dampening or maintenance procedures only after understanding their effects on recovery and correctness.

## 5. Low-latency measurement plan

Baseline before changes, repeat under stable load and record:
- Physical interface link state, errors, drops, FEC/CRC, optical power where supported.
- Linux `ethtool -S`, `ip -s link`, `ss -s`, `nstat`, `/proc/net/softnet_stat`, CPU affinity/IRQ placement.
- Application echo RTT distributions with full sample counts and timeout ratios, plus separate transaction timestamps at the venue if available.
- Independent packet captures on both sides (where authorized), with clocks aligned by verified PTP/hardware timestamps before claiming one-way latency.
- p50/p95/p99/p99.9, worst observed excursions and confidence/experiment count; avoid relying on the average alone.
- Baseline and change comparisons with matching payload size, rate, time windows and system load.

**Do not infer physical packet loss from a user-space echo timeout alone.** Verify capture coverage, NIC counters and application behavior.

## 6. Security and operational controls

- Separate trading, monitoring and OOB management traffic; limit management plane access with ACLs, authentication and audit logs.
- Permit only needed exchange endpoints and protocol ports, with explicit change control and security review.
- Coordinate DDoS controls with providers; validate their effect on path selection and latency.
- Restrict who can modify BGP policy; use peer-prefix allowlists and compare proposed policy against approved inventory.
- Prepare on-call escalation, timestamps in UTC, incident evidence retention and postmortem procedures.

## 7. Maintenance/rollback example (hypothetical)

**Pre-change:** approve change ticket, capture BGP peers/paths, kernel routes, link counters, application health, and verify backup service.

**Change:** provision a second physical circuit, verify light levels and IP reachability, establish and validate BGP on the new path without shifting primary traffic. Use staged policy changes only after both sides approve the path.

**Validation:** check accepted prefixes, next-hop reachability, return traffic, packet captures, RTT/timeout distributions and failover behavior at both endpoints. Verify no unexpected route leaks.

**Rollback triggers:** unexpected prefixes, blackholed traffic, elevated application failure ratio, time synchronization faults or unstable interface errors. Revert route-policy change, withdraw only newly introduced advertisements, restore the last approved configuration, and notify counterparties.

**Post-change:** document actual observed metrics with evidence and assign an owner for remaining risks.

## 8. Interview defense

**Q:** Does a redundant BGP session prove path independence? **A:** No, physical media/carrier and power diversity must be confirmed.

**Q:** What would you ask a data center before ordering a cross-connect? **A:** LOA/CFA, demarc and meet-me-room, fiber/optic specifications, service ownership, maintenance windows, expected lead time and acceptance tests.

**Q:** How do you prove the new circuit reduced latency? **A:** Measure under controlled matched conditions using validated timestamps and full tail distributions, not simulated values.

**Q:** What is this project's real-world evidence? **A:** It is a documented design exercise, connected conceptually to a functioning Docker BGP lab. It proves architectural reasoning, not colocation deployment or trading network operations.
