# Build Week — day-by-day checklist

Five engineers, five days. End state: a working flood-aware routing MVP
demoed end-to-end at the Friday review.

## Day 1 — Infrastructure & ingestion

* [ ] `make bootstrap && make up` works on every engineer's laptop
* [ ] Postgres + PostGIS + h3 extension up; `infra/postgres/init/*.sql` runs
* [ ] Redpanda + MinIO + ClickHouse healthy in `compose.dev.yaml`
* [ ] OSRM tile rebuilt with `motorbike-vn` Lua profile
* [ ] React Native scaffold builds for both Android & iOS Expo Go

## Day 2 — Baseline ETA

* [ ] `roadpulse_ml.eta.EtaModel` trains on 90 days of synthetic VETC + weather
* [ ] MAPE ≤ 15% vs OSRM-only baseline on held-out 5-day window
* [ ] Feast online (Redis) & offline (S3 parquet) stores populated
* [ ] `POST /v1/eta-batch` returns predictions for a 100-order batch

## Day 3 — Flood-aware routing

* [ ] `roadpulse_ml.flood.FloodDetector` fits Isolation Forest + Bayesian SAR
* [ ] OSRM consumes the live traffic CSV every 5 min
* [ ] `POST /v1/route` returns 3 variants (fast / safe / eco) with flood scores
* [ ] P95 latency < 250 ms over 1000 trial requests

## Day 4 — Frontend + payment

* [ ] B2C Smart Trip app — 3-route picker, flood overlay, VETC Pay sandbox
* [ ] B2B dashboard — Dispatch + Toll Yield mini-widget online
* [ ] OAuth login wired against the dev IdP

## Day 5 — End-to-end demo + metrics

* [ ] Playwright script: 1000 simulated journeys + 100 batch orders
* [ ] Grafana board shows MAPE, P95 latency, k-anon violations live
* [ ] First parametric trigger fired end-to-end against a sandbox policy
* [ ] Friday demo recorded; PR merged to `main`
