/** Format property/host phone numbers for guest-facing pages.
 *  Always include an international dial code so guests can tap-to-call. */

const DIAL_BY_COUNTRY: Record<string, string> = {
  india: "91",
  in: "91",
  "united arab emirates": "971",
  uae: "971",
  ae: "971",
  "united states": "1",
  usa: "1",
  us: "1",
  "united kingdom": "44",
  uk: "44",
  gb: "44",
  singapore: "65",
  sg: "65",
  australia: "61",
  au: "61",
}

function dialForCountry(country?: string | null): string {
  const key = (country || "India").trim().toLowerCase()
  return DIAL_BY_COUNTRY[key] || "91"
}

/** Digits only, drop a leading trunk 0. */
function digitsOnly(raw: string): string {
  return raw.replace(/\D/g, "").replace(/^0+/, "")
}

/**
 * Display form, e.g. `+91 91488 69914`.
 * Leaves numbers that already start with `+` intact (normalized spacing).
 */
export function formatPhoneDisplay(
  phone: string | null | undefined,
  country?: string | null,
): string {
  if (!phone?.trim()) return ""
  const raw = phone.trim()
  if (raw.startsWith("+")) {
    const rest = digitsOnly(raw.slice(1))
    if (!rest) return raw
    // +91XXXXXXXXXX → +91 XXXXX XXXXX-ish grouping by country code length
    if (rest.length > 10) {
      const cc = rest.slice(0, rest.length - 10)
      const local = rest.slice(-10)
      return `+${cc} ${local.slice(0, 5)} ${local.slice(5)}`
    }
    return `+${rest}`
  }
  const dial = dialForCountry(country)
  let local = digitsOnly(raw)
  // Strip country code if already present without +
  if (local.startsWith(dial) && local.length > dial.length + 6) {
    local = local.slice(dial.length)
  }
  if (local.length === 10) {
    return `+${dial} ${local.slice(0, 5)} ${local.slice(5)}`
  }
  return `+${dial} ${local}`
}

/** tel: href value, e.g. `+919148869914`. */
export function formatPhoneTel(
  phone: string | null | undefined,
  country?: string | null,
): string {
  if (!phone?.trim()) return ""
  const raw = phone.trim()
  if (raw.startsWith("+")) {
    return `+${digitsOnly(raw.slice(1))}`
  }
  const dial = dialForCountry(country)
  let local = digitsOnly(raw)
  if (local.startsWith(dial) && local.length > dial.length + 6) {
    local = local.slice(dial.length)
  }
  return `+${dial}${local}`
}
