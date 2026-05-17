-- Aggregated VETC traffic rollup. Partitioned by day, ordered by hex + bucket.
CREATE TABLE IF NOT EXISTS roadpulse.vetc_hex_5min
(
    hex_id          LowCardinality(String),
    bucket_start    DateTime CODEC(Delta, ZSTD(3)),
    vehicle_class   LowCardinality(String),
    avg_speed_kmh   Float32,
    speed_p10       Float32,
    speed_p50       Float32,
    speed_p90       Float32,
    vehicle_count   UInt32,
    flow_in         UInt32,
    flow_out        UInt32,
    source          LowCardinality(String)
)
ENGINE = MergeTree()
PARTITION BY toDate(bucket_start)
ORDER BY (hex_id, bucket_start, vehicle_class)
SETTINGS index_granularity = 8192;
