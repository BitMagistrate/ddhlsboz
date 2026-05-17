"""``GET /v1/trigger-feed/{policy_id}`` — parametric insurance oracle feed.

Each event payload is signed with the gateway's Ed25519 key. Insurance partners
verify the signature using the public key exposed at
``/v1/trigger-feed/{policy_id}/pubkey`` so a downstream smart contract can
trustlessly trigger payouts.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from roadpulse_core.types import Org

from app.dependencies import org_from_api_key, state_dep
from app.models import TriggerEvent, TriggerFeedResponse
from app.state import AppState

router = APIRouter(prefix="/v1", tags=["trigger-feed"])


@router.get(
    "/trigger-feed/{policy_id}",
    response_model=TriggerFeedResponse,
    summary="Stream parametric insurance trigger events for a policy",
)
def get_trigger_feed(
    policy_id: str,
    state: Annotated[AppState, Depends(state_dep)],
    _org: Annotated[Org, Depends(org_from_api_key)],
) -> TriggerFeedResponse:
    policy = next((p for p in state.policies if str(p["id"]) == policy_id), None)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="policy not found",
        )
    threshold = float(policy.get("flood_threshold", 0.65))  # type: ignore[arg-type]
    monitored_hexes = set(policy.get("monitored_hex_ids", []))  # type: ignore[arg-type]
    events: list[TriggerEvent] = []
    for entry in state.flood_overlay:
        hex_id = str(entry["hex_id"])
        score = float(entry["score"])  # type: ignore[arg-type]
        if score < threshold:
            continue
        if monitored_hexes and hex_id not in monitored_hexes:
            continue
        captured_at = datetime.now(UTC)
        payload = {
            "policy_id": policy_id,
            "hex_id": hex_id,
            "flood_score": round(score, 4),
            "confidence": 0.85,
            "captured_at": captured_at.isoformat(),
        }
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = state.signing_key.sign(payload_bytes)
        event_id = hashlib.sha256(payload_bytes).hexdigest()[:32]
        events.append(
            TriggerEvent(
                event_id=event_id,
                policy_id=policy_id,
                hex_id=hex_id,
                flood_score=round(score, 4),
                confidence=0.85,
                captured_at=captured_at,
                payload_signature=base64.b64encode(signature).decode("ascii"),
                payload_alg="Ed25519",
            )
        )
    return TriggerFeedResponse(
        policy_id=policy_id,
        generated_at=datetime.now(UTC),
        events=events,
    )


@router.get(
    "/trigger-feed/{policy_id}/pubkey",
    response_class=PlainTextResponse,
    summary="Ed25519 public key for verifying trigger event signatures",
)
def get_pubkey(
    policy_id: str,
    state: Annotated[AppState, Depends(state_dep)],
    _org: Annotated[Org, Depends(org_from_api_key)],
) -> str:
    # In production each policy may have its own key; MVP uses a single tenant key.
    return state.public_key_pem
