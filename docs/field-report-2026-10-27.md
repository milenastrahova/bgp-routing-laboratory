# Workstation validation report — 27 October 2026

**Project:** BGP Routing Laboratory · **FRRouting image:** `quay.io/frrouting/frr:10.7.1` · **Docker Engine:** 29.9.2 (Windows 11 / Docker Desktop WSL2 backend).

## Provenance and reproducibility

A participant ran v0.2 on their own Windows 11 machine and supplied four original JSON files bundled as `BGP_Evidence_v0.2.zip`. These are **real user-supplied laboratory artifacts**, reviewed offline for this v0.4 publication package. They were **not generated** by the archive author, and no Docker or FRR runtime was available in the packaging environment. Independent verification means the four documents were parsed and checked for **internal consistency**; it does not cryptographically establish where or how they were created.

The original ZIP and full four-router snapshot **are not included in the public project**, to avoid unnecessarily distributing runtime environment/configuration details. The files' SHA-256 checksums and an attributable subset of their contents are in [`evidence-summary-2026-10-27.json`](evidence-summary-2026-10-27.json). Verification is reproducible with the unchanged private ZIP:

```powershell
py -3 .\scripts\verify_evidence.py .\BGP_Evidence_v0.2.zip
```

Use `--output .\artifacts\verification.json` to export a derived machine-readable report; it does **not** change the original evidence.

## Observations in the supplied JSON

| UTC recorded in JSON | Artifact | Directly recorded finding |
|---|---|---|
| 2026-10-27 15:32:54 | `baseline-20261027T153254Z.json` | `status: PASS`; edge preferred `10.255.10.3`, core preferred `10.255.30.2`; total baseline check `3.406 s`, **not** network RTT |
| 2026-10-27 15:34:58 | `failover-20261027T153458Z.json` | `backup_path_observed: true`; observed control-plane/CLI time `0.516 s`; poll interval `0.5 s`; full experiment reported `11.969 s`; `failure_detail: null` |
| 2026-10-27 15:36:34 | `filter-20261027T153634Z.json` | `status: PASS`; injection `198.18.0.1/32` at `transit_primary`; absent at both endpoints during the observation; `observation_seconds: 5.578` |
| 2026-10-27 15:37:02 | `snapshot-20261027T153705Z.json` | Four router snapshots, each with FRR BGP table, summary, FRR route table, running config and version. Eight directional peering perspectives were all `Established` at snapshot time. |

The snapshot records two candidate routes on each endpoint after restoration:

| Receiver | Destination | Selected primary | Local Preference | Standby | Local Preference |
|---|---|---|---:|---|---:|
| `edge` (AS65010) | `10.40.40.1/32` | via `10.255.10.3` (AS65020) | 200 | via `10.255.20.3` (AS65030) | 100 |
| `core` (AS65040) | `10.10.10.1/32` | via `10.255.30.2` (AS65020) | 200 | via `10.255.40.2` (AS65030) | 100 |

Both selected BGP routes were marked `selected: true` and `installed: true` in the collected `show ip route json` output (FRR's route/FIB status reporting). That confirms *reported installation* at snapshot time, not independent hardware forwarding telemetry. The unauthorized prefix was absent from edge/core BGP tables **in the post-test snapshot** as well.

## What the JSON cannot prove alone

- The snapshot was collected **after** the primary path had been restored. It cannot independently show the backup bestpath while the primary container was stopped. The separate `failover` JSON says a backup path was observed; user-provided terminal output additionally showed **both** endpoints selecting the standby path, responding to the post-failure ICMP checks, and returning to primary after restart.
- Two-way ICMP outcomes are shown by the user's terminal log. The provided JSON **does not contain packet-by-packet timestamps**, full ping output, or a continuous latency/loss series.
- `0.516 s` includes Docker stop and CLI polling and is **not** a measured data-plane outage duration. The `5.12 s` shown in terminal output after restoration is a **peer-established polling observation**, not physical link failover.
- The `5.578 s` filter metric covers injection/observation operations; a finite absence check is **not** a universal safety guarantee against route leaks.
- No claims about live trading systems, commercial operations, production throughput, millisecond/microsecond/nanosecond forwarding, jitter, sustained loss or HFT performance are made.

## Regression and limitations

The first v0.1 Windows run established BGP sessions, but a sourced loopback ICMP test failed (two packets lost). v0.2 changed the Docker bridge configuration, and all subsequent user-run baseline, failover and filter checks passed. This is a confirmed remediation; the precise v0.1 packet-drop mechanism was **not** established through packet capture.

GitHub Actions CI and the manual GitHub-hosted Docker integration workflow have **not** been run as part of these evidence artifacts. CI verification is separate from workstation verification. Source JSON is ignored under `artifacts/` to prevent accidental publication.
