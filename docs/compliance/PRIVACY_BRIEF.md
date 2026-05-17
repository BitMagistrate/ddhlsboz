# RoadPulse — Privacy & Security One-Pager

> Audience: jury, Skolkovo data-protection desk, TASCO compliance, partner DPOs.
> Owners: Vladimir Ermolenko (data + privacy lead), Sergey Karelin (security).
> Last revised: 17 May 2026.

## TL;DR

RoadPulse never ingests, stores or forwards personally identifiable information.
Every public endpoint is gated by a k-anonymity primitive with `min_k = 50` over
a 5-minute window. Every entry-point declares whether it's serving real or
synthetic data via the `data_origin` field. Today every feed in the MVP is
`synthetic`.

## 1. What we do *not* collect

The `roadpulse_privacy.PIIScrubber` forbids these fields anywhere in the system
(API request bodies, Kafka topics, Avro schemas, log lines, model features,
parquet exports):

```
name, full_name, first_name, last_name,
phone, phone_number, msisdn,
email, email_address,
plate, plate_number, license_plate,
transponder_id, vetc_id,
gps_track, gps_trace,
transaction_id, vin,
national_id, passport_number
```

Any payload containing one of these keys fails validation before it touches
downstream code. CI runs the scrubber against generated schemas; a single hit
turns the build red.

## 2. What we *do* collect, and how we anonymise it

| Source             | Raw shape                              | What we keep                                          |
| ------------------ | -------------------------------------- | ----------------------------------------------------- |
| VETC (post-MoU)    | per-transaction (`vetc_id`, plate, ts) | `BLAKE2b-128(vetc_id || daily_salt)` → drops after 24 h |
| Sentinel-1 SAR     | raster geotiff                         | 250 m water-mask raster, no per-vehicle data          |
| VNMS weather       | per-station obs                        | district-level hourly aggregates                      |
| Voluntary fleet SDK| GPS samples + battery state            | sub-hex (≥ res-9 H3) GPS quantisation                 |

Every aggregate that leaves the trust boundary goes through
`roadpulse_privacy.KAnonGuard(min_k=50, time_window_s=300)`. Buckets with
`observed_k < 50` are dropped and emitted to `audit.kanon.violations` so the
compliance dashboard surfaces them. No bucket means no API response — we'd
rather degrade the demo than emit re-identifiable data.

## 3. Trust boundary

```
+----------------------------+      +-----------------------------+
|  Real feeds (post-MoU)     |      |  Synthetic fixtures (today) |
|  vetc / sar / weather / sdk|  ──► |  data/seed/*.json           |
+-------------+--------------+      +--------------+--------------+
              │                                    │
              ▼                                    ▼
        ┌─────────────────────────────────────────────────┐
        │  ingestion-* services + PIIScrubber (strict)    │
        │  KAnonGuard(min_k=50, window=300 s)             │
        │  BLAKE2b-128 hashing + 24 h salt rotation       │
        └────────────────────────┬────────────────────────┘
                                 ▼
                  ┌──────────────────────────────┐
                  │  feature store (Redis-shaped)│
                  │  no row maps to a person     │
                  └────────────────┬─────────────┘
                                   ▼
                  ┌──────────────────────────────┐
                  │  /v1/* api-gateway responses │
                  │  data_origin: synthetic|real │
                  └──────────────────────────────┘
```

## 4. Security posture

* **Transport** — every internal hop is mTLS-terminated via Istio; the public
  surface is TLS 1.3-only behind an Nginx ingress with HSTS.
* **Secrets** — Helm charts source from External Secrets / SealedSecrets; the
  repo contains *zero* baseline secrets (`rg "BEGIN PRIVATE KEY"` is clean).
  `.env.example` is the only env scaffold checked in.
* **Trigger feed** — every parametric event is signed Ed25519. The per-policy
  public key is published at `/v1/trigger-feed/{policy_id}/pubkey` so the
  insurer (PTI) can verify out-of-band.
* **Audit log** — k-anon violations and policy lookup failures land in
  `audit.*` topics (Redpanda). Retention is 90 days; subjects can request a
  pull within 5 business days.
* **Vulnerability disclosure** — see [SECURITY.md](../../SECURITY.md). Reports
  go to `security@roadpulse.dev` and we ack within 3 business days.

## 5. Regulatory mapping

| Framework                               | How RoadPulse satisfies it                                              |
| --------------------------------------- | ----------------------------------------------------------------------- |
| VN PDPD 13/2023 (privacy decree)         | No PII; aggregates only; 24-h salt rotation; in-region DC hosting       |
| VN Cybersecurity Law (Decree 53/2022)    | Synthetic-only today; real-feed deployments will host in-country (FPT)  |
| GDPR Art. 5(c) (data minimisation)       | PIIScrubber + KAnonGuard make per-person data structurally impossible   |
| ISO/IEC 27701 PIMS                       | Roadmap (Build Week): map controls to the existing scrubber + auditor   |

> External legal counsel — TBD. The founders are not licensed lawyers; the
> mapping above is engineering-side best-effort and is reviewed once we engage
> Vietnamese privacy counsel before signing the first MoU.

## 6. Roles & rights (DPO surface)

* Vladimir Ermolenko — interim privacy lead, primary contact for DPOs.
* Sergey Karelin — interim security lead, primary contact for incident response.
* RoadPulse has no other employees. Every record in this repo is authored by
  one of the two founders plus this AI assistant.

## 7. Open questions tracked for Build Week

* Engage a Vietnamese privacy lawyer (Sokoloff & Co or the Skolkovo legal
  panel) to translate the engineering mapping above into a registered PIMS.
* DPIA template: stub at `docs/compliance/dpia_template.md` (Build Week TODO).
* Subject access request workflow: drafted in
  `docs/runbooks/SAR.md` — single-page checklist; needs lawyer review.

## 8. Where to look in the code

* [`packages/python/roadpulse_privacy/`](../../packages/python/roadpulse_privacy)
  — the moat. Touch only to *extend* tests.
* [`packages/python/roadpulse_privacy/tests/`](../../packages/python/roadpulse_privacy/tests)
  — k-anon, scrubber and audit-ring unit tests.
* [`apps/api-gateway/app/data_origin.py`](../../apps/api-gateway/app/data_origin.py)
  — single source of truth for the synthetic / real flag.
* [`docs/api/QUICKSTART.md`](../api/QUICKSTART.md) — public contract incl.
  health endpoint and the data-origin matrix.

## 9. Change history

| Date       | Change                                                      | Author              |
| ---------- | ----------------------------------------------------------- | ------------------- |
| 17 May 2026 | Initial pitch revision; ties to the synthetic-data labelling. | Vladimir Ermolenko |
