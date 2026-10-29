# Technical defense guide — BGP Routing Laboratory

This is a four-AS educational routing lab with live FRRouting inside Docker namespaces. It is not a production HFT deployment and it does not establish a microsecond convergence time.

## Demonstration flow

1. Draw the diamond: Edge AS65010 connects to Core AS65040 through primary AS65020 or backup AS65030.
2. Show `show bgp ipv4 unicast summary` and explain why **Established** only confirms control-plane peering.
3. Show `show bgp ipv4 unicast 10.40.40.1/32` on Edge. Explain primary inbound Local Preference 200 and backup 100; BGP does **not** automatically select the lowest-latency link.
4. Show `ip -4 route get 10.40.40.1` to distinguish FRRouting RIB from Linux kernel forwarding.
5. Demonstrate route filters from `configs/edge/frr.conf`; explain inbound/outbound allowlists and the intentionally blocked 198.18.0.1/32.
6. Only in an authorized isolated Docker project, run controlled failover, verify both paths, and restore. Never disrupt shared or production infrastructure.
7. Walk through a JSON evidence file, identifying the measurement boundary. A Python polling timestamp is not actual outage duration.

## Interview questions

- Why use eBGP rather than iBGP for the four private ASes?
- What happens if the BGP session is Established but no routes are accepted?
- What is the difference between a RIB and a FIB?
- How can a route exist in FRR but not forward packets through Linux?
- Why does Local Preference override a shorter AS_PATH? Is Local Preference sent to eBGP peers?
- What does the route-map implicit deny prevent, and where might a route leak still occur?
- Why is a healthy ping insufficient proof that the latency-sensitive application is working?
- How would you evaluate BFD, ECMP, multiple failures, asymmetric paths and MTU problems?
- What does Docker virtualization invalidate as a measurement of physical NIC behavior?

## Known boundaries and next engineering experiments

No physical switches or carrier circuits, no PTP/hardware timestamping, no DPDK, no optical cross-connects, no production traffic. To strengthen diagnostic skills, practice next-hop reachability, asymmetric failure and packet capture on isolated interfaces. For higher-fidelity measurement integrate actual packet captures and independent observer clocks; do not label current results as wire-level convergence.

## Source integrity

Original supplied field reports are represented by sanitized summaries and SHA-256 references. The original private artifacts remain excluded from the repository. GitHub workflow success confirms the specified CI tests, not every possible routing or security scenario.
