/**
 * Trip state — last queried OD pair, selected variant, in-trip telemetry.
 * Persisted to AsyncStorage so the app re-opens to the user's last route.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";
import type { LatLon, RouteResponse, RouteVariantName } from "@/lib/api";

type Telemetry = {
  startedAtMs: number | null;
  bumpsDetected: number;
  helmetOk: boolean;
};

type TripState = {
  origin: LatLon | null;
  destination: LatLon | null;
  routes: RouteResponse | null;
  selected: RouteVariantName;
  telemetry: Telemetry;
  setOd(origin: LatLon, destination: LatLon): void;
  setRoutes(routes: RouteResponse): void;
  select(variant: RouteVariantName): void;
  startTrip(): void;
  endTrip(): void;
};

const TELEMETRY_EMPTY: Telemetry = { startedAtMs: null, bumpsDetected: 0, helmetOk: true };

export const useTripStore = create<TripState>((set, get) => ({
  origin: null,
  destination: null,
  routes: null,
  selected: "safe",
  telemetry: TELEMETRY_EMPTY,
  setOd(origin, destination) {
    set({ origin, destination });
    void AsyncStorage.setItem("roadpulse:od", JSON.stringify({ origin, destination }));
  },
  setRoutes(routes) {
    set({ routes });
  },
  select(variant) {
    set({ selected: variant });
  },
  startTrip() {
    set({ telemetry: { ...TELEMETRY_EMPTY, startedAtMs: Date.now() } });
  },
  endTrip() {
    set({ telemetry: TELEMETRY_EMPTY });
  },
}));

export async function rehydrate(): Promise<void> {
  const raw = await AsyncStorage.getItem("roadpulse:od");
  if (!raw) return;
  try {
    const parsed = JSON.parse(raw) as { origin: LatLon; destination: LatLon };
    useTripStore.getState().setOd(parsed.origin, parsed.destination);
  } catch {
    /* corrupted storage — ignore */
  }
}
