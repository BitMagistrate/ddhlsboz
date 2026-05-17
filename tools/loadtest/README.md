# RoadPulse loadtest

`route.js` is a [k6](https://k6.io/) script that proves the `/v1/route`
endpoint stays under 250 ms p95 with 50 concurrent VUs on the seeded HCMC
demo graph.

## Run locally

```bash
# 1. boot the api-gateway against the synthetic fixtures
make up
uvicorn apps.api-gateway.app.main:app --port 8000 --reload &

# 2. run the loadtest (k6 ≥ 0.50)
make load
# or:
BASE_URL=http://localhost:8000 k6 run tools/loadtest/route.js
```

The script writes a human-readable summary to `docs/demo/loadtest-results.txt`
so we can paste the numbers straight onto pitch-deck slide 14.

## What the script proves

* p95 latency < 250 ms on the /v1/route endpoint
* < 1 % error rate
* The api-gateway returns three variants (fast/safe/eco) for every request
* All traffic is hitting the synthetic-fixtures dataset — never a real feed

## Tuning

Pass shape overrides via env vars:

| Variable                | Default                 | Meaning                                        |
| ----------------------- | ----------------------- | ---------------------------------------------- |
| `BASE_URL`              | `http://localhost:8000` | API gateway base URL.                          |
| `ROADPULSE_API_KEY`     | `demo_synthetic_key`    | API key used in the X-Api-Key header.          |
| `K6_THRESHOLD_P95_MS`   | `250`                   | SLA threshold for p95 latency.                 |

If you need a heavier scenario, edit the `stages` block in `route.js` — we
keep the default conservative so CI can run it on a 2-core runner.
