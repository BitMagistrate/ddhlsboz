/**
 * VETC Pay sandbox wallet view.
 *
 * The MVP implementation simulates the eToll handshake locally; the production
 * build will mount the real VETC Pay SDK once we have a partner-API token.
 */
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { palette, radius } from "@/lib/theme";

const PENDING_TOLLS = [
  { id: "toll-01", name: "Long Thanh Expressway gantry 3", amount_vnd: 45_000 },
  { id: "toll-02", name: "Cát Lái Bridge tollbooth",        amount_vnd: 15_000 },
];

export default function WalletScreen() {
  const [paid, setPaid] = useState<Record<string, boolean>>({});
  const balanceRemaining = 250_000 - PENDING_TOLLS.filter((t) => paid[t.id]).reduce((acc, t) => acc + t.amount_vnd, 0);

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.balanceCard}>
        <Text style={styles.balanceLabel}>VETC Pay balance</Text>
        <Text style={styles.balanceValue}>{balanceRemaining.toLocaleString("vi-VN")} ₫</Text>
        <Text style={styles.balanceHint}>top-up via VietQR · linked wallet ****1248</Text>
      </View>
      <Text style={styles.heading}>Pending tolls</Text>
      {PENDING_TOLLS.map((toll) => (
        <View key={toll.id} style={styles.tollRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.tollName}>{toll.name}</Text>
            <Text style={styles.tollSub}>{toll.amount_vnd.toLocaleString("vi-VN")} ₫</Text>
          </View>
          <Pressable
            style={[styles.payButton, paid[toll.id] && styles.payButtonDone]}
            disabled={paid[toll.id]}
            onPress={() => setPaid({ ...paid, [toll.id]: true })}
          >
            <Text style={styles.payLabel}>{paid[toll.id] ? "Paid" : "Pay"}</Text>
          </Pressable>
        </View>
      ))}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, padding: 20, backgroundColor: palette.surface, gap: 16 },
  heading: { fontSize: 20, fontWeight: "700", color: palette.ink },
  balanceCard: {
    backgroundColor: palette.pulse, borderRadius: radius.lg, padding: 20, gap: 4,
  },
  balanceLabel: { color: "#DBEAFE", fontWeight: "500" },
  balanceValue: { color: "white", fontWeight: "700", fontSize: 30, fontVariant: ["tabular-nums"] },
  balanceHint: { color: "#DBEAFE", marginTop: 4 },
  tollRow: {
    flexDirection: "row", alignItems: "center", padding: 14, gap: 12,
    borderRadius: radius.md, backgroundColor: palette.surfaceMuted,
  },
  tollName: { fontWeight: "600", color: palette.ink },
  tollSub: { color: "#475569" },
  payButton: { paddingHorizontal: 18, paddingVertical: 10, borderRadius: radius.pill, backgroundColor: palette.pulse },
  payButtonDone: { backgroundColor: palette.good },
  payLabel: { color: "white", fontWeight: "600" },
});
