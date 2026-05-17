/** Shared colour palette + spacing for the Smart Trip app. */
export const palette = {
  pulse: "#2563EB",
  hazard: "#F59E0B",
  river: "#0F172A",
  ink: "#0B1426",
  surface: "#FFFFFF",
  surfaceMuted: "#F1F5F9",
  good: "#16A34A",
  bad: "#DC2626",
} as const;

export const radius = { sm: 6, md: 10, lg: 16, pill: 999 } as const;

export const variantColour: Record<"fast" | "safe" | "eco", string> = {
  fast: palette.pulse,
  safe: palette.hazard,
  eco: palette.good,
};
