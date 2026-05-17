# B2B Operator dashboard

Vite + React + TypeScript. Four product surfaces:

| Route             | Pitch reference         | Notes                                                                |
| ----------------- | ----------------------- | -------------------------------------------------------------------- |
| `/`               | Dispatch tower (§4.2.A) | Batch ETA + flood-aware re-route                                     |
| `/toll-yield`     | Toll yield (§4.2.B)     | Dynamic pricing recommendations + 5% lift chart                      |
| `/site-selection` | Site selection (§4.2.C) | Hex-level O-D flow ranking for retail / dark-store                   |
| `/fleet-match`    | Fleet match (§4.2.D)    | Load-matching marketplace ranked by ETA, bid &amp; flood safety      |

## Quickstart

```bash
pnpm install
pnpm --filter @roadpulse/b2b-dashboard dev
```

The dev server runs on <http://localhost:5174>. The API base URL is taken from
`VITE_API_BASE_URL` (default `http://localhost:8080`, the local `api-gateway`).

## Build

```bash
pnpm --filter @roadpulse/b2b-dashboard build
```

Outputs to `dist/` — bundled with Vite + Rollup, source-maps included.

## Theming

CSS variables live in `src/styles.css`. The palette mirrors the B2C app:
pulse blue `#2563EB`, hazard amber `#F59E0B`, river slate `#0F172A`.
