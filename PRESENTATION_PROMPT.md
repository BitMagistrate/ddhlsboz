# RoadPulse — Presentation Prompt

> A drop-in prompt for any deck-generating assistant (Gamma, Tome, Beautiful.ai,
> Slidesgo AI, ChatGPT + the *Slides* GPT, Claude + Canva). Copy everything
> between the `===` markers, paste it into the tool, then export to `.pptx`
> or `.pdf`. The prompt is written so the assistant has **all** the facts it
> needs — it should not invent numbers; if it lacks data, it must surface a
> placeholder labelled `«TBD — confirm with founder»`.

---

```
===
You are a senior investor-deck designer working for **RoadPulse JSC**, a
Vietnam-incorporated flood-aware mobility-intelligence startup. Build a
**16:9 pitch deck (24 ± 2 slides)** that I can use in three pitching contexts:

1. **Skolkovo Startup Tour 2026 — TashKent regional final** (Russian audience,
   technology track). 8-minute talk + 4-minute Q&A.
2. **TASCO Group strategic-investment committee** (Vietnamese audience,
   English working language). 15-minute formal pitch.
3. **Bao Việt Holdings InsurTech round-table** (Vietnamese, English-bilingual).
   10-minute appetiser pitch + 5-minute parametric-insurance demo.

The deck must work in all three contexts — i.e. include both Vietnamese
spelling of place names ("Quận 1", "Cát Lái", "Bến Thành") *and* an English
gloss in parentheses on first mention; keep Russian-readable numerics (use
", " as thousands separator, " " as decimal? — actually keep "," for
thousands and "." for decimals to match international convention; spell out
₫ as "VND" the first time, then use "₫").

────────────────────────────────────────────────────────────────────────
1. POSITIONING — THE ONE LINE
────────────────────────────────────────────────────────────────────────
RoadPulse is the first **flood-aware mobility-intelligence layer for
Vietnam**. We turn aggregated VETC (Vietnam Electronic Toll Collection)
transponder data + Sentinel-1 SAR + crowd reports into three concrete
products:

* a **B2C** Smart Trip app ("the Google Maps that doesn't drown you")
* four **B2B** dashboards (Dispatch, Toll Yield, Site Selection, Fleet Match)
* a **B2B2C** parametric-insurance oracle for Bao Việt / PVI / MIC

Tagline (use exactly): **"Don't predict the rain. Predict the flood."**

────────────────────────────────────────────────────────────────────────
2. SLIDE-BY-SLIDE STRUCTURE (24 slides)
────────────────────────────────────────────────────────────────────────
For every slide use the format:

  • Header — 5-word headline
  • Body  — three sub-bullets, max 14 words each
  • Footer — 1-line "so what" (italic, 12pt)
  • Visual — a short brief for the image / chart / diagram

1. **Cover** — Logo, tagline, three speaker names, contact, the line
   "Vietnam-incorporated · VNG Cloud · k-anonymity ≥ 50". Visual: a
   night-time photo of motorbikes wading through ankle-deep flooding on
   Nguyễn Hữu Cảnh St — colour-graded toward our river-slate / pulse-blue
   palette (#0F172A / #2563EB).

2. **The 30-second hook** — three numbers, no prose:
   - **57 cm**  · average flood depth on Nguyễn Hữu Cảnh, monsoon 2024
   - **₫ 3 800 bn / yr** · estimated flood-related logistics cost in HCMC alone
   - **0** · existing flood-aware routing APIs in Vietnam
   Visual: a giant "57 cm" overlaid on a hex map of HCMC, the eight worst hexes
   tinted hazard-amber.

3. **Problem** — three bullets that flow:
   - HCMC + Hà Nội average 12–24 monsoon flood days / year, growing
   - Existing nav apps (Google Maps, Vietmap) re-route too late — typically
     12–18 min *after* the first complaint hits social media
   - Logistics fleets, retail and parametric insurers all eat the cost
   Visual: timeline graphic — "First flood report → Google re-routes → Lost
   delivery window" with three icons (rain cloud, smartphone, scooter).

4. **Why us, why now** — five "why now" bullets:
   - 100% of VN tolled traffic on VETC by end-2026 (Decree 119/2024)
   - VNG Cloud opened the Hanoi region in 2025 → data residency is solved
   - Sentinel-1 SAR free + global; Copernicus Data Space gives 6-day revisit
   - LightGBM + H3 are commodity → the moat is **the data deal**, not the model
   - Skolkovo + TASCO both have a Vietnam-corridor mandate
   Visual: 5-row matrix with a green check next to each row.

5. **Market** — TAM / SAM / SOM, all in VND:
   - TAM (VN mobility-data layer): ₫ 9 200 bn / yr by 2030
   - SAM (HCMC + Hà Nội + Đà Nẵng B2B2C): ₫ 2 100 bn / yr by 2028
   - SOM (Y3 plan, 4 segments): ₫ 190 bn / yr
   Use a 3-tier concentric-ring chart, not a pie.

6. **Product surface** — 4 tiles in a 2×2 grid:
   - Smart Trip (B2C app, three-route picker, flood overlay, VETC Pay)
   - Dispatch (B2B, batch ETA, flood-aware re-route)
   - Toll Yield (B2B concessionaire, dynamic price recs)
   - Site Selection + Fleet Match (B2B retail + freight)
   Each tile: screenshot stub + 2-sentence description + a single KPI.

7. **How it works — data flywheel** — diagram (left → right):
   VETC SFTP → ingestion-vetc → KAnonGuard (k≥50) → Redpanda
                                            ↓
                              Feast online (Redis) / offline (S3 parquet)
                                            ↓
        OSRM (custom Lua profile)  ←—  LightGBM ETA  ←—  IsolationForest+SAR flood
                                            ↓
                                api-gateway → B2C / B2B / triggers
   Annotate every arrow with the SLA / latency it must hit.

8. **Demo flow — 3 minutes live** — describe the demo, not record it:
   - Step 1: Type O-D in Smart Trip → 3 routes returned in < 250 ms
   - Step 2: Tap "Safe" → animated flooded hexes appear on overlay
   - Step 3: Switch to Dispatch dashboard → 100 batch orders re-routed in 12 s
   - Step 4: Force a flood-trigger → Bao Việt JSON payload signed live with
     Ed25519, verified on screen against the published PEM
   The slide is just talking points; the actual demo runs from the dashboard.

9. **Defensibility / the moat** — three "compounding loops":
   - Data: VETC deal is exclusive for 3 years; every new fleet that opts in to
     the SDK adds k-anon volume → unlocks more hexes for everybody
   - Regulatory: we operate inside the Decree 13/2023 personal-data framework
     by design (k≥50, PII never persisted) → carriers + ministries can deploy
     us without legal risk
   - Network: the parametric-insurance oracle becomes the **price reference**
     for flood risk; once two carriers cite it, every new product points at us
   Visual: a 3-node feedback diagram with arrows looping back.

10. **Business model — six revenue streams** in a table:
    | Stream                         | Pricing                        | Y3 share |
    | ------------------------------ | ------------------------------ | -------- |
    | Smart Trip premium (B2C)       | ₫ 39 000 / mo                  | 8%       |
    | Dispatch API (B2B logistics)   | ₫ 0.4–0.9 / call, vol tiers    | 26%      |
    | Toll-yield uplift (B2B conc.)  | 12% rev-share of incremental   | 22%      |
    | Site-selection licence (B2B)   | ₫ 1.8 bn / yr / chain          | 14%      |
    | Fleet-match marketplace        | 4% take rate                   | 12%      |
    | Insurance trigger feed (B2B2C) | ₫ 480 / event + ₫ 18M / mo MRR | 18%      |

11. **Unit economics** — one chart + three numbers:
    - Blended ARPU (Y3, weighted): ₫ 142 000 / paying user / mo
    - CAC payback: 5.8 months
    - LTV / CAC: 4.6×
    Use a tornado chart: revenue lines stacked on the right, CAC + COGS bars
    pointing left.

12. **Financial model — 5-year forecast** — table only:
    | VND bn        | Y1   | Y2    | Y3    | Y4    | Y5    |
    | ------------- | ---- | ----- | ----- | ----- | ----- |
    | Revenue       | 6.2  | 28.4  | 92.6  | 218.0 | 396.0 |
    | Gross margin  | 41%  | 56%   | 64%   | 68%   | 71%   |
    | EBITDA        | -8.1 | -4.6  | 11.8  | 64.5  | 132.0 |
    | Cash burn     | -22  | -16   | -2    | +14   | +66   |
    | Headcount     | 14   | 32    | 58    | 96    | 140   |
    Footnote: assumes 1 USD = 25 400 ₫, monsoon-year base case.

13. **Go-to-market** — three concentric phases:
    - **Phase 0 (Build Week → Q3 2026)**: 1 paid Dispatch pilot (Lazada
      Logistics or Ahamove), 1 Toll-Yield pilot (VEC), 1 Bao Việt parametric
      MoU. No B2C yet.
    - **Phase 1 (Q4 2026 → Q2 2027)**: Smart Trip open beta in HCMC, 2 paid
      dispatch contracts, first MIC / PVI trigger product.
    - **Phase 2 (H2 2027 → H1 2028)**: Hà Nội + Đà Nẵng expansion; first
      ASEAN deal (Bangkok / Jakarta) via the Skolkovo corridor.
    Visual: roadmap timeline with milestones and named partners.

14. **Competition** — 2×2 matrix:
    - x-axis: VN data depth (low → high)
    - y-axis: flood awareness (none → core capability)
    - We sit alone in the top-right corner
    - Quadrants populated with Google Maps, Vietmap, HERE, Mapbox, Vietnam
      Posts & Telecoms (VNPT), Grab, Be, FPT IS, and (open) ASEAN insurtechs
    Don't say "we have no competition" — explicitly call out who **could**
    enter (Google Local Discovery, Grab GeoOS) and why VETC exclusivity
    blocks them for 24-36 months.

15. **Team** — 6 photos in a 2×3 grid:
    - CEO (founder, ex-Lazada Logistics, BCG before)
    - CTO (ex-Zalo / VNG, 8 yrs distributed systems, OSRM contributor)
    - Chief Data Officer (ex-VinAI, PhD in Bayesian inference, Sentinel-1
      author on three papers)
    - Head of Insurance (ex-Bao Việt actuary, MAS-licensed)
    - Head of Vietnam Public Affairs (ex-MOT senior advisor)
    - VP Engineering (ex-Booking.com Amsterdam, hiring lead)
    Each tile: name, prior co, 1 superpower (12pt). Mark advisors separately.

16. **Tech stack — one diagram, no text** — the architecture diagram from
    section 7 of the pitch document, simplified to ≤ 14 boxes. Group by
    color: green = data sources, blue = ingestion, purple = ML, orange =
    serving, grey = consumers. Pull `compose.dev.yaml` for the exact
    component list — do not hallucinate components.

17. **Privacy & compliance** — four bullets, each tied to a primary source:
    - k-anonymity ≥ 50 enforced in `roadpulse_privacy.guard.KAnonGuard`
      (Vietnam Decree 13/2023 art. 25)
    - PII scrubber blocks driver_id, phone, plate, transponder_id, GPS track
      (`packages/python/roadpulse_privacy/scrubber.py`)
    - Data residency: VNG Cloud HCM-1; cold storage in HCM-2 DR pair
    - Sentinel-1 reuse is Copernicus Open Data licence — explicit attribution
    Visual: 4 lock icons with footnote sources.

18. **Weak spots — the slide every junior founder forgets** — be brutal:
    - VETC data deal is single-vendor risk; mitigation: voluntary fleet SDK
      already gives us 8% of HCMC traffic without VETC
    - ETA MAPE target 15% is aggressive; backup plan: ship 18%, throttle
      revenue claims, retrain weekly until model improves
    - Monsoon seasonality means revenue is concave; we counter with the
      Toll-Yield + Site-Selection streams which are flat year-round
    - Personnel concentration in HCMC; we open a Hà Nội pod in Y2 for DR
    Slide design: "What could kill us?" headline, four red-bordered boxes
    each with the problem + mitigation.

19. **Russian-audience summary** — one full slide in Russian only, for the
    Skolkovo / Sber audience. Cover:
    - Что строим? Геопространственный AI-слой для Вьетнама.
    - Почему сейчас? Эксклюзивная сделка с VETC; рынок страхования от
      наводнений во Вьетнаме растёт +28% YoY.
    - Какие деньги? ARR ₫ 92.6 млрд через 3 года, gross margin 64%.
    - Что нужно? Раунд Pre-seed 1.2 млн USD на 18 месяцев, оценка
      pre-money 6 млн USD.
    - Кто командует? CEO + CTO + Chief Data Officer — все вьетнамцы с
      опытом в Lazada / VNG / VinAI; русскоязычный CFO в процессе найма.
    - Какой риск для инвестора? Single-vendor (VETC) + регуляторный риск
      Декрета 13/2023; оба покрыты в слайде 18.
    Use Cyrillic-safe fonts (Inter or Roboto Cyrillic).

20. **Legal & compliance roadmap** — single timeline:
    - Q1 2026: VN Ministry of Industry & Trade business licence
    - Q2 2026: Cybersecurity Law 24/2018 registration with A05
    - Q2 2026: PDPL/Decree 13/2023 data-controller declaration filed
    - Q3 2026: First insurance trigger published — MAS / SBV review
    - Q4 2026: ISO/IEC 27001 audit (BSI Vietnam)
    Mark each milestone as "done / in flight / not started".

21. **Use of funds** — donut chart:
    - 38% engineering & data science (12 hires over 18 mo)
    - 22% data-deal exclusivity advance to VETC
    - 14% sales & partnerships (2 senior BD hires)
    - 12% compliance, legal, audits
    - 8%  ASEAN expansion runway (Bangkok pilot)
    - 6%  reserve / contingency

22. **The ask** — three lines, huge type:
    - **₫ 30,5 bn pre-seed** (≈ 1.2 M USD)
    - **18-month runway**, milestone-gated
    - **Lead investor wanted** — Skolkovo or TASCO Group; we close together
      with at least one VN-based angel + one ASEAN strategic.

23. **Milestones we'll hit on this round** — checklist:
    - VETC exclusivity contract signed (legal closed)
    - Smart Trip app launched in HCMC, 50 K MAU
    - 3 paying B2B contracts (Lazada / Ahamove / VEC)
    - First parametric trigger paid out under a Bao Việt policy
    - ETA MAPE ≤ 13% on a public 30-day benchmark
    - ARR ₫ 8 bn / annualised by end of round

24. **Closing slide** — tagline repeated, contact, QR code linking to
    `https://roadpulse.vn/pitch`, founder phone in Vietnamese / English /
    Russian. Visual: a wide shot of dawn over the Saigon River, with the
    river-slate gradient continuing into the page edges.

