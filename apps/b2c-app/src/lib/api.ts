/**
 * Typed thin client for the RoadPulse public API.
 *
 * The shape mirrors `schemas/openapi/public_v1.yaml`. Only the endpoints the
 * mobile app actually consumes are wrapped — the dashboard uses its own
 * (richer) client in `apps/b2b-dashboard`.
 */
import Constants from "expo-constants";

const BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  (Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined)?.apiBaseUrl ??
  "http://localhost:8080";

export type LatLon = { lat: number; lng: number };

export type RouteVariantName = "fast" | "safe" | "eco";

export type RouteVariant = {
  name: RouteVariantName;
  distance_m: number;
  duration_s: number;
  flood_score: number;
  congestion_score: number;
  eco_score: number;
  toll_estimate_vnd: number;
  geometry: LatLon[];
  hex_path: string[];
  steps: RouteStep[];
};

export type RouteStep = {
  instruction: string;
  distance_m: number;
  duration_s: number;
  bearing_deg: number;
  flood_score: number;
};

export type RouteResponse = {
  request_id: string;
  generated_at_ms: number;
  routes: RouteVariant[];
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`RoadPulse ${path} → ${res.status} ${text}`);
  }
  return (await res.json()) as T;
}

export const api = {
  baseUrl: BASE_URL,
  route(origin: LatLon, destination: LatLon, mode: "motorbike" | "car" = "motorbike") {
    return call<RouteResponse>("/v1/route", {
      method: "POST",
      body: JSON.stringify({ origin, destination, mode, flood_aware: true }),
    });
  },
  floodOverlay(horizon: "now" | "1h" | "3h" | "6h" = "now") {
    return call<{ hexes: { hex_id: string; lat: number; lng: number; score: number }[] }>(
      `/v1/flood-risk?horizon=${horizon}`,
    );
  },
};
