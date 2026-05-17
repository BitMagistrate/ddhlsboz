# 90-second demo script

> Reproducible. Same flow every time. Use a screen recorder set to 1280×720.
> One run, no cuts, no voiceover (we add subtitles in post). Total budget:
> 90 seconds.

## 0. Prep (off camera, do once)

```bash
git pull
make bootstrap
make seed
make up
uvicorn apps.api-gateway.app.main:app --port 8000 --reload &
(cd apps/b2b-dashboard && pnpm dev --host) &
(cd apps/b2c-app       && pnpm start) &
```

Wait until:

* `curl :8000/v1/healthz | jq .data_origin` returns `"synthetic"`.
* `http://localhost:5173` renders the B2B dashboard.
* The Expo "Smart Trip" tab renders in the iOS simulator.

Open three windows in this order, left-to-right:

1. iOS simulator (B2C "Smart Trip" tab, prefilled with the Tan Son Nhat →
   Phu My Hung trip).
2. Chrome at `http://localhost:5173/flood-watch` (B2B dashboard).
3. Terminal positioned to call `curl http://localhost:8000/v1/trigger-feed/policy_pti_d1_flood_2024 | jq .events[0]`.

## 1. Beat-by-beat (90 s)

| Time   | What's on screen                                              | Subtitle                                                                |
| ------ | -------------------------------------------------------------- | ----------------------------------------------------------------------- |
| 0–10 s | Smart Trip screen with Fast/Safe/Eco picker; flood overlay on. | "Choose Safe — RoadPulse re-routes around District-1 flood."           |
| 10–25 s | Tap Safe → flood corridor highlights → user starts trip.       | "+11 min, +0.4 kg CO₂ avoided. ETA p10/p90 visible."                    |
| 25–40 s | Swap to B2B dashboard `flood-watch` page; live overlay.        | "Same data drives the dispatcher's view — k≥50, no PII."                |
| 40–55 s | Open Toll Yield page; show synthetic banner + chart.           | "Top-5 hex by daily toll revenue, updated every five minutes."          |
| 55–70 s | Open Fleet Match page; trigger a match request live.           | "B2B fleet match: ETA, capacity, flood risk — one click."               |
| 70–85 s | Terminal `curl` returns a signed parametric event.             | "Ed25519-signed trigger feed for the parametric insurer."               |
| 85–90 s | Hold on the `healthz` JSON; highlight `data_origin: synthetic`. | "All demo data is synthetic. Real feeds plug in post-MoU."             |

## 2. Variants

* **45-second cut for slide 6.** Drop the toll-yield page (40–55 s) and
  the fleet-match beat (55–70 s); keep B2C → B2B flood → trigger feed.
* **3-minute walk-through.** Insert (after 70 s) the privacy brief, the
  ML eval table (`make test.ml.eval`) and the loadtest summary
  (`docs/demo/loadtest-results.txt`).

## 3. Things that always break (and how to recover)

| Symptom                                                | Fix                                                        |
| ------------------------------------------------------ | ---------------------------------------------------------- |
| B2C overlay won't render                                | Reload the Expo bundler; the H3 polygons are heavy.        |
| `/v1/route` returns 422 "destination unreachable"      | Re-seed: `make seed` then restart `dev.api`.               |
| B2B dashboard shows "demo banner" on every page        | Working as intended. Don't hide the banner.                |
| Trigger feed returns `[]`                              | Bump the seeded clock: `python tools/seed_dataset.py --bump-clock`. |

## 4. Final cut

Render at 1080p / 30 fps. Upload as `docs/demo/SCRIPT-2026-05-17.webp`
animated. Link from `README.md` § Demo and from the pitch deck slide 6.

## 5. Linkable assets

* [Privacy brief](../compliance/PRIVACY_BRIEF.md)
* [Loadtest summary](./loadtest-results.txt)
* [ML eval results](../../ml/eval/results.json)
* [API quickstart](../api/QUICKSTART.md)
* [Pitch deck source](../pitch/roadpulse_pitch.md)
