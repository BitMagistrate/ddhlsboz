/**
 * Hex-level flood overlay. The user picks a horizon (now / 1h / 3h / 6h) and
 * the screen pulls the hex scores from `GET /v1/flood-risk`. Each hex is
 * coloured on a green → red ramp.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "@/lib/api";
import { palette, radius } from "@/lib/theme";

const HORIZONS = ["now", "1h", "3h", "6h"] as const;
type Horizon = (typeof HORIZONS)[number];

export default function FloodsScreen() {
  const [horizon, setHorizon] = useState<Horizon>("now");
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["floods", horizon],
    queryFn: () => api.floodOverlay(horizon),
  });

  return (
    <SafeAreaView style={styles.screen}>
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
      {isPending && <Text style={styles.muted}>Loading hex scores…</Text>}
      {isError && <Text style={styles.error}>{(error as Error).message}</Text>}
      <ScrollView contentContainerStyle={styles.list}>
        {(data?.hexes ?? []).map((hex) => (
          <View key={hex.hex_id} style={styles.row}>
            <View style={[styles.dot, { backgroundColor: hexColour(hex.score) }]} />
            <Text style={styles.rowLabel}>{hex.hex_id}</Text>
            <Text style={styles.rowScore}>{(hex.score * 100).toFixed(0)}%</Text>
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

function hexColour(score: number): string {
  if (score >= 0.7) return palette.bad;
  if (score >= 0.4) return palette.hazard;
  return palette.good;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: palette.surface, padding: 20, gap: 16 },
  tabs: { flexDirection: "row", gap: 8 },
  tab: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: radius.pill,
    backgroundColor: palette.surfaceMuted,
  },
  tabActive: { backgroundColor: palette.pulse },
  tabLabel: { fontWeight: "600", color: "#475569" },
  tabLabelActive: { color: "white" },
  list: { gap: 8, paddingBottom: 32 },
  row: {
    flexDirection: "row", alignItems: "center", gap: 12, padding: 12,
    borderRadius: radius.md, backgroundColor: palette.surfaceMuted,
  },
  dot: { width: 14, height: 14, borderRadius: 7 },
  rowLabel: { flex: 1, color: palette.ink, fontWeight: "600" },
  rowScore: { color: palette.ink, fontVariant: ["tabular-nums"] },
  muted: { color: "#64748B" },
  error: { color: palette.bad },
});
