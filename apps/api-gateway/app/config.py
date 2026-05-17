"""Runtime configuration loaded from environment variables.

We use ``pydantic-settings`` so every variable is validated, typed and documented
in one place. The same ``Settings`` class is consumed by every router via the
:func:`app.dependencies.get_settings` dependency.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Public API gateway configuration."""

    model_config = SettingsConfigDict(env_prefix="ROADPULSE_", case_sensitive=False)

    service_name: str = Field(default="api-gateway")
    environment: str = Field(default="dev")
    log_level: str = Field(default="INFO")

    # Storage / cache backends. In MVP these are stubs — the in-memory feature store
    # is wired through ``app.state.seed`` so the app starts without external infra.
    redis_url: str | None = None
    postgres_dsn: str | None = None
    clickhouse_dsn: str | None = None
    redpanda_brokers: str | None = None

    # OSRM is only consulted if reachable; the routing engine has a pure-Python
    # fallback that runs on the seeded HCMC graph.
    osrm_motorbike_url: str = "http://osrm-motorbike:5000"
    osrm_car_url: str = "http://osrm-car:5000"

    # Public ``/v1`` is API-key gated. Seed keys live in the seed bundle.
    require_api_key: bool = False
    rate_limit_per_minute: int = 600

    # CORS. The B2B dashboard uses Vite (5173) and the B2C app uses Expo (8081/19006).
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:19006",
            "http://localhost:8081",
        ]
    )

    # Seed data location. Defaults to ``data/seed`` in the repo.
    seed_data_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3] / "data" / "seed"
    )

    # Privacy. The k-anon threshold from PDPD 13/2023/NĐ-CP MVP guidance.
    k_anon_threshold: int = 50


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