────────────────────────────────────────────────────────────────────────
3. DESIGN SYSTEM (must follow)
────────────────────────────────────────────────────────────────────────
- Colours: river slate `#0F172A`, pulse blue `#2563EB`, hazard amber
  `#F59E0B`, river fog `#F1F5F9`, good green `#16A34A`. Background is
  always either white or river slate; never both on the same slide.
- Typography: **Inter** (or Helvetica Now as fallback) for everything. Use
  3 sizes only: 56pt headline, 28pt body, 12pt footnote. No italics in
  headlines; italics allowed in footnotes only.
- Icons: lucide-react style (line, 1.5pt weight, rounded caps). Reuse the
  same 12 icons throughout — never invent new ones.
- Charts: recharts default ramp with our pulse-blue accent. No 3D charts,
  no exploded pies, no gradient fills beyond a single 12% opacity wash.
- Whitespace: every slide breathes. Minimum 64pt outer margin on 16:9.
  Body content occupies ≤ 70% of slide height.
- Numbers: VND uses "₫" suffix after a thin space (" ₫"). Percentages have
  no space. Decimal separator is ".". Thousands separator is ",".
- Photography: always Vietnam-shot. Prefer Saigon River, motorbikes, hex
  overlays. Never use cliché stock images of "data" (binary rain, neon
  cyberpunk grids, glowing brains).
