# ADR-0004 — OSRM (MLD) with custom Lua profiles for routing

* Status: Accepted
* Date: 2026-01-18
* Deciders: CTO, Chief Data Officer

## Context

We need a fast routing engine that supports per-edge weight updates every 5
minutes without rebuilding the contraction hierarchy. Candidates: OSRM
(MLD), Valhalla, GraphHopper, custom.

## Decision

Use OSRM 5.27 with the **Multi-Level Dijkstra** (MLD) algorithm and three
custom Lua profiles (`motorbike-vn`, `car-vn`, `truck-vn`). Live
traffic + flood signals are pushed via `osrm-customize --segment-speed-file
traffic.csv` every 5 minutes — sub-second on HCMC.

The cost formula `cost = free_flow × (1 + α·cong + β·flood + γ·eco)` is
mirrored exactly in `roadpulse_routing.profiles` so the Python fallback
returns identical paths when OSRM is offline.

## Consequences

* Cold-build of HCMC tile takes ~6 minutes; runtime memory ~3.5 GB.
* Two replicas behind a Kubernetes Service; rolling restart on profile
  changes is automated by the `osrm-rebuilder` CronJob.
* When OSRM is offline the api-gateway transparently falls back to the
  in-process Python graph — slow but correct.
