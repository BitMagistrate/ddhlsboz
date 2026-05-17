# OSRM service

OSRM 5.27 with three custom Lua profiles tuned for Vietnam:

| Profile         | α (cong) | β (flood) | γ (eco) | Notes                                          |
| --------------- | -------- | --------- | ------- | ---------------------------------------------- |
| `motorbike-vn`  | 0.6      | 2.5       | 0.05    | Highest β — bikes are most sensitive to floods |
| `car-vn`        | 0.9      | 1.5       | 0.10    | Higher α — cars hurt most by congestion        |
| `truck-vn`      | 1.0      | 1.2       | 0.18    | Highest γ — fuel sensitivity dominates eco     |

The profiles must stay in sync with
`packages/python/roadpulse_routing/roadpulse_routing/profiles.py` — both
engines use the formula `cost = free_flow × (1 + α·cong + β·flood + γ·eco)`
so the in-process Python fallback returns identical paths.

## Build

```bash
osrm-extract  -p services/osrm/profiles/motorbike-vn.lua data/osm/vietnam-latest.osm.pbf
osrm-partition data/osm/vietnam-latest.osrm
osrm-customize data/osm/vietnam-latest.osrm
osrm-routed --algorithm=MLD data/osm/vietnam-latest.osrm
```

## Live traffic update

`tools/osrm-updater` writes a `traffic.csv` with `(from_node, to_node, rate)`
every 5 min and calls `osrm-customize --segment-speed-file traffic.csv`. The
contraction hierarchy is preserved so the update is sub-second.
