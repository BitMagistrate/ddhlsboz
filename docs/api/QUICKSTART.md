# RoadPulse Public API — Quickstart

> RoadPulse exposes a flood-aware mobility intelligence layer for Vietnam.
> All `/v1` endpoints currently serve **synthetic-fixtures** data — the public
> contract is locked, but the underlying feeds are demo data. Every response
> includes a `data_origin` flag so you can never confuse the demo with a real
> deployment.

The OpenAPI source of truth lives in
[`schemas/openapi/public_v1.yaml`](../../schemas/openapi/public_v1.yaml).
A Postman collection ready to import is at
[`postman_collection.json`](postman_collection.json).

## 1. Start the API locally

```bash
git clone https://github.com/BitMagistrate/ddhlsboz roadpulse
cd roadpulse
make bootstrap            # uv venv + python deps + pnpm install
make up                   # docker compose (postgres, redis, redpanda)
make dev.api              # uvicorn at http://localhost:8000
```

The api-gateway boots with the seeded HCMC graph + an in-memory feature store +
the IsolationForest / quantile-LightGBM models pre-trained on `data/seed/`. It
takes ~3s to come up on a 4-core laptop.

Verify the data origin:

```bash
curl -s http://localhost:8000/v1/healthz | jq
# {
#   "status": "ok",
#   "version": "0.1.0",
#   "data_origin": "synthetic",
#   "real_feeds": [],
#   "pending_real_feeds": [
#     "vetc.hex.5min",
#     "sentinel1.sar.water_mask",
#     "vnms.weather.hourly",
#     "fleet_sdk.probes"
#   ]
# }
```

## 2. Authentication

Every request must carry an API key in the `X-Api-Key` header. The demo
fixtures ship with one key per org bucket — see `data/seed/orgs.json`:

```bash
export RP_API_KEY="demo_synthetic_key"
```

If you forget the header, the gateway falls back to the public `b2c` tier so
the demo always renders something. Real-feed deployments will reject missing
keys with `401`.

## 3. The endpoints you need to know

### `POST /v1/route` — three-variant flood-aware route

Returns Fast / Safe / Eco variants for a single trip, with the live
flood-overlay polygons and a weather note when relevant:

```bash
curl -s http://localhost:8000/v1/route \
  -H "X-Api-Key: $RP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "origin":      {"lat": 10.820, "lng": 106.645},
    "destination": {"lat": 10.754, "lng": 106.733},
    "mode": "motorbike",
    "avoid_flood": true
  }' | jq '.variants[].name'
# "fast"
# "safe"
# "eco"
```

p95 latency is < 250 ms on the seed graph (`make load` runs k6 against this
endpoint and writes a summary to `docs/demo/loadtest-results.txt`).

### `POST /v1/eta-batch` — fleet ETA prediction (≤ 50 000 orders / call)

```bash
curl -s http://localhost:8000/v1/eta-batch \
  -H "X-Api-Key: $RP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "batch_id": "demo_001",
    "items": [
      {"order_id": "ord_001",
       "origin":      {"lat": 10.820, "lng": 106.645},
       "destination": {"lat": 10.754, "lng": 106.733}}
    ]
  }' | jq '.predictions[0]'
```

### `POST /v1/isochrone` — reachable-area polygons

```bash
curl -s http://localhost:8000/v1/isochrone \
  -H "X-Api-Key: $RP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": {"lat": 10.780, "lng": 106.700},
    "minutes": [5, 10, 15]
  }' | jq '.rings | length'
# 3
```

### `GET /v1/flood-risk?horizon=now|1h|3h|6h` — H3 hexes with flood scores

```bash
curl -s "http://localhost:8000/v1/flood-risk?horizon=6h" \
  -H "X-Api-Key: $RP_API_KEY" | jq '.hexes[0:2]'
```

### `POST /v1/site-selection` — top-N hexes within a bbox for a target audience

```bash
curl -s http://localhost:8000/v1/site-selection \
  -H "X-Api-Key: $RP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "bbox": [106.64, 10.73, 106.78, 10.83],
    "audience": "retail"
  }' | jq '.top_cells[0]'
```

### `POST /v1/fleet-match` — match a pickup/dropoff to fleet operators

```bash
curl -s http://localhost:8000/v1/fleet-match \
  -H "X-Api-Key: $RP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "pickup":  {"lat": 10.780, "lng": 106.700},
    "dropoff": {"lat": 10.754, "lng": 106.733},
    "weight_kg": 800,
    "volume_m3": 5,
    "mode": "truck"
  }' | jq '.candidates[0]'
```

### `GET /v1/trigger-feed/{policy_id}` — Ed25519-signed parametric events

Used by the parametric flood insurance reference integration. Each event
carries a `payload_signature` you can verify against the per-policy public key
returned by `GET /v1/trigger-feed/{policy_id}/pubkey`.

```bash
curl -s http://localhost:8000/v1/trigger-feed/policy_pti_d1_flood_2024 \
  -H "X-Api-Key: $RP_API_KEY" | jq '.events[0]'
```

## 4. Error envelopes

All errors share the same shape:

```json
{
  "detail": "origin and destination map to the same graph node"
}
```

* `400` — request body validation failed
* `404` — referenced policy / org does not exist
* `422` — the routing graph cannot satisfy this request (origin or destination
  has no path under the requested profile)
* `429` — rate-limit hit (demo cap is 60 req/min/key, controlled by Redis)
* `5xx` — transient internal error; safe to retry with exponential backoff

## 5. Generated SDKs

The OpenAPI document is regenerated from the FastAPI app every commit (see
`tools/gen_openapi.py`). Use the standard `openapi-typescript` or
`datamodel-code-generator` pipeline to produce typed clients:

```bash
npx openapi-typescript schemas/openapi/public_v1.yaml -o /tmp/roadpulse.d.ts
```

## 6. What's real vs synthetic right now

| Feed                            | Status (today)          | Path to real        |
| ------------------------------- | ----------------------- | ------------------- |
| HCMC routing graph              | Synthetic (63 nodes)    | OSM extract + STR tree |
| VETC speed aggregates           | Synthetic fixtures      | MoU with VETC JSC   |
| Sentinel-1 SAR water-mask       | Synthetic fixtures      | Copernicus DIAS API |
| VNMS hourly weather             | Synthetic fixtures      | VNMS open data feed |
| Fleet SDK probes                | Synthetic fixtures      | Voluntary partner SDK |
| Trigger feed (PTI policies)     | Synthetic, signed       | Live once MoU signed |

When a feed flips to real, the operator sets `ROADPULSE_REAL_FEEDS=vetc.hex.5min`
in the environment; the `data_origin` field on every endpoint flips to `real`
and the feed leaves `pending_real_feeds`.

## 7. Where to go from here

* [Architecture overview](../architecture/OVERVIEW.md)
* [Privacy + security one-pager](../compliance/PRIVACY_BRIEF.md)
* [ML eval harness](../../ml/eval/harness.py) — quotes MAPE / PR-AUC numbers
* [Loadtest harness](../../tools/loadtest/route.js) — proves p95 < 250 ms
* [Pitch deck source](../pitch/roadpulse_pitch.md)
* [Demo script](../demo/SCRIPT.md)
