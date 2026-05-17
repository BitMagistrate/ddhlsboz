/**
 * Root layout for expo-router. Wraps every screen in QueryClient + safe area.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { rehydrate } from "@/store/trip";

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

export default function RootLayout() {
  useEffect(() => {
    void rehydrate();
  }, []);
  return (
    <QueryClientProvider client={qc}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        <Stack screenOptions={{ headerStyle: { backgroundColor: "#0F172A" }, headerTintColor: "white" }}>
          <Stack.Screen name="index" options={{ title: "Smart Trip" }} />
          <Stack.Screen name="floods" options={{ title: "Flood overlay" }} />
          <Stack.Screen name="wallet" options={{ title: "VETC Pay" }} />
        </Stack>
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
