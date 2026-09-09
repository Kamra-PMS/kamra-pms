/** Format property/host phone numbers for guest-facing pages.
 *  Always include an international dial code so guests can tap-to-call. */

/**
 * Country (or ISO code) to international dial code. Keys are lower-cased and
 * matched exactly, so common spellings and emirate/city names guests actually
 * write get their own alias - "dubai" must not fall through to the default.
 */
const DIAL_BY_COUNTRY: Record<string, string> = {
  // India and neighbours
  india: "91",
  in: "91",
  nepal: "977",
  np: "977",
  "sri lanka": "94",
  lk: "94",
  bangladesh: "880",
  bd: "880",
  maldives: "960",
  mv: "960",
  bhutan: "975",
  bt: "975",
  pakistan: "92",
  pk: "92",

  // Gulf - the emirates are commonly written in place of the country
  "united arab emirates": "971",
  uae: "971",
  "u.a.e.": "971",
  emirates: "971",
  ae: "971",
  dubai: "971",
  "abu dhabi": "971",
  sharjah: "971",
  "saudi arabia": "966",
  ksa: "966",
  sa: "966",
  qatar: "974",
  qa: "974",
  oman: "968",
  om: "968",
  kuwait: "965",
  kw: "965",
  bahrain: "973",
  bh: "973",

  // Americas
  "united states": "1",
  usa: "1",
  us: "1",
  "united states of america": "1",
  canada: "1",
  ca: "1",
  mexico: "52",
  mx: "52",
  brazil: "55",
  br: "55",

  // Europe
  "united kingdom": "44",
  uk: "44",
  gb: "44",
  england: "44",
  ireland: "353",
  ie: "353",
  germany: "49",
  de: "49",
  france: "33",
  fr: "33",
  italy: "39",
  it: "39",
  spain: "34",
  es: "34",
  portugal: "351",
  pt: "351",
  netherlands: "31",
  nl: "31",
  belgium: "32",
  be: "32",
  switzerland: "41",
  ch: "41",
  austria: "43",
  at: "43",
  sweden: "46",
  se: "46",
  norway: "47",
  no: "47",
  denmark: "45",
  dk: "45",
  poland: "48",
  pl: "48",
  greece: "30",
  gr: "30",
  russia: "7",
  ru: "7",
  turkey: "90",
  tr: "90",

  // Asia-Pacific
  china: "86",
  cn: "86",
  "hong kong": "852",
  hk: "852",
  japan: "81",
  jp: "81",
  "south korea": "82",
  kr: "82",
  thailand: "66",
  th: "66",
  malaysia: "60",
  my: "60",
  indonesia: "62",
  id: "62",
  vietnam: "84",
  vn: "84",
  philippines: "63",
  ph: "63",
  singapore: "65",
  sg: "65",
  australia: "61",
  au: "61",
  "new zealand": "64",
  nz: "64",

  // Africa and Middle East
  "south africa": "27",
  za: "27",
  kenya: "254",
  ke: "254",
  egypt: "20",
  eg: "20",
  mauritius: "230",
  mu: "230",
  israel: "972",
  il: "972",
}

/**
 * National-number digit counts per dial code, for the countries above.
 * A range covers countries where landline and mobile differ in length
 * (UK landlines run 9-10 digits, UAE 8-9); most are a single fixed length.
 * Counts exclude the dial code and any trunk "0".
 */
