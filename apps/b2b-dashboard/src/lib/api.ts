/**
 * Typed client for the RoadPulse public API.
 *
 * The shape mirrors `schemas/openapi/public_v1.yaml`. Only the endpoints the
 * operator dashboard actually consumes are wrapped.
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080";

export type LatLon = { lat: number; lng: number };

export type EtaPrediction = {
  order_id: string;
  eta_s: number;
  eta_p10_s: number;
  eta_p90_s: number;
  flood_score: number;
  distance_m: number;
  confidence: "low" | "medium" | "high";
};

export type BatchEtaResponse = {
  batch_id: string;
  predictions: EtaPrediction[];
};

export type EtaBatchItem = {
  order_id: string;
  origin: LatLon;
  destination: LatLon;
  mode?: "motorbike" | "car" | "truck";
  depart_at?: string;
};

export type SiteCell = {
  hex_id: string;
  origin_flows: number;
  destination_flows: number;
  rank: number;
};

export type FleetMatchCandidate = {
  fleet_id: string;
  fleet_name: string;
  vehicle_class: string;
  eta_s: number;
  bid_vnd: number;
  flood_safe: boolean;
};

export type TriggerEvent = {
  policy_id: string;
  event_id: string;
  hex_id: string;
  score: number;
  threshold: number;
  ts_ms: number;
  payout_vnd: number;
  signature_b64: string;
};

export type FloodHex = {
  hex_id: string;
  lat: number;
  lng: number;
  score: number;
};

export type HealthResponse = {
  status: "ok";
  version: string;
  data_origin: "synthetic" | "real";
  real_feeds: string[];
  pending_real_feeds: string[];
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    throw new Error(`RoadPulse ${path} → ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as T;
}

export const api = {
  baseUrl: BASE_URL,
  etaBatch(items: EtaBatchItem[]) {
    return call<BatchEtaResponse>("/v1/eta-batch", {
      method: "POST",
      body: JSON.stringify({ batch_id: crypto.randomUUID(), items }),
    });
  },
  siteSelection(bbox: { north: number; south: number; east: number; west: number }, hour: number) {
    return call<{ ranked: SiteCell[] }>("/v1/site-selection", {
      method: "POST",
      body: JSON.stringify({ bbox, hour_of_week: hour, top_n: 10 }),
    });
  },
  fleetMatch(origin: LatLon, destination: LatLon) {
    return call<{ candidates: FleetMatchCandidate[] }>("/v1/fleet-match", {
      method: "POST",
      body: JSON.stringify({ origin, destination, vehicle_class: "MOTORBIKE", max_candidates: 5 }),
    });
  },
  triggerFeed(policyId: string) {
    return call<{ policy_id: string; events: TriggerEvent[]; public_key_pem: string }>(
      `/v1/trigger-feed/${encodeURIComponent(policyId)}`,
    );
  },
  floodRisk(horizon: "now" | "1h" | "3h" | "6h" = "now") {
    return call<{ hexes: FloodHex[] }>(`/v1/flood-risk?horizon=${horizon}`);
  },
  health() {
    return call<HealthResponse>("/v1/healthz");
  },
};
