# Smart Trip — RoadPulse B2C app

Expo (React Native) app. Renders the three-route picker (fast / safe / eco),
the H3 flood overlay, and the VETC Pay sandbox payment flow.

## Quickstart

```bash
pnpm install
pnpm --filter @roadpulse/b2c-app start
```

The Metro bundler opens at `http://localhost:8081`. Scan the QR code with the
Expo Go app, or press `i` / `a` for iOS / Android simulator.

The API base URL is read from `app.json -> expo.extra.apiBaseUrl` and defaults
to `http://localhost:8080` (the local `api-gateway`). Override per-environment
with `EXPO_PUBLIC_API_BASE_URL`.

## Screens

| Route                | Purpose                                           |
| -------------------- | ------------------------------------------------- |
| `/`                  | Trip planner with three-route picker              |
| `/floods`            | Hex-level flood overlay                           |
| `/wallet`            | VETC Pay sandbox                                  |
| `/safety`            | In-trip alerts (panic, helmet check, low battery) |

## Design system

Tailwind-style utility classes via `nativewind`. Colour palette inspired by
the Saigon River — pulse blue `#2563EB`, hazard amber `#F59E0B`, river slate
`#0F172A`.
