## Windows GitHub publisher compatibility fix (2026-10-27)

- Fixed the evidence ZIP unit test to use byte-exact test fixtures on both Windows (CRLF) and Linux (LF).
- Regression coverage validates that original JSON bytes and SHA-256 checksums are unchanged in the ZIP.
- The application configuration, BGP policies, network lab, and collected field evidence are unchanged.
- The previous upload attempt stopped at the offline tests; no Git push took place.

---

# BGP Routing Laboratory — v0.4 (2026-10-27)

## Evidence received and checked

- Reviewed the participant-supplied `BGP_Evidence_v0.2.zip` (four real JSON files), preserved verbatim outside public source control.
- Validated four-router snapshot data: eight directional BGP peers Established, appropriate 4 ASNs, correct primary/backup next hops and local preferences, primary BGP paths reported installed, post-test unauthorized prefix absent at endpoints.
- Confirmed failover, baseline and filtering JSON fields and documented exact observed durations **with their methodological limitations**.
- Published a concise, derived evidence report with original SHA-256 hashes under `docs/evidence-summary-2026-10-27.json`. No private raw snapshot embedded in this repository.
- Added `scripts/verify_evidence.py`, an independent, standard-library offline evidence validator, plus six synthetic-fixture tests.
- Updated English field report, validation status, README and GitHub publication guide.
- Preserved all working v0.2 FRRouting configurations and Docker Compose networks unchanged; no new workstation Docker run of v0.4 claimed.

## Important limitations

A successful BGP bestpath transition observed by Docker + CLI polling is not packet-level outage duration, nor HFT-grade data-plane latency. Snapshot was taken after primary transit recovery; the failover-in-progress observation is recorded separately. GitHub Actions static and manual integration workflows are not yet verified by GitHub.

---

# BGP Routing Laboratory — v0.3 (2026-10-27)

## Confirmed on the user's Windows 11 / Docker Desktop workstation

- Four FRR containers started and eight eBGP neighbor perspectives Established.
- `check`: correct primary bestpaths and two-way sourced ICMP PASS.
- `failover`: backup path selected on both endpoints, sourced ICMP stayed reachable in the post-failure test, and preferred path recovered after restart.
- `filter`: locally injected `198.18.0.1/32` present at primary transit and absent at edge/core during test observation window.
- `collect`: four-router diagnostic JSON snapshot written on user's workstation.
- Raw JSON files were **not** provided to the archive author; results are transcribed from screenshots.

## Package changes (no FRR configuration changes)

- English field report with evidence provenance, environment, regression history, and timing limitations.
- README and verification matrix brought up to date with observed runtime results.
- Added standard-library `bundle` CLI to ZIP unchanged user-side `artifacts/*.json` with a SHA-256 manifest; unit tests for success, missing evidence, and corrupt JSON.
- Offline unit tests: see executed build validation for this package. Live Docker v0.3 runtime not independently rerun (routing config unchanged from successful v0.2 run).

---

# BGP Routing Laboratory — v0.2 (2026-10-27)

## Changes based on the first real Windows run

- Preserve the complete four-AS FRR topology and BGP policies.
- Replace `internal: true` Docker networks with per-link user-defined Docker
  bridges and `enable_ip_masquerade: false`, to test whether internal bridge
  filtering prevented traffic to/from the two loopback /32s.
- Add the read-only `diagnose` command. Collect kernel routes, forwarding
  sysctls, FRR RIB and neighbor state, six ICMP probes (including failures),
  and a UTC-stamped JSON artifact.
- Add unit tests for the diagnostic failure capture and CLI registration.
- Document the observed v0.1 runtime success and failure separately from the
  unverified v0.2 hypothesis.

## Evidence status

v0.1 user's Docker Desktop run: four services Up; eight BGP neighbor perspectives
Established; primary path selected at edge and core; **2/2 sourced ICMP packets
lost** from edge to core. v0.2 has not been run on Docker yet in the author's
environment. Do not claim route forwarding or failover is verified.

## Running v0.2 after v0.1

Run `docker compose down` in the old folder, extract the new ZIP to a new folder,
then `docker compose up -d`, `py -3 .\scripts\labctl.py diagnose` and
`py -3 .\scripts\labctl.py check --timeout 120` in the new folder.

---

# BGP Routing Laboratory — v0.1 (2026-10-27)

## Shipped

- Four FRRouting v10.7.1 routers across four isolated Docker bridges; explicit private ASNs and IPAM addresses.
- Independent primary/backup transit with local-preference controls on both endpoints.
- Prefix allowlists and in/out route maps on eight eBGP neighbor perspectives.
- A standard-library Python controller: preflight, up/down, status, check, failover, filter, collect.
- Bidirectional sourced ICMP on loopback /32 service prefixes.
- UTC-stamped output artifacts for baseline, route-policy and failover observations.
- Offline unit/config/parser tests; GitHub Actions static CI and manual Docker integration workflow.
- English runbook, architecture, interview notes, validation and GitHub publication instructions.

## Offline validation of this release

- Python unit tests: 22 / 22 passed (no Docker required).
- Python syntax compile: passed.
- Independent YAML parsing: passed (four services and four networks).

## Pending runtime validation

The artifact was built without access to a Docker Engine. Therefore no FRR startup, real BGP adjacency, forwarding, Linux route installation, route-policy rejection, or failover result has been measured. These tests are provided as executable scripts but not claimed as passed. Follow `docs/validation.md` and update the results with actual evidence.