- Footer (every slide): RoadPulse logo bottom-left at 18pt; slide number
  bottom-right at 12pt; tagline only on cover and close.

────────────────────────────────────────────────────────────────────────
4. NARRATIVE FLOW (read aloud as the deck advances)
────────────────────────────────────────────────────────────────────────
Open with the hook (slide 2). Spend 45 s on problem (3) → why-now (4) →
market (5). 90 s on product (6) → flywheel (7) → demo (8). 90 s on moat
(9) → business model (10) → unit economics (11) → financial model (12).
60 s on GTM (13) → competition (14) → team (15). 60 s on tech (16) →
privacy (17) → weak spots (18). For the Skolkovo cut, swap slides 19-20
to the top of this block (Russian summary first, then legal). 30 s for
funds (21) → ask (22) → milestones (23) → close (24).

────────────────────────────────────────────────────────────────────────
5. SOURCES THE ASSISTANT MUST CITE (not invent)
────────────────────────────────────────────────────────────────────────
- Vietnam Decree 13/2023/NĐ-CP on personal-data protection
- Decree 119/2024/NĐ-CP on the mandatory rollout of VETC
- Cybersecurity Law 24/2018/QH14
- Copernicus Data Space — Sentinel-1 Open Data licence
- VN General Statistics Office (GSO) — vehicle registration data 2023
- World Bank — "Climate Resilience for Urban Mobility in Vietnamese Cities"
  technical paper, 2024
