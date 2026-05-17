# RoadPulse

> Vietnam's flood-aware mobility intelligence — built on VETC.

RoadPulse is a routing & mobility intelligence layer for Vietnam. It combines anonymised
VETC aggregates, Sentinel-1 SAR water-masks, weather feeds and a voluntary fleet SDK into
a flood-aware OSRM routing engine, ETA models, a B2C "Smart Trip" app and B2B dashboards
(Dispatch, Toll Yield, Site Selection, Fleet Match).

This repository is the full Skolkovo × TASCO Smart Mobility pitch implementation:

- Backend `api-gateway` (FastAPI) implementing all public `/v1/*` endpoints from
  `schemas/openapi/public_v1.yaml`.
- Internal services: `routing-engine`, `eta-service`, `flood-service`, ingestion
  pipelines (`vetc`, `weather`, `sar`, voluntary SDK), `trigger-feed`, `tile-server`,
  `ops-tools`.
- Python packages (`packages/python/*`): `roadpulse_core`, `roadpulse_privacy`,
  `roadpulse_features`, `roadpulse_routing`, `roadpulse_ml`, `roadpulse_telemetry`.
- TypeScript packages (`packages/ts/*`): generated API client, deck.gl map layers,
  shared UI design-system and VETC Pay SDK wrapper.
- Apps: `b2c-app` (Expo / React Native) and `b2b-dashboard` (React + Vite + deck.gl).
- Proto and Avro schemas (`proto/`, `schemas/`), OpenAPI source of truth in
  `schemas/openapi/public_v1.yaml`.
- Infrastructure as code (`infra/`): Terraform, Helm charts, Argo CD ApplicationSets,
  environment overlays.
- ML harness (`ml/`): training pipelines, MAPE & flood PR/ROC eval, model registry.
- Tooling, ADRs, runbooks and data dictionary (`tools/`, `docs/`).

## Quick start (local dev)

Pre-requisites: Linux/macOS, Docker ≥ 24, `make`, Python 3.12, Node 20 LTS, `pnpm ≥ 9`.

```bash
make bootstrap   # uv sync, pnpm install, pre-commit install
make seed        # generate 7 days of HCMC + Hanoi VETC fixtures, SAR mask, OSM extract
make up          # docker compose: postgres+postgis, redis, redpanda, minio, mlflow
make dev.api     # FastAPI api-gateway with reload at http://localhost:8000
make dev.web     # B2B dashboard at http://localhost:5173
make dev.b2c     # Expo dev server for the B2C app
```

Run the full quality gate:

```bash
make lint       # ruff + biome
make typecheck  # mypy + tsc --noEmit
make test       # pytest + vitest + contract checks
```

## Repo layout

```
apps/         runnable services (FastAPI, ingestion daemons, RN, web)
services/     long-lived in-cluster components (OSRM, Valhalla, Feast, Airflow, tiles)
packages/     reusable libraries (python + ts)
proto/        Buf-managed gRPC + Kafka contracts
schemas/      Avro + OpenAPI source of truth
infra/        Terraform, Helm, Argo CD, env overlays
ml/           training pipelines, eval harness, registry
tools/        CLI helpers (seed, k-anon audit, replay)
docs/         ADRs, runbooks, data dictionary, full pitch
```

## Privacy by design

RoadPulse never ingests PII. Every public bucket is guarded by
`roadpulse_privacy.KAnonGuard(min_k=50, time_window_s=300)` and every input/output is
validated against `roadpulse_privacy.PIIScrubber`. Violations are dropped and audited in
the `audit.kanon.violations` Kafka topic. See
[docs/compliance/privacy.md](docs/compliance/privacy.md).

## Licence

Source code is released under the Apache 2.0 licence (`LICENSE`).

## Pitch

The full Skolkovo × TASCO pitch (RU + EN) is in [docs/pitch.md](docs/pitch.md). The
presentation prompt (for generating slides separately) is in
[PRESENTATION_PROMPT.md](PRESENTATION_PROMPT.md).
