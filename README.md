# RoadPulse

> **Vietnam's flood-aware mobility intelligence layer.**
> Three-variant routing (fast / safe / eco), batch ETA, isochrones,
> flood-risk hex tiles, site-selection and fleet matching — all behind a single
> OpenAPI surface and an Ed25519-signed trigger feed for parametric insurance.

[![pitch — Skolkovo × TASCO Smart Mobility](https://img.shields.io/badge/pitch-Skolkovo%20%C3%97%20TASCO-2563eb)](docs/pitch/roadpulse_pitch.md)
[![status — synthetic-fixtures](https://img.shields.io/badge/data_origin-synthetic--fixtures-f59e0b)](docs/api/QUICKSTART.md#6-whats-real-vs-synthetic-right-now)
[![tests — 97](https://img.shields.io/badge/tests-97%20green-16a34a)](#quality-gates)
[![route p95 — < 250 ms](https://img.shields.io/badge/route_p95-<250ms-16a34a)](docs/demo/loadtest-results.txt)
[![security — SECURITY.md](https://img.shields.io/badge/security-SECURITY.md-0f172a)](SECURITY.md)

This repository is the complete Skolkovo × TASCO Smart Mobility pitch
implementation — backend, mobile app, operator dashboards, ML pipelines,
infrastructure and docs. Every public endpoint is reproducible from seed data
in under five minutes on a laptop.

## 1. What's in the box

| Layer            | Path                                  | What it does                                            |
| ---------------- | ------------------------------------- | ------------------------------------------------------- |
| Public API       | `apps/api-gateway`                    | FastAPI service implementing every `/v1/*` route        |
| Routing          | `apps/routing-engine` + `packages/python/roadpulse_routing` | flood-aware Dijkstra w/ per-mode profiles |
| ETA              | `apps/eta-service` + `packages/python/roadpulse_ml/eta.py`  | HistGB + quantile MAPE forecaster        |
| Flood            | `apps/flood-service` + `roadpulse_ml/flood.py`              | IsolationForest + Bayes SAR fusion       |
| Ingestion        | `apps/ingestion-{vetc,sar,weather,sdk-collector}`           | synthetic feeds today; pluggable real feeds |
| Trigger feed     | `apps/trigger-feed`                                         | Ed25519-signed parametric events         |
| B2C mobile       | `apps/b2c-app` (Expo / React Native)                        | Smart-Trip app, flood overlay, VETC Pay  |
| B2B web          | `apps/b2b-dashboard` (Vite + Recharts)                      | Dispatch, Flood watch, Toll yield, Site, Fleet |
| ML eval          | `ml/eval/harness.py`                                        | k-fold MAPE, PR-AUC, routing overlap     |
| Loadtest         | `tools/loadtest/route.js`                                   | k6 — p95 < 250 ms target                 |
| Privacy moat     | `packages/python/roadpulse_privacy`                         | k-anon ≥ 50, PII scrubber, audit ring    |
| Infra            | `infra/{terraform,helm,argocd}`                             | env overlays, ApplicationSets            |
| Docs             | `docs/{api,architecture,compliance,demo,pitch}`             | quickstart, brief, demo script, deck     |

## 2. Quick start (5 minutes)

Pre-requisites: Linux/macOS, Docker ≥ 24, `make`, Python 3.11, Node 20 LTS,
`pnpm ≥ 9`.

```bash
make bootstrap   # uv sync, pnpm install, pre-commit install
make seed        # generate the HCMC + Hanoi fixtures, SAR mask, OSM extract
make up          # docker compose: postgres+postgis, redis, redpanda, minio, mlflow
make dev.api     # FastAPI api-gateway with reload at http://localhost:8000
make dev.web     # B2B dashboard at http://localhost:5173
make dev.b2c     # Expo dev server for the B2C app
```

Confirm the API is serving synthetic data:

```bash
curl -s http://localhost:8000/v1/healthz | jq .data_origin
# "synthetic"
```

See [`docs/api/QUICKSTART.md`](docs/api/QUICKSTART.md) for the complete public
contract and a ready-to-import [Postman collection](docs/api/postman_collection.json).

## 3. What's real vs synthetic (today)

| Feed                            | Status              | Path to real             |
| ------------------------------- | ------------------- | ------------------------ |
| HCMC routing graph              | Synthetic, 63 nodes | OSM HCMC extract         |
| VETC speed aggregates           | Synthetic fixtures  | MoU with VETC JSC        |
| Sentinel-1 SAR water-mask       | Synthetic fixtures  | Copernicus DIAS API      |
| VNMS hourly weather             | Synthetic fixtures  | VNMS open data feed      |
| Fleet SDK probes                | Synthetic fixtures  | Voluntary partner SDK    |
| Trigger feed (PTI policies)     | Synthetic, signed   | Live once MoU signed     |

Every `/v1` response carries a `data_origin` field. Operators can flip a feed
to real by setting `ROADPULSE_REAL_FEEDS=<canonical_name>` in the environment.

## 4. Quality gates

```bash
make lint       # ruff + biome
make typecheck  # mypy + tsc --noEmit
make test       # pytest (97 tests) + vitest + contract checks
make test.ml.eval   # k-fold MAPE, flood PR-AUC, routing overlap (ml/eval/results.json)
make load       # k6 loadtest — writes docs/demo/loadtest-results.txt
```

Current numbers from `make test.ml.eval`:

| Metric                              | Target          | Latest    |
| ----------------------------------- | --------------- | --------- |
| ETA MAPE                            | ≤ 0.18          | 0.0385    |
| ETA p10/p90 coverage                | ≥ 0.75          | 0.7700    |
| Flood PR-AUC                        | ≥ 0.85          | 0.9474    |
| Three-variant routing overlap       | ≤ 0.95 on seed  | 0.9143    |

Current numbers from `make load`:

| Metric                | Target          | Latest    |
| --------------------- | --------------- | --------- |
| `/v1/route` p95       | < 250 ms        | 187.42 ms |
| Error rate            | < 1 %           | 0 %       |
| Iterations            | n/a             | 4218      |

## 5. Architecture

* Single-page overview: [`docs/architecture/OVERVIEW.md`](docs/architecture/OVERVIEW.md)
* Privacy + security brief: [`docs/compliance/PRIVACY_BRIEF.md`](docs/compliance/PRIVACY_BRIEF.md)
* Disclosure policy: [`SECURITY.md`](SECURITY.md)

## 6. Demo

The 90-second reproducible demo script lives at
[`docs/demo/SCRIPT.md`](docs/demo/SCRIPT.md). It walks through:
B2C smart-trip → B2B flood-watch → toll yield → fleet match → signed trigger
feed, ending on the `data_origin: synthetic` flag.

## 7. Privacy by design

RoadPulse never ingests PII. Every public bucket is guarded by
`roadpulse_privacy.KAnonGuard(min_k=50, time_window_s=300)` and every
input/output is validated against `roadpulse_privacy.PIIScrubber`. Violations
are dropped and audited in `audit.kanon.violations`. The
[privacy brief](docs/compliance/PRIVACY_BRIEF.md) is the single-page
explainer for jury and DPOs.

## 8. Licence

Source code is released under the Apache 2.0 licence (`LICENSE`).

## 9. Pitch & contacts

The full Skolkovo × TASCO pitch (RU + EN) is in
[`docs/pitch/roadpulse_pitch.md`](docs/pitch/roadpulse_pitch.md). The slide
generator prompt is at [`PRESENTATION_PROMPT.md`](PRESENTATION_PROMPT.md).

Team: Vladimir Ermolenko & Sergey Karelin — `security@roadpulse.dev`.
