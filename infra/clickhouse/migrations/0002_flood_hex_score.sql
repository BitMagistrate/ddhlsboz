CREATE TABLE IF NOT EXISTS roadpulse.flood_hex_score
(
    hex_id          LowCardinality(String),
    ts              DateTime,
    horizon_minutes UInt16,
    score           Float32,
    speed_drop_pct  Float32,
    sar_water_prior Float32,
    precipitation_mm_h Float32,
    crowd_reports   UInt16,
    confidence      Float32
)
ENGINE = MergeTree()
PARTITION BY toDate(ts)
ORDER BY (hex_id, ts, horizon_minutes);