const LENGTH_BY_DIAL: Record<string, { min: number; max: number }> = {
  // South Asia
  "91": { min: 10, max: 10 }, // India
  "977": { min: 8, max: 10 }, // Nepal - 8 landline, 10 mobile
  "94": { min: 9, max: 9 }, // Sri Lanka
  "880": { min: 9, max: 10 }, // Bangladesh
  "960": { min: 7, max: 7 }, // Maldives
  "975": { min: 8, max: 8 }, // Bhutan
  "92": { min: 10, max: 10 }, // Pakistan

  // Gulf
  "971": { min: 8, max: 9 }, // UAE - incl. Dubai, Abu Dhabi
  "966": { min: 9, max: 9 }, // Saudi Arabia
  "974": { min: 8, max: 8 }, // Qatar
  "968": { min: 8, max: 8 }, // Oman
  "965": { min: 8, max: 8 }, // Kuwait
  "973": { min: 8, max: 8 }, // Bahrain

  // Americas
  "1": { min: 10, max: 10 }, // US / Canada
  "52": { min: 10, max: 10 }, // Mexico
  "55": { min: 10, max: 11 }, // Brazil

  // Europe
  "44": { min: 9, max: 10 }, // UK
  "353": { min: 7, max: 9 }, // Ireland
  "49": { min: 6, max: 11 }, // Germany - unusually variable
  "33": { min: 9, max: 9 }, // France
  "39": { min: 9, max: 11 }, // Italy
  "34": { min: 9, max: 9 }, // Spain
  "351": { min: 9, max: 9 }, // Portugal
  "31": { min: 9, max: 9 }, // Netherlands
  "32": { min: 8, max: 9 }, // Belgium
  "41": { min: 9, max: 9 }, // Switzerland
  "43": { min: 7, max: 13 }, // Austria - unusually variable
  "46": { min: 7, max: 9 }, // Sweden
  "47": { min: 8, max: 8 }, // Norway
  "45": { min: 8, max: 8 }, // Denmark
  "48": { min: 9, max: 9 }, // Poland
  "30": { min: 10, max: 10 }, // Greece
  "7": { min: 10, max: 10 }, // Russia / Kazakhstan
  "90": { min: 10, max: 10 }, // Turkey

  // Asia-Pacific
  "86": { min: 10, max: 11 }, // China
  "852": { min: 8, max: 8 }, // Hong Kong
  "81": { min: 9, max: 10 }, // Japan
  "82": { min: 9, max: 10 }, // South Korea
  "66": { min: 8, max: 9 }, // Thailand
  "60": { min: 9, max: 10 }, // Malaysia
  "62": { min: 9, max: 12 }, // Indonesia
  "84": { min: 9, max: 9 }, // Vietnam
  "63": { min: 10, max: 10 }, // Philippines
  "65": { min: 8, max: 8 }, // Singapore
  "61": { min: 9, max: 9 }, // Australia
  "64": { min: 8, max: 10 }, // New Zealand

  // Africa and Middle East
  "27": { min: 9, max: 9 }, // South Africa
  "254": { min: 9, max: 9 }, // Kenya
  "20": { min: 10, max: 10 }, // Egypt
  "230": { min: 7, max: 8 }, // Mauritius
  "972": { min: 9, max: 9 }, // Israel
}

/** E.164 caps a full number at 15 digits, so an unlisted code gets the slack. */
const DEFAULT_LENGTH = { min: 4, max: 15 }

/** How many digits the local part may have, for a given dial code. */
export function phoneLengthForDial(dial: string): { min: number; max: number } {
  const spec = LENGTH_BY_DIAL[dial]
  if (spec) return spec
  const room = 15 - dial.length
  return { min: DEFAULT_LENGTH.min, max: Math.min(DEFAULT_LENGTH.max, room) }
}

export function dialForCountry(country?: string | null): string {
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
  // Strip an embedded country code, e.g. "919148869914" -> "9148869914".
  // Guard on length > 10: a plain 10-digit local number (India) can itself
  // start with "91" (e.g. 9148869914) and must NOT be stripped.
  if (local.length > 10 && local.startsWith(dial)) {
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
  if (local.length > 10 && local.startsWith(dial)) {
    local = local.slice(dial.length)
  }
  return `+${dial}${local}`
}

/**
 * Split a stored number into its dial code and the local part, for inputs that
 * render the code as a fixed prefix. Falls back to the property's country when
 * the stored value carries no code of its own.
 */
export function splitPhone(
  phone: string | null | undefined,
  country?: string | null,
): { dial: string; local: string } {
  const dial = dialForCountry(country)
  const raw = (phone || "").trim()
  if (!raw) return { dial, local: "" }
  if (raw.startsWith("+")) {
    // joinPhone always writes a leading "+", so the code here is unambiguous
    // even mid-typing: "+919" is a 1-digit local number, not "919".
    const digits = digitsOnly(raw.slice(1))
    return {
      dial,
      local: digits.startsWith(dial) ? digits.slice(dial.length) : digits,
    }
  }
  // stored without a code: only strip one that sits in front of a full local
  // number, since a 10-digit Indian number can itself start with "91"
  const digits = digitsOnly(raw)
  if (digits.length > 10 && digits.startsWith(dial)) {
    return { dial, local: digits.slice(dial.length) }
  }
  return { dial, local: digits }
}

/** Recombine a prefixed input back into storage form, e.g. `+919148869914`. */
export function joinPhone(dial: string, local: string): string {
  const digits = digitsOnly(local)
  return digits ? `+${dial}${digits}` : ""
}

/** Trim a local part to the most digits its country allows. */
export function clampLocal(local: string, dial: string): string {
  return digitsOnly(local).slice(0, phoneLengthForDial(dial).max)
}

/**
 * Is this a complete number for its country? Empty counts as valid: phone is
 * optional on a booking, so only a half-typed number should block anything.
 */
export function isPhoneComplete(
  phone: string | null | undefined,
  country?: string | null,
): boolean {
  const { dial, local } = splitPhone(phone, country)
  if (!local) return true
  const { min, max } = phoneLengthForDial(dial)
  return local.length >= min && local.length <= max
}
