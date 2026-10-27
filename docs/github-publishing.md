# GitHub publication — BGP Routing Laboratory

## Repository name and description

**Repository:** `bgp-routing-laboratory`

**Description:** `Reproducible four-AS BGP routing and failover lab using FRRouting, Docker Compose, Python, route filtering, and independently reviewed workstation evidence.`

Suggested topics: `network-engineering`, `bgp`, `frrouting`, `docker`, `python`, `network-automation`, `routing`, `failover`.

## Pre-publication review

- Confirm that you extracted v0.4 and that `compose.yaml` is at the project root.
- The raw `BGP_Evidence_v0.2.zip` and full `artifacts/` folder should **not** be committed. The repository intentionally includes only a derived, checkable summary under `docs/evidence-summary-2026-10-27.json` with SHA-256 hashes of the original four JSON files.
- Personal credentials, private host paths, tokens and real employer names should never be added to commits.
- The proof belongs to a *portfolio lab*, not employment, live exchange connectivity, or data-plane latency benchmark.

## Verify and publish from the v0.4 directory

```powershell
py -3 -m unittest discover -s tests -v
# Optionally, place the private evidence ZIP in .\artifacts\ before verification:
py -3 .\scripts\verify_evidence.py .\artifacts\BGP_Evidence_v0.2.zip
# If you do not have the evidence ZIP in the new folder, omit that step.
git init
git branch -M main
git add .
git status --short
git commit -m "Build reproducible FRRouting BGP failover lab with validated evidence"
```

Create an empty GitHub repository with the suggested name **without** creating a remote README/license (already included locally). Then add it and push:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/bgp-routing-laboratory.git
git push -u origin main
```

Replace `YOUR_USERNAME` with the username on your actual GitHub account. Do not copy a GitHub token into source files or screenshots. If Git is not installed, the GitHub web UI can upload the non-private project files instead.

GitHub Actions static workflow runs on push. The Docker integration workflow is **manual** (`workflow_dispatch`) and should be run explicitly after reviewing its effects. Their results must be documented separately; no CI success is claimed from workstation evidence.

## Interview-ready description

> Built an isolated 4-AS BGP routing lab with FRRouting and Docker Compose, automated neighbor/bestpath and sourced-ICMP checks, demonstrated primary-to-standby path selection and recovery, and tested strict prefix export policies. Collected real FRR snapshots on Windows Docker Desktop and wrote an independent offline evidence validator. The experiment does not measure packet-level outage duration or exchange-grade latency.
