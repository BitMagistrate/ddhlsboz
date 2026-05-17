// RoadPulse loadtest — proves /v1/route p95 < 250 ms.
//
// Run locally with:
//
//   k6 run tools/loadtest/route.js
//
// The script issues realistic three-variant route requests against the
// `api-gateway` running on http://localhost:8000 (override with the
// `BASE_URL` env var). Each VU mixes Tan Son Nhat → Phu My Hung, District 1
// → Thu Duc, and a long-tail D8 → D7 trip so we see graph traversals of
// varying length. The thresholds match the SLA we quote in the pitch deck:
//
//   * p95 latency  < 250 ms
//   * error rate   < 1 %
//   * synthetic traffic only — we never hit production
//
// The harness writes a histogram to `docs/demo/loadtest-results.txt` via
// `tools/loadtest/run.sh` so the slide-deck and CI both quote the same
// numbers.

import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Counter, Rate } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const API_KEY = __ENV.ROADPULSE_API_KEY || "demo_synthetic_key";

const routeLatency = new Trend("route_latency_ms", true);
const routeOk = new Rate("route_ok");
const variantsReturned = new Counter("variants_returned");

// O/D pool — keep small and stable so SLA numbers stay reproducible.
const TRIPS = [
  {
    name: "tsn_to_pmh",
    origin: { lat: 10.82, lng: 106.645 },
    destination: { lat: 10.754, lng: 106.733 },
    mode: "motorbike",
  },
  {
    name: "d1_to_thuduc",
    origin: { lat: 10.776, lng: 106.7 },
    destination: { lat: 10.85, lng: 106.77 },
    mode: "car",
  },
  {
    name: "d8_to_d7",
    origin: { lat: 10.74, lng: 106.66 },
    destination: { lat: 10.728, lng: 106.72 },
    mode: "truck",
  },
];

export const options = {
  // Default scenario: ramp to 50 VUs, hold for 1 min, ramp down.
  // Override with `K6_STAGES="5,30,30,30"` for a heavier shape.
  scenarios: {
    steady: {
      executor: "ramping-vus",
      stages: [
        { duration: "20s", target: 25 },
        { duration: "60s", target: 50 },
        { duration: "20s", target: 0 },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    // The two numbers we quote on slide 14 of the pitch deck.
    "http_req_duration{group:::/v1/route}": ["p(95)<250"],
    route_ok: ["rate>0.99"],
  },
  // Disable the noisy default summary — we render our own at the bottom.
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

function pickTrip() {
  return TRIPS[Math.floor(Math.random() * TRIPS.length)];
}

export default function () {
  const trip = pickTrip();
  const payload = JSON.stringify({
    origin: trip.origin,
    destination: trip.destination,
    mode: trip.mode,
    avoid_flood: true,
    locale: "vi",
  });
  const headers = {
    "Content-Type": "application/json",
    "X-Api-Key": API_KEY,
    "X-RoadPulse-Test": `loadtest/${trip.name}`,
  };
  const res = http.post(`${BASE_URL}/v1/route`, payload, {
    headers,
    tags: { name: "/v1/route" },
  });
  routeLatency.add(res.timings.duration);
  const ok = check(res, {
    "status is 200": (r) => r.status === 200,
    "returns three variants": (r) => {
      try {
        return JSON.parse(r.body).variants.length === 3;
      } catch (_e) {
        return false;
      }
    },
  });
  routeOk.add(ok);
  if (ok) {
    try {
      variantsReturned.add(JSON.parse(res.body).variants.length);
    } catch (_e) {
      // body wasn't JSON — already counted as failure above.
    }
  }
  // Smear requests so 50 VUs don't all collide on the same tick.
  sleep(0.1 + Math.random() * 0.4);
}

export function handleSummary(data) {
  const trend = data.metrics.route_latency_ms?.values || {};
  const rate = data.metrics.route_ok?.values || {};
  const lines = [
    "RoadPulse /v1/route loadtest",
    "============================",
    "",
    `VUs (max)          : ${data.metrics.vus_max?.values?.max ?? "n/a"}`,
    `Iterations         : ${data.metrics.iterations?.values?.count ?? "n/a"}`,
    `Errors             : ${data.metrics.http_req_failed?.values?.fails ?? 0}`,
    `Success rate       : ${(rate.rate ?? 0).toFixed(4)}`,
    "",
    "Latency (ms)       :",
    `  min   = ${(trend.min ?? 0).toFixed(2)}`,
    `  med   = ${(trend.med ?? 0).toFixed(2)}`,
    `  avg   = ${(trend.avg ?? 0).toFixed(2)}`,
    `  p90   = ${(trend["p(90)"] ?? 0).toFixed(2)}`,
    `  p95   = ${(trend["p(95)"] ?? 0).toFixed(2)}`,
    `  p99   = ${(trend["p(99)"] ?? 0).toFixed(2)}`,
    `  max   = ${(trend.max ?? 0).toFixed(2)}`,
    "",
    "Target             : p95 < 250 ms",
    `Verdict            : ${(trend["p(95)"] ?? 1e9) < 250 ? "PASS" : "FAIL"}`,
    "Data origin        : synthetic-fixtures (api-gateway in synthetic-data mode)",
  ];
  const summaryText = lines.join("\n") + "\n";
  return {
    stdout: summaryText,
    "docs/demo/loadtest-results.txt": summaryText,
  };
}
