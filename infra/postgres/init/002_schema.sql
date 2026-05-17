-- Core schemas. Each domain owns a dedicated schema so role-based access can
-- be enforced via GRANT.

CREATE SCHEMA IF NOT EXISTS roadpulse;
CREATE SCHEMA IF NOT EXISTS roadpulse_audit;

-- Organisations (commercial accounts)
CREATE TABLE IF NOT EXISTS roadpulse.organisations (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    tier         TEXT NOT NULL CHECK (tier IN ('internal','b2c','b2b','b2b2c','research')),
    country      TEXT NOT NULL DEFAULT 'VN',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- API keys (hashed)
CREATE TABLE IF NOT EXISTS roadpulse.api_keys (
    key_hash     BYTEA PRIMARY KEY,
    org_id       TEXT NOT NULL REFERENCES roadpulse.organisations(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at   TIMESTAMPTZ
);

-- Fleets (B2B logistics customers)
CREATE TABLE IF NOT EXISTS roadpulse.fleets (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    vehicle_class   TEXT NOT NULL,
    home_lat        DOUBLE PRECISION NOT NULL,
    home_lng        DOUBLE PRECISION NOT NULL,
    capacity        INTEGER NOT NULL,
    rating          DOUBLE PRECISION NOT NULL DEFAULT 0.0
);

-- Parametric-insurance policies
CREATE TABLE IF NOT EXISTS roadpulse.policies (
    id              TEXT PRIMARY KEY,
    carrier         TEXT NOT NULL,
    threshold       DOUBLE PRECISION NOT NULL,
    payout_vnd      BIGINT NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- k-anon violation log (write-only from API + ingestion)
CREATE TABLE IF NOT EXISTS roadpulse_audit.kanon_violations (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT NOT NULL,
    bucket        TEXT NOT NULL,
    attempted_k   INTEGER NOT NULL,
    min_k         INTEGER NOT NULL,
    dropped_at    TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kanon_dropped_at ON roadpulse_audit.kanon_violations (dropped_at DESC);
