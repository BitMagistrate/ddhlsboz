"""FastAPI app for the parametric-insurance trigger feed."""

from __future__ import annotations

import base64
import hashlib
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from roadpulse_telemetry.logger import get_logger


class TriggerEvent(BaseModel):
    policy_id: str
    event_id: str
    hex_id: str
    score: float
    threshold: float
    ts_ms: int
    payout_vnd: int
    signature_b64: str


_ed25519_signer: Ed25519PrivateKey | None = None  # gitleaks:allow
_public_pem: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _ed25519_signer, _public_pem
    logger = get_logger("trigger-feed")
    logger.info(
        "trigger.startup",
        mode="synthetic-fixtures",
        data_origin="synthetic",
        pending_real_feed="vetc.hex.5min+sentinel1.sar.water_mask",
    )
    _ed25519_signer = Ed25519PrivateKey.generate()
    _public_pem = (
        _ed25519_signer.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    yield
    logger.info("trigger.shutdown")


app = FastAPI(title="RoadPulse Trigger Feed", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "data_origin": "synthetic",
        "real_feeds": [],
        "pending_real_feeds": ["vetc.hex.5min", "sentinel1.sar.water_mask"],
    }


@app.get("/policies/{policy_id}/pubkey", response_class=None)
def pubkey(policy_id: str) -> dict[str, str]:
    return {"policy_id": policy_id, "pem": _public_pem}


@app.post("/policies/{policy_id}/emit", response_model=TriggerEvent)
def emit(
    policy_id: str, hex_id: str, score: float, threshold: float, payout_vnd: int
) -> TriggerEvent:
    if _ed25519_signer is None:
        raise HTTPException(503, "signer not initialised")
    ts_ms = int(time.time() * 1_000)
    event_id = hashlib.blake2b(f"{policy_id}|{hex_id}|{ts_ms}".encode(), digest_size=12).hexdigest()
    payload = f"{policy_id}|{event_id}|{hex_id}|{score:.4f}|{ts_ms}".encode()
    sig = base64.b64encode(_ed25519_signer.sign(payload)).decode("ascii")
    return TriggerEvent(
        policy_id=policy_id,
        event_id=event_id,
        hex_id=hex_id,
        score=score,
        threshold=threshold,
        ts_ms=ts_ms,
        payout_vnd=payout_vnd,
        signature_b64=sig,
    )
