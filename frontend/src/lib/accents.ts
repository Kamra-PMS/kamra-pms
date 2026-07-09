/** Curated booking-page accents. A fixed set (not a free colour picker) so
 * every choice keeps AA contrast for buttons and links on white. Keys match
 * Property.brand_accent options; values map onto the --color-brand-* CSS
 * variables the Tailwind utilities read. */
export const ACCENTS: Record<
  string,
  { 50: string; 100: string; 600: string; 700: string; 900: string }
> = {
  Emerald: {
    50: "#ecf7f2",
    100: "#d2ece0",
    600: "#0f6b54",
    700: "#0b5442",
    900: "#073527",
  },
  Ocean: {
    50: "#eff8ff",
    100: "#d8edfc",
    600: "#0369a1",
    700: "#075985",
    900: "#0c4a6e",
  },
  Royal: {
    50: "#eef2ff",
    100: "#e0e7ff",
    600: "#4f46e5",
    700: "#4338ca",
    900: "#312e81",
  },
  Sunset: {
    50: "#fff7ed",
    100: "#ffedd5",
    600: "#c2410c",
    700: "#9a3412",
    900: "#7c2d12",
  },
  Burgundy: {
    50: "#fff1f2",
    100: "#ffe4e6",
    600: "#be123c",
    700: "#9f1239",
    900: "#881337",
  },
  Slate: {
    50: "#f8fafc",
    100: "#f1f5f9",
    600: "#334155",
    700: "#1e293b",
    900: "#0f172a",
  },
}

/** Inline style that re-points the brand CSS variables for a subtree. */
export function accentVars(name: string | null | undefined) {
  const a = ACCENTS[name ?? ""] ?? ACCENTS.Emerald
  return {
    "--color-brand-50": a[50],
    "--color-brand-100": a[100],
    "--color-brand-600": a[600],
    "--color-brand-700": a[700],
    "--color-brand-900": a[900],
  } as React.CSSProperties
}
