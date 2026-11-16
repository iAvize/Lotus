export type ThemeName = "purple" | "blue" | "red" | "pink" | "green" | "orange";

export type Palette = {
  bg: string;
  panel: string;
  border: string;
  accent: string;
  accentLight: string;
  text: string;
  sub: string;
  input: string;
};

export const PALETTES: Record<ThemeName, Palette> = {
  purple: {
    bg: "#080512", panel: "rgba(23, 13, 43, 0.92)", border: "#4c2a7d",
    accent: "#8b5cf6", accentLight: "#a78bfa", text: "#e9d5ff",
    sub: "#a78bfa", input: "#130b24",
  },
  blue: {
    bg: "#04121f", panel: "rgba(10, 28, 48, 0.92)", border: "#1d4e79",
    accent: "#38bdf8", accentLight: "#7dd3fc", text: "#dbeafe",
    sub: "#93c5fd", input: "#0a1a2f",
  },
  red: {
    bg: "#160608", panel: "rgba(48, 12, 16, 0.92)", border: "#7f1d1d",
    accent: "#ef4444", accentLight: "#fca5a5", text: "#fee2e2",
    sub: "#fca5a5", input: "#2a0a0d",
  },
  pink: {
    bg: "#160512", panel: "rgba(45, 12, 38, 0.92)", border: "#86198f",
    accent: "#ec4899", accentLight: "#f9a8d4", text: "#fce7f3",
    sub: "#f9a8d4", input: "#26091c",
  },
  green: {
    bg: "#04120b", panel: "rgba(8, 38, 24, 0.92)", border: "#166534",
    accent: "#22c55e", accentLight: "#86efac", text: "#dcfce7",
    sub: "#86efac", input: "#071f14",
  },
  orange: {
    bg: "#160c04", panel: "rgba(48, 24, 8, 0.92)", border: "#9a3412",
    accent: "#f97316", accentLight: "#fdba74", text: "#ffedd5",
    sub: "#fdba74", input: "#2a1508",
  },
};

export const THEME_NAMES = Object.keys(PALETTES) as ThemeName[];
