"""Light wrapper that proxies vector-tile requests to martin and overlays our
H3 flood layer. For Build Week we serve GeoJSON directly (Mapbox GL ingests
both)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="RoadPulse Tile Server", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "data_origin": "synthetic",
        "real_feeds": [],
        "pending_real_feeds": ["sentinel1.sar.water_mask"],
    }


@app.get("/overlays/flood.geojson")
def flood_overlay() -> JSONResponse:
    seed = Path(__file__).resolve().parents[3] / "data" / "seed" / "flood_markers.json"
    if not seed.exists():
        raise HTTPException(404, "flood_markers.json missing")
    floods = json.loads(seed.read_text())
    features = []
    for hex_id, payload in floods.items():
        if not isinstance(payload, dict):
            continue
        try:
            lat = float(payload.get("lat"))
            lng = float(payload.get("lng"))
        except (TypeError, ValueError):
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {
                    "hex_id": hex_id,
                    "score": float(payload.get("score", 0.0)),
                    "note": payload.get("note", ""),
                },
            }
        )
    return JSONResponse({"type": "FeatureCollection", "features": features})
