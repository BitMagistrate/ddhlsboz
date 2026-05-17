# ADR-0003 — k-anonymity ≥ 50 as the privacy floor

* Status: Accepted
* Date: 2026-01-15
* Deciders: CEO, Chief Data Officer, Head of Public Affairs

## Context

VETC transponder data is sensitive. Vietnam Decree 13/2023/NĐ-CP requires
that personal data be anonymised before processing for analytics. Industry
practice for k-anonymity ranges from k=5 (academic) to k=100 (telco).

## Decision

We enforce **k ≥ 50** at the **bucket** boundary (hex × 5-min × vehicle
class). Any bucket with fewer than 50 distinct device hashes is dropped at
ingestion time and never leaves the privacy boundary.

* Implementation: `roadpulse_privacy.KAnonGuard` (`packages/python/roadpulse_privacy`).
* Audited via the `audit.kanon.violations` Kafka topic + Postgres mirror.
* The threshold is exposed via `ROADPULSE_KANON_MIN_K` but defaults to 50;
  no environment may set it below 50 in production.

## Consequences

* Roughly 4–6% of hexes in HCMC will be dropped during quiet hours. This is
  acceptable because routing is still served via OSRM defaults.
* SDK collectors must hash device_id with BLAKE2b-128 before emit; the
  collector enforces this server-side.
* PII scrubber refuses to persist driver_id, phone, plate, transponder_id
  or any GPS trace at sub-hex granularity.
