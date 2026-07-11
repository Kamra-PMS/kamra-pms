/** Booking-page accent. The admin picks any colour (a hex); the full
 * 50/100/600/700/900 ramp the UI needs is derived from it. A few presets are
 * offered as quick swatches, and older named values (Emerald, Ocean…) still
 * resolve for backward compatibility. */

export const PRESETS: { name: string; hex: string }[] = [
  { name: "Emerald", hex: "#0f6b54" },
  { name: "Ocean", hex: "#0369a1" },
  { name: "Royal", hex: "#4f46e5" },
  { name: "Sunset", hex: "#c2410c" },
  { name: "Burgundy", hex: "#be123c" },
  { name: "Slate", hex: "#334155" },
]
const PRESET_HEX: Record<string, string> = Object.fromEntries(
  PRESETS.map((p) => [p.name, p.hex]),
)

const DEFAULT = "#0f6b54"

function toRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "")
  const n = h.length === 3 ? h.split("").map((c) => c + c).join("") : h
  const v = parseInt(n, 16)
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255]
}
function toHex([r, g, b]: number[]): string {
  return "#" + [r, g, b].map((x) => Math.round(x).toString(16).padStart(2, "0")).join("")
}
/** Blend a colour toward white (ratio>0) or black; ratio 0..1. */
function mix(hex: string, target: number, ratio: number): string {
  const [r, g, b] = toRgb(hex)
  return toHex([r, g, b].map((c) => c + (target - c) * ratio))
}

/** Resolve any stored value (hex, preset name, or empty) to a hex. */
export function accentHex(value: string | null | undefined): string {
  if (!value) return DEFAULT
  if (value.startsWith("#")) return value
  return PRESET_HEX[value] ?? DEFAULT
}

/** The 5-stop ramp the app's --color-brand-* variables expect. */
export function accentRamp(value: string | null | undefined) {
  const base = accentHex(value)
  return {
    50: mix(base, 255, 0.92),
    100: mix(base, 255, 0.82),
    600: base,
    700: mix(base, 0, 0.16),
    900: mix(base, 0, 0.45),
  }
}

/** Inline style that re-points the brand CSS variables for a subtree. */
export function accentVars(value: string | null | undefined) {
  const a = accentRamp(value)
  return {
    "--color-brand-50": a[50],
    "--color-brand-100": a[100],
    "--color-brand-600": a[600],
    "--color-brand-700": a[700],
    "--color-brand-900": a[900],
  } as React.CSSProperties
}