- The RoadPulse internal pitch document (`docs/pitch/roadpulse_pitch.md`)
  is the single source of truth for product, architecture and financials
- The RoadPulse monorepo for code-level facts:
  https://github.com/BitMagistrate/ddhlsboz — every architectural box on
  slide 16 must correspond to a directory under `apps/`, `packages/`,
  `services/` or `infra/`

────────────────────────────────────────────────────────────────────────
6. STRICT RULES
────────────────────────────────────────────────────────────────────────
- DO NOT invent partners, customers, MAU or ARR numbers beyond what is in
  this prompt. If you need a number we have not provided, insert
  `«TBD — confirm with founder»` and continue.
- DO NOT generate code in the deck; reference the repo URL instead.
- DO NOT use English for the slide-19 body — keep it 100% Russian.
- DO NOT produce more than 26 slides total.
- DO NOT add a "thank-you / questions?" slide; the closing slide already
  does that with the tagline.
- DO produce a separate "speaker notes" block for each slide of ≤ 90 words,
  written in the founder's first-person voice ("we", not "the team").
- DO output everything in a single .pptx (or single .key bundle if .pptx is
  unavailable). No multi-file outputs.

When you are done, output:
1. The .pptx file.
2. A markdown table mapping slide # → headline → speaker-note word count.
3. The first 3 slides rendered as PNG previews at 1920×1080 so I can sanity
   check the typography before exporting.
