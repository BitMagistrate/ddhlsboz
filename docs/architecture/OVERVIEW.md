# RoadPulse — Architecture Overview

This document is the single-page mental model for the codebase. For deeper
treatment of any individual subsystem, follow the linked ADRs / READMEs.

## 1. One-paragraph summary

RoadPulse is Vietnam's flood-aware mobility intelligence layer. We ingest four
data feeds (VETC speed aggregates, Sentinel-1 SAR water masks, VNMS weather and
voluntary fleet SDK probes), fuse them through a privacy-preserving feature
store, and serve three product surfaces (B2C smart-trip app, B2B dashboards, and
a parametric-insurance trigger feed) on top of a flood-aware OSRM-shaped routing
engine. All MVP feeds are **synthetic-fixtures**; the contract surface is
production-ready.

## 2. Service map

```
                              ┌───────────────────┐
                              │   B2C app (Expo)  │ ◄────────┐
                              │ apps/b2c-app      │          │
                              └────────┬──────────┘          │
                                       │ /v1/route,         │
                                       │ /v1/flood-risk      │
                                       ▼                    │
┌────────────────┐   ┌────────────────────────────────────┐  │
│ B2B dashboard  │──►│         apps/api-gateway          │  │
│ apps/b2b-      │   │  FastAPI · pydantic · ulid traces │  │
│ dashboard      │   │  OpenAPI ◄─── schemas/openapi/    │  │
└────────────────┘   │  public_v1.yaml                   │  │
                     └───┬─────────────┬───────────────┬─┘  │
                         │             │               │    │
                         ▼             ▼               ▼    │
          ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
          │ routing-engine │  │  eta-service   │  │  flood-service │
          │ Dijkstra +     │  │ HGB + Quantile │  │ Isolation +    │
          │ profiles vn    │  │ k-fold MAPE    │  │ Bayes (SAR)    │
          └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
                  │                   │                   │
                  ▼                   ▼                   ▼
          ┌──────────────────────────────────────────────────────┐
          │           feature store (Redis-shaped)              │
          │           roadpulse_features.InMemoryFeatureStore   │
          └────────┬────────────────────┬───────────────────────┘
                   │                    │
                   ▼                    ▼
        ┌────────────────────┐ ┌──────────────────────┐
        │ ingestion-vetc     │ │ ingestion-weather    │
        │ ingestion-sar      │ │ ingestion-sdk        │
        │ (synthetic-fixtures│ │  collector           │
        │ replace post-MoU)  │ │                      │
        └────────────────────┘ └──────────────────────┘

                                     ┌──────────────────────┐
                                     │  trigger-feed        │
                                     │  Ed25519 signed      │
                                     │  events for insurers │
                                     └──────────────────────┘
```

## 3. Where each tier lives

| Layer            | Code path                                | Tech                              |
| ---------------- | ---------------------------------------- | --------------------------------- |
| HTTP gateway     | `apps/api-gateway`                       | FastAPI 0.110, pydantic v2        |
| Routing          | `apps/routing-engine` + `roadpulse_routing` | Dijkstra, profiles per vehicle   |
| ETA              | `apps/eta-service` + `roadpulse_ml.eta`  | HistGB + quantile GB ensemble     |
| Flood            | `apps/flood-service` + `roadpulse_ml.flood` | IsolationForest + Bayes fusion  |
| Tiles            | `apps/tile-server`                       | FastAPI vector tiles              |
| Trigger feed     | `apps/trigger-feed`                      | Ed25519 (`cryptography`)          |
| Ingestion        | `apps/ingestion-*`                       | Standalone Python processes       |
| Feature store    | `roadpulse_features`                     | Feast-shape; in-memory fallback   |
| Privacy moat     | `roadpulse_privacy`                      | KAnonGuard, PIIScrubber, audit    |
| Telemetry        | `roadpulse_telemetry`                    | structlog + trace context         |
| ML eval          | `ml/eval/harness.py`                     | k-fold MAPE, PR-AUC, routing      |
| Loadtest         | `tools/loadtest/route.js`                | k6 — p95 < 250 ms target          |
| B2B web          | `apps/b2b-dashboard`                     | React + Vite + deck.gl + Recharts |
| B2C mobile       | `apps/b2c-app`                           | Expo / React Native               |

## 4. Data flow on a single `/v1/route` call

1. Client POSTs JSON to `api-gateway`.
2. `roadpulse_telemetry.bind_request_context` mints a 26-char ULID trace id.
3. `PIIScrubber` validates the body — never accepts forbidden fields.
4. `state.nearest_node()` snaps origin / destination to the seeded graph.
5. `RoutingEngine.three_candidates()` runs Dijkstra three times (fast / safe /
   eco) with per-mode profiles and the flood/congestion penalty lookups.
6. For each candidate the gateway feeds an `ETARecord` to the trained
   `EtaModel` for `eta_s + p10/p90` and an `EcoModel` for `co2_g` / eco score.
7. The response includes a `flood_overlay` list from the live flood detector
   and a `weather_note` if any variant crosses a >0.6 score hex.
8. The gateway emits a `route.candidates` structlog event with the trace id.

## 5. Frontend stack

* **B2C app (`apps/b2c-app`)** — Expo + React Native + `@rnmapbox/maps`. The
  `/floods.tsx` screen renders the live overlay and animates wet hexes; the
  `/wallet.tsx` screen surfaces toll-paid history and eco-trip tags (no carbon
  credits — eco is a user-facing hint, never a revenue line).
* **B2B dashboard (`apps/b2b-dashboard`)** — React + Vite + Recharts +
  deck.gl. Each page (`flood-watch`, `dispatch`, `toll-yield`, `site-select`,
  `fleet-match`) shows a synthetic-data banner and at least one chart that
  consumes the matching `/v1` endpoint.

## 6. Where we draw the trust line

```
[ public clients ] ◄── /v1/* (OpenAPI-checked) ─── [ api-gateway ]
                                                       │
[ partner real feeds ] ─── ingestion ──► PIIScrubber ──┤
                                       └─ KAnonGuard ──┘
                                          ▼
                                   feature store
                                          ▼
                                  ML models + engine
                                          ▼
                                  data_origin: synthetic|real
```

* PII never crosses the scrubber.
* Aggregates never leave the KAnonGuard unless `k ≥ 50`.
* Every endpoint always declares its `data_origin` so the demo and a real-feed
  prod build can never be confused at the wire.

## 7. Operational defaults

| SLA                   | Target          | Verified by                |
| --------------------- | --------------- | -------------------------- |
| `/v1/route` p95       | < 250 ms        | `make load`                |
| ETA MAPE              | ≤ 18 %          | `make test.ml.eval`        |
| Flood PR-AUC          | ≥ 0.85          | `make test.ml.eval`        |
| Three-variant overlap | ≤ 0.95 on seed  | `make test.ml.eval`        |
| Test coverage         | 97 tests pass   | `make test`                |
| Lint                  | ruff clean      | `make lint`                |
| Type-check            | mypy strict     | `make typecheck`           |

## 8. Outside the box

The repo intentionally **does not** implement:

* Carbon credits / Verra / Gold Standard issuance — eco is a user hint only.
* Real VETC data ingestion — synthetic-fixtures until the MoU is signed.
* Blockchain anchoring — Ed25519 signatures on the trigger feed are enough.
* In-house legal review — see `docs/compliance/PRIVACY_BRIEF.md` § 5.
