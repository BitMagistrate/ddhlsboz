# ADR-0001 — Record architecture decisions

* Status: Accepted
* Date: 2026-01-09
* Deciders: CEO, CTO, Chief Data Officer

## Context

We need a lightweight record of significant architectural choices so that new
engineers can understand *why* the system looks the way it does without
re-deriving it from the pitch document.

## Decision

Use Markdown-formatted Architecture Decision Records (ADRs), one per
significant decision, stored under `docs/adr/`. ADRs are append-only:
superseding an ADR creates a new one referencing the old.

## Consequences

* Each PR that touches more than one service must reference an ADR or open one.
* The CTO reviews ADRs in the weekly platform sync.
* No ADR may exceed two A4 pages.
