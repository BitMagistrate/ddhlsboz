# Data dictionary

The canonical table of every named field that crosses a service boundary.
Pulled from `schemas/avro/*.avsc` + `proto/**/*.proto` + the FastAPI
`schemas/openapi/public_v1.yaml`.

## VETC hex 5-min rollup (`vetc.hex.5min`)

| Field            | Type            | Required | Description                                        |
| ---------------- | --------------- | -------- | -------------------------------------------------- |
| `hex_id`         | string (H3 r8/9)| ✓        | Aggregation key. Always H3 res 8 or 9              |
| `bucket_start_ms`| int64           | ✓        | UNIX ms of bucket start (UTC)                      |
| `vehicle_class`  | enum            | ✓        | MOTORBIKE / CAR / TRUCK / BUS / OTHER              |
| `avg_speed_kmh`  | float32         | ✓        | Mean speed in bucket                               |
| `vehicle_count`  | int32           | ✓        | Distinct device hashes (post-k-anon)               |
| `flow_in`        | int32           | ✓        | Inbound transitions from adjacent hex              |
| `flow_out`       | int32           | ✓        | Outbound transitions                               |
| `source`         | enum            | ✓        | VETC / SDK / SYNTHETIC                             |

## Flood hex score (`flood.hex.score`)

| Field             | Type            | Required | Description                                       |
| ----------------- | --------------- | -------- | ------------------------------------------------- |
| `hex_id`          | string          | ✓        | H3 res 8                                          |
| `ts_ms`           | int64           | ✓        | Score timestamp                                   |
| `horizon_minutes` | int16           | ✓        | 0 / 60 / 180 / 360                                |
| `score`           | float32         | ✓        | Probability in [0,1]                              |
| `confidence`      | float32         | ✓        | Posterior std after Bayesian fusion               |

## Trigger event (`trigger.flood.event`)

See `proto/trigger/v1/trigger.proto` and
`schemas/avro/trigger_flood_event.avsc`. Every event is Ed25519-signed.

## API surface

For consumer-facing payloads see `schemas/openapi/public_v1.yaml`.
