# Security Policy

RoadPulse is a pre-pilot mobility intelligence project run by a two-person founding
team (Vladimir Ermolenko, Sergey Karelin). The codebase currently runs on synthetic
fixtures only — no production deployment, no real PII, no real VETC feed. Despite
that, we take responsible disclosure seriously: a flaw in the privacy primitive
(`roadpulse_privacy.KAnonGuard`), the trigger-feed signing key handling, or the
ingestion pipelines could become real exposure the moment the first MoU is signed.

## Supported versions

We currently maintain only the latest `main` branch. There are no released versions yet.

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |
| older   | :x: (pre-pilot)    |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security reports. Instead:

1. Email **security@roadpulse.dev** (forwards to both founders) with:
   - A short description of the issue.
   - Reproduction steps or a minimal proof-of-concept.
   - The affected paths / endpoints / config keys.
2. Expect an initial acknowledgement within **3 business days**.
3. We aim to publish a fix on `main` within **30 days** for high-severity findings,
   90 days for lower-severity ones, and to credit you in the commit message and the
   release notes (unless you ask to remain anonymous).

If you cannot reach the e-mail alias, you can fall back to the founders directly:

- Vladimir Ermolenko — primary security contact.
- Sergey Karelin — backup contact while Vladimir is travelling.

## Scope

In scope for security reports:

- Anything under `apps/`, `packages/`, `schemas/`, `proto/`, `infra/`, `tools/`.
- The Ed25519 trigger-feed signing flow (`apps/trigger-feed`).
- The k-anonymity guard, PII scrubber and audit logger
  (`packages/python/roadpulse_privacy/*`).
- The OpenAPI contract in `schemas/openapi/public_v1.yaml`.
- Any `.env.example`, Helm values, Terraform plan that may accidentally leak a secret.

Out of scope:

- Findings on dependencies (please report upstream first; we'll bump after the
  upstream advisory is public).
- DoS against the demo `compose.dev.yaml` stack (it's a developer fixture, not a
  hardened deployment).
- Social engineering of the founding team.

## Coordinated disclosure

We follow a 90-day coordinated disclosure window. After we publish a fix on `main`,
you are free to publish your write-up; we will gladly link it from a CHANGELOG entry.

## Legal review

We do **not** have in-house legal counsel. Any contract clauses, DPAs, or SCC
templates required to formalise a disclosure are routed to **external legal
counsel — TBD** and may take additional time. We will keep you in the loop.

---

_Last reviewed: 2026-05. Maintained by Vladimir Ermolenko and Sergey Karelin._