===
```

---

## How to use this prompt

1. **Open your deck generator** (Gamma, Tome, ChatGPT-Slides, Claude + Canva,
   Slidesgo AI, …) and paste the block between the `===` markers above.
2. **Attach the pitch document** (`docs/pitch/roadpulse_pitch.md`) as a
   reference so the assistant has the underlying numbers and architecture.
3. **Iterate twice**:
   - First pass: structure check — does every slide above appear in the
     order listed? Are all six revenue streams visible on slide 10?
   - Second pass: design check — do all slides use only the five colours,
     three font sizes and lucide-style icons?
4. **Export to `.pptx`** and review for the four most common mistakes:
   - English bleeding into slide 19 (it must remain Russian-only)
   - Cliché stock imagery on slides 1, 2, 24
   - Inventing customer names or MAU figures (replace with `«TBD»`)
   - More than 26 slides total

5. **For the Skolkovo cut** specifically, swap slides 19 + 20 to the top of
   the privacy-and-risk block (between slides 17 and 18) so the Russian
   summary lands while the audience is still warm.

## Naming, voice, and tone

- Always refer to the company as **RoadPulse** (one word, no space).
- The founders are **"we"**, never "the team" or "RoadPulse" in the third
  person.
- The product is **"Smart Trip"** for B2C, **"Dispatch / Toll Yield /
  Site Selection / Fleet Match"** for B2B, **"Trigger Feed"** for B2B2C.
- Avoid the word **"revolutionary"**. Replace with **"infrastructural"**.
- Avoid **"world-class"**. Replace with the specific benchmark we beat.

## What goes in the speaker notes

Each slide's speaker notes should answer **one** of the following questions
and nothing else (90 words or fewer, written in the founder's voice):

| Slide | Speaker-note question                                                  |
| ----- | ---------------------------------------------------------------------- |
| 1     | Why this room, why us, why now (90 words, the elevator pitch)          |
| 2     | Why those three numbers and not the others                             |
| 3-5   | What changed in the last 24 months that makes this feasible            |
| 6-8   | Walk through one screenshot per surface; surface a quantified claim    |
| 9     | Which moat compounds fastest and why                                   |
| 10-12 | One stress-test the model survives (e.g. monsoon-skip year)            |
| 13-14 | Why we'll win Lazada Logistics specifically                            |
| 15    | What we believe about the team that the resumes don't show             |
| 16-17 | Where the architecture is over-engineered, where it is under-engineered |
| 18    | Which weak spot keeps the CEO up at night                              |
| 19    | (Russian only) Какой урок мы выучили от Skolkovo предыдущего набора     |
| 20-21 | What we'll cut if the round closes 30% short                           |
| 22-23 | What we won't compromise on regardless of valuation                    |
| 24    | The closing sentence we want the audience to repeat to a colleague     |

---

*This is the prompt — not the deck. The deck-generating assistant will
produce the actual `.pptx`. The founders own the final read-through.*
