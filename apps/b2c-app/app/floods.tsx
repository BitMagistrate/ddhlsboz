/**
 * Hex-level flood overlay. The user picks a horizon (now / 1h / 3h / 6h) and
 * the screen pulls the hex scores from `GET /v1/flood-risk`. Each hex is
 * coloured on a green → amber → red ramp; "wet" hexes (score ≥ 0.4) pulse
 * gently so the operator and the driver visually share the same heat map.
 */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  Animated,
  Easing,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "@/lib/api";
import { palette, radius } from "@/lib/theme";

const HORIZONS = ["now", "1h", "3h", "6h"] as const;
type Horizon = (typeof HORIZONS)[number];

type Hex = { hex_id: string; lat: number; lng: number; score: number };

export default function FloodsScreen() {
  const [horizon, setHorizon] = useState<Horizon>("now");
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["floods", horizon],
    queryFn: () => api.floodOverlay(horizon),
  });

  const hexes: Hex[] = data?.hexes ?? [];
  const wet = hexes.filter((h) => h.score >= 0.4).length;
  const mean =
    hexes.length > 0
      ? Math.round((hexes.reduce((acc, h) => acc + h.score, 0) / hexes.length) * 100)
      : 0;

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.banner}>
        <Text style={styles.bannerText}>synthetic-fixtures · not real VETC data</Text>
      </View>

      <View style={styles.tabs}>
        {HORIZONS.map((h) => (
          <Pressable
            key={h}
            onPress={() => setHorizon(h)}
            style={[styles.tab, horizon === h && styles.tabActive]}
          >
            <Text style={[styles.tabLabel, horizon === h && styles.tabLabelActive]}>{h}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.summary}>
        <Stat label="hexes" value={hexes.length.toString()} />
        <Stat label="wet (≥40%)" value={wet.toString()} tone={wet > 0 ? "hazard" : "good"} />
        <Stat label="mean" value={`${mean}%`} />
      </View>

      {isPending && <Text style={styles.muted}>Loading hex scores…</Text>}
      {isError && <Text style={styles.error}>{(error as Error).message}</Text>}
      <ScrollView contentContainerStyle={styles.list}>
        {hexes.map((hex) => (
          <HexRow key={hex.hex_id} hex={hex} />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

function HexRow({ hex }: { hex: Hex }) {
  const wet = hex.score >= 0.4;
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!wet) {
      pulse.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 800,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: 800,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, wet]);

  const scale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.6] });
  const opacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.55, 0] });
  const colour = hexColour(hex.score);

  return (
    <View style={styles.row}>
      <View style={styles.dotWrap}>
        <View style={[styles.dot, { backgroundColor: colour }]} />
        {wet && (
          <Animated.View
            style={[
              styles.dotPulse,
              { backgroundColor: colour, transform: [{ scale }], opacity },
            ]}
          />
        )}
      </View>
      <Text style={styles.rowLabel}>{hex.hex_id}</Text>
      <Text style={styles.rowScore}>{(hex.score * 100).toFixed(0)}%</Text>
    </View>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "hazard" | "good";
}) {
  const colour =
    tone === "hazard" ? palette.bad : tone === "good" ? palette.good : palette.ink;
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, { color: colour }]}>{value}</Text>
    </View>
  );
}

function hexColour(score: number): string {
  if (score >= 0.7) return palette.bad;
  if (score >= 0.4) return palette.hazard;
  return palette.good;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: palette.surface, padding: 20, gap: 12 },
  banner: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: "rgba(245,158,11,0.16)",
    alignSelf: "flex-start",
  },
  bannerText: {
    color: palette.hazard,
    fontWeight: "600",
    fontSize: 11,
    letterSpacing: 0.6,
  },
  tabs: { flexDirection: "row", gap: 8 },
  tab: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: radius.pill,
    backgroundColor: palette.surfaceMuted,
  },
  tabActive: { backgroundColor: palette.pulse },
  tabLabel: { fontWeight: "600", color: "#475569" },
  tabLabelActive: { color: "white" },
  summary: { flexDirection: "row", gap: 12 },
  stat: {
    flex: 1,
    backgroundColor: palette.surfaceMuted,
    borderRadius: radius.md,
    padding: 12,
  },
  statLabel: {
    color: "#64748B",
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  statValue: { fontSize: 22, fontWeight: "700", marginTop: 4 },
  list: { gap: 8, paddingBottom: 32 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 12,
    borderRadius: radius.md,
    backgroundColor: palette.surfaceMuted,
  },
  dotWrap: { width: 22, height: 22, alignItems: "center", justifyContent: "center" },
  dot: { width: 14, height: 14, borderRadius: 7 },
  dotPulse: { position: "absolute", width: 14, height: 14, borderRadius: 7 },
  rowLabel: { flex: 1, color: palette.ink, fontWeight: "600" },
  rowScore: { color: palette.ink, fontVariant: ["tabular-nums"] },
  muted: { color: "#64748B" },
  error: { color: palette.bad },
});
