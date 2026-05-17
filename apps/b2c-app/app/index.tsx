/**
 * Trip planner — three-route picker (fast / safe / eco) with flood overlay.
 *
 * The map view is rendered with react-native-maps; the polylines for each
 * variant are coloured per `lib/theme.variantColour`. Tap a card to switch
 * the highlighted polyline.
 */
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api, type LatLon, type RouteVariant, type RouteVariantName } from "@/lib/api";
import { palette, radius, variantColour } from "@/lib/theme";
import { useTripStore } from "@/store/trip";

const DEFAULT_ORIGIN: LatLon = { lat: 10.776, lng: 106.7 }; // District 1 HCMC
const DEFAULT_DEST: LatLon = { lat: 10.737, lng: 106.722 }; // District 7

export default function TripPlannerScreen() {
  const router = useRouter();
  const { setOd, setRoutes, routes, selected, select } = useTripStore();
  const [origin, setOrigin] = useState<LatLon>(DEFAULT_ORIGIN);
  const [destination, setDestination] = useState<LatLon>(DEFAULT_DEST);

  const findRoutes = useMutation({
    mutationFn: async () => {
      const res = await api.route(origin, destination, "motorbike");
      setOd(origin, destination);
      setRoutes(res);
      return res;
    },
  });

  const variants = useMemo<RouteVariant[]>(() => routes?.routes ?? [], [routes]);

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.heading}>Where to?</Text>

        <View style={styles.odCard}>
          <Field label="From" value={`${origin.lat.toFixed(3)}, ${origin.lng.toFixed(3)}`} />
          <Field label="To"   value={`${destination.lat.toFixed(3)}, ${destination.lng.toFixed(3)}`} />
          <Pressable
            style={[styles.ctaPrimary, findRoutes.isPending && styles.ctaDisabled]}
            disabled={findRoutes.isPending}
            onPress={() => findRoutes.mutate()}
          >
            <Text style={styles.ctaPrimaryLabel}>
              {findRoutes.isPending ? "Routing…" : "Find safe route"}
            </Text>
          </Pressable>
          {findRoutes.isError && (
            <Text style={styles.error}>{(findRoutes.error as Error).message}</Text>
          )}
        </View>

        {variants.length > 0 && (
          <View style={styles.variants}>
            <Text style={styles.subheading}>3 routes</Text>
            {variants.map((variant) => (
              <VariantCard
                key={variant.name}
                variant={variant}
                isSelected={selected === variant.name}
                onPress={() => select(variant.name as RouteVariantName)}
              />
            ))}
            <Pressable style={styles.ctaSecondary} onPress={() => router.push("/floods")}>
              <Text style={styles.ctaSecondaryLabel}>See flood overlay</Text>
            </Pressable>
            <Pressable style={styles.ctaSecondary} onPress={() => router.push("/wallet")}>
              <Text style={styles.ctaSecondaryLabel}>Pay tolls with VETC Pay</Text>
            </Pressable>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <Text style={styles.fieldValue}>{value}</Text>
    </View>
  );
}

function VariantCard({
  variant,
  isSelected,
  onPress,
}: { variant: RouteVariant; isSelected: boolean; onPress: () => void }) {
  const accent = variantColour[variant.name];
  return (
    <Pressable
      onPress={onPress}
      style={[styles.variantCard, { borderColor: isSelected ? accent : palette.surfaceMuted }]}
    >
      <View style={[styles.variantBadge, { backgroundColor: accent }]}>
        <Text style={styles.variantBadgeLabel}>{variant.name.toUpperCase()}</Text>
      </View>
      <View style={styles.variantBody}>
        <Text style={styles.variantTime}>{Math.round(variant.duration_s / 60)} min</Text>
        <Text style={styles.variantSub}>
          {(variant.distance_m / 1000).toFixed(1)} km · flood{" "}
          {(variant.flood_score * 100).toFixed(0)}% · tolls{" "}
          {variant.toll_estimate_vnd.toLocaleString("vi-VN")} ₫
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: palette.surface },
  container: { padding: 20, gap: 18 },
  heading: { fontSize: 28, fontWeight: "700", color: palette.ink },
  subheading: { fontSize: 18, fontWeight: "600", color: palette.ink, marginBottom: 8 },
  odCard: { backgroundColor: palette.surfaceMuted, borderRadius: radius.lg, padding: 16, gap: 12 },
  field: { gap: 4 },
  fieldLabel: { fontSize: 12, color: "#475569", textTransform: "uppercase", letterSpacing: 0.6 },
  fieldValue: { fontSize: 16, color: palette.ink },
  ctaPrimary: {
    marginTop: 4, paddingVertical: 14, borderRadius: radius.md, alignItems: "center",
    backgroundColor: palette.pulse,
  },
  ctaDisabled: { opacity: 0.6 },
  ctaPrimaryLabel: { color: "white", fontWeight: "600", fontSize: 16 },
  ctaSecondary: {
    paddingVertical: 12, borderRadius: radius.md, alignItems: "center",
    borderWidth: 1, borderColor: palette.pulse,
  },
  ctaSecondaryLabel: { color: palette.pulse, fontWeight: "600" },
  variants: { gap: 12 },
  variantCard: {
    flexDirection: "row", alignItems: "center", gap: 14, padding: 14,
    borderRadius: radius.lg, borderWidth: 2, backgroundColor: palette.surface,
  },
  variantBadge: {
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.pill,
  },
  variantBadgeLabel: { color: "white", fontWeight: "700", letterSpacing: 0.5 },
  variantBody: { flex: 1 },
  variantTime: { fontSize: 22, fontWeight: "700", color: palette.ink },
  variantSub: { color: "#475569", marginTop: 2 },
  error: { color: palette.bad, marginTop: 4 },
});
