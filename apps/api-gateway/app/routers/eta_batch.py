"""``POST /v1/eta-batch`` — batch ETA inference for dispatch/logistics."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from roadpulse_core.types import Org
from roadpulse_ml.eta import EtaModel, ETARecord
from roadpulse_routing.engine import RoutingEngine

from app.dependencies import (
    eta_model_dep,
    org_from_api_key,
    routing_engine_dep,
    state_dep,
)
from app.models import (
    BatchEtaPrediction,
    BatchEtaRequest,
    BatchEtaResponse,
)
from app.state import AppState

router = APIRouter(prefix="/v1", tags=["eta"])


@router.post(
    "/eta-batch",
    response_model=BatchEtaResponse,
    summary="Predict ETA for a batch of 1–50K orders",
)
def post_eta_batch(
    body: BatchEtaRequest,
    engine: Annotated[RoutingEngine, Depends(routing_engine_dep)],
    eta_model: Annotated[EtaModel, Depends(eta_model_dep)],
    state: Annotated[AppState, Depends(state_dep)],
    _org: Annotated[Org, Depends(org_from_api_key)],
) -> BatchEtaResponse:
    depart_at = body.depart_at or datetime.now(UTC)
    hour_of_week = (depart_at.weekday() * 24 + depart_at.hour) % 168
    is_weekend = 1 if depart_at.weekday() >= 5 else 0
    is_rush = 1 if depart_at.hour in {7, 8, 9, 17, 18, 19} else 0

    predictions: list[BatchEtaPrediction] = []
    eta_sum = 0.0
    flood_sum = 0.0
    for item in body.items:
        origin = state.nearest_node(item.origin).id
        dest = state.nearest_node(item.destination).id
        try:
            variant = engine.three_candidates(origin, dest, mode=item.mode)[0]
        except LookupError:
            # Fall back to a haversine straight-line estimate so an unreachable
            # outlier doesn't poison the whole batch.
            from roadpulse_core.geo import haversine_m

            distance_m = haversine_m(
                item.origin.lat, item.origin.lng, item.destination.lat, item.destination.lng
            )
            ff = distance_m / 1000 / 25 * 3600
            predictions.append(
                BatchEtaPrediction(
                    order_id=item.order_id,
                    distance_m=distance_m,
                    eta_s=ff * 1.4,
                    eta_p10_s=ff,
                    eta_p90_s=ff * 1.8,
                    flood_score=0.05,
                    confidence=eta_model.predict(
                        ETARecord(
                            distance_m=distance_m,
                            free_flow_seconds=ff,
                            hour_of_week=hour_of_week,
                            is_weekend=is_weekend,
                        )
                    ).confidence,
                )
            )
            eta_sum += ff * 1.4
            flood_sum += 0.05
            continue
        avg_speed = (variant.distance_m / variant.duration_s) * 3.6 if variant.duration_s > 0 else 0
        record = ETARecord(
            distance_m=variant.distance_m,
            free_flow_seconds=variant.free_flow_seconds,
            hour_of_week=hour_of_week,
            is_weekend=is_weekend,
            precipitation_mm_h=4.0 if variant.flood_score > 0.2 else 0.0,
            wind_kmh=12.0,
            is_rush_hour=is_rush,
            lag_speed_5min=avg_speed,
            lag_speed_15min=avg_speed,
            lag_speed_1h=avg_speed,
            vehicle_count_5min=320,
            flood_score=variant.flood_score,
            road_class_index=1,
        )
        prediction = eta_model.predict(record)
        predictions.append(
            BatchEtaPrediction(
                order_id=item.order_id,
                distance_m=variant.distance_m,
                eta_s=prediction.eta_s,
                eta_p10_s=prediction.eta_p10_s,
                eta_p90_s=prediction.eta_p90_s,
                flood_score=variant.flood_score,
                confidence=prediction.confidence,
            )
        )
        eta_sum += prediction.eta_s
        flood_sum += variant.flood_score

    n = max(1, len(predictions))
    summary = {
        "n_orders": float(len(predictions)),
        "mean_eta_s": eta_sum / n,
        "mean_flood_score": flood_sum / n,
    }
    return BatchEtaResponse(
        batch_id=body.batch_id,
        generated_at=datetime.now(UTC),
        predictions=predictions,
        summary=summary,
    )
