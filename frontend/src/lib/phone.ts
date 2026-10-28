import {
  Metadata,
  getCountries,
  getCountryCallingCode,
  parsePhoneNumberFromString,
} from "libphonenumber-js/core"
import metadata from "libphonenumber-js/metadata.min.json"

/** Format property/host phone numbers and support international guest numbers. */

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
  nigeria: "234",
  ng: "234",
  ethiopia: "251",
  et: "251",
  tanzania: "255",
  tz: "255",

  // Rest of the Arab world, with Arabic names (the desk UI ships in Arabic)
  yemen: "967",
  ye: "967",
  "اليمن": "967",
  jordan: "962",
  jo: "962",
  "الأردن": "962",
  iraq: "964",
  iq: "964",
  "العراق": "964",
  syria: "963",
  sy: "963",
  "سوريا": "963",
  lebanon: "961",
  lb: "961",
  "لبنان": "961",
  palestine: "970",
  ps: "970",
  "فلسطين": "970",
  morocco: "212",
  ma: "212",
  "المغرب": "212",
  algeria: "213",
  dz: "213",
  "الجزائر": "213",
  tunisia: "216",
  tn: "216",
  "تونس": "216",
  libya: "218",
  ly: "218",
  "ليبيا": "218",
  sudan: "249",
  sd: "249",
  "السودان": "249",
  "مصر": "20",
  "السعودية": "966",
  "الإمارات": "971",
  "قطر": "974",
  "الكويت": "965",
  "عمان": "968",
  "عُمان": "968",
  "البحرين": "973",

  // Rest of Asia
  iran: "98",
  ir: "98",
  afghanistan: "93",
  af: "93",
  cambodia: "855",
  kh: "855",
  myanmar: "95",
  mm: "95",
  laos: "856",
  la: "856",
}

/** Resolve every supported country, retaining the existing city/name aliases. */
const countries = getCountries(metadata)
for (const language of ["en", "es", "ar", "pt"]) {
  const names = new Intl.DisplayNames([language], { type: "region" })
  for (const country of countries) {
    const dial = getCountryCallingCode(country, metadata)
    DIAL_BY_COUNTRY[country.toLowerCase()] = dial
    const name = names.of(country)
    if (name) DIAL_BY_COUNTRY[name.toLowerCase()] = dial
  }
}

/** All country and international-service calling codes, independent of the hotel. */
export const PHONE_DIAL_CODES = [
  ...new Set([
    ...countries.map((country) => getCountryCallingCode(country, metadata)),
    ...Object.keys(metadata.nonGeographic ?? {}),
  ]),
].sort((a, b) => Number(a) - Number(b))

const dialPrefixes = [...PHONE_DIAL_CODES].sort((a, b) => b.length - a.length)
const lengthsByDial = new Map<string, Set<number>>()
const plans = new Metadata(metadata)
for (const country of countries) {
  const dial = getCountryCallingCode(country, metadata)
  plans.selectNumberingPlan(country)
  const lengths = lengthsByDial.get(dial) ?? new Set<number>()
  for (const length of plans.numberingPlan?.possibleLengths() ?? []) {
    // E.164 permits at most 15 digits including the calling code.
    if (length + dial.length <= 15) lengths.add(length)
  }
  lengthsByDial.set(dial, lengths)
}

/** How many digits the national part may have, including shared calling codes. */
export function phoneLengthForDial(dial: string): { min: number; max: number } {
  const lengths = lengthsByDial.get(dial)
  if (lengths?.size) return { min: Math.min(...lengths), max: Math.max(...lengths) }
  return { min: 4, max: 15 - dial.length }
}

export function dialForCountry(country?: string | null): string {
  const key = (country ?? "").trim().toLowerCase()
  // An unrecognised country must not silently assign an Indian phone number.
  return DIAL_BY_COUNTRY[key] ?? ""
}

/** Keep significant leading zeros, for example on Italian landline numbers. */
function digitsOnly(raw: string): string {
  return raw.replace(/\D/g, "")
}

function knownDialPrefix(digits: string): string | undefined {
  return dialPrefixes.find((dial) => digits.startsWith(dial))
}

function parsedInternational(dial: string, local: string) {
  if (!dial || !local) return undefined
  return parsePhoneNumberFromString(`+${dial}${local}`, { extract: false }, metadata)
}

/**
 * An explicit +/00 code always belongs to the phone, even at a hotel abroad.
 * Only numbers without their own code use the property's country as a default.
 */
export function splitPhone(
  phone: string | null | undefined,
  country?: string | null,
): { dial: string; local: string } {
  const raw = (phone ?? "").trim()
  const defaultDial = dialForCountry(country)
  if (!raw) return { dial: defaultDial, local: "" }
  if (raw.startsWith("+") || raw.startsWith("00")) {
    const digits = digitsOnly(raw.slice(raw.startsWith("+") ? 1 : 2))
    const dial = knownDialPrefix(digits)
    // Preserve an unrecognised international number for correction rather than
    // attaching the hotel's code and changing the number's destination.
    if (!dial) return { dial: "", local: digits }
    const local = digits.slice(dial.length)
    return { dial, local: parsedInternational(dial, local)?.nationalNumber ?? local }
  }
  let local = digitsOnly(raw)
  const { min, max } = phoneLengthForDial(defaultDial)
  // Legacy values may contain a country code without a leading +. Strip it
  // only when the complete value is too long to be a national number.
  if (defaultDial && local.startsWith(defaultDial) && local.length > max) {
    const national = local.slice(defaultDial.length)
    if (national.length >= min && national.length <= max) local = national
  }
  return {
    dial: defaultDial,
    local: parsedInternational(defaultDial, local)?.nationalNumber ?? local,
  }
}

/** Recombine a selected calling code and national number for storage. */
export function joinPhone(dial: string, local: string): string {
  const digits = digitsOnly(local)
  if (!digits) return ""
  return parsedInternational(dial, digits)?.number ?? (dial ? `+${dial}${digits}` : digits)
}

/** Display the correct international grouping for the number's own country. */
export function formatPhoneDisplay(
  phone: string | null | undefined,
  country?: string | null,
): string {
  if (!phone?.trim()) return ""
  const { dial, local } = splitPhone(phone, country)
  const parsed = parsedInternational(dial, local)
  if (parsed?.isPossible()) return parsed.formatInternational()
  if (dial) return `+${dial}${local ? ` ${local}` : ""}`
  return phone.trim()
}

/** tel: href value, retaining a foreign number's own calling code. */
export function formatPhoneTel(
  phone: string | null | undefined,
  country?: string | null,
): string {
  if (!phone?.trim()) return ""
  const { dial, local } = splitPhone(phone, country)
  if (dial) return joinPhone(dial, local)
  const raw = phone.trim()
  if (raw.startsWith("+") || raw.startsWith("00")) {
    return `+${digitsOnly(raw.slice(raw.startsWith("+") ? 1 : 2))}`
  }
  return digitsOnly(raw)
}

/** Phone is optional; a supplied number must fit its own calling code. */
export function isPhoneComplete(
  phone: string | null | undefined,
  country?: string | null,
): boolean {
  if (!phone?.trim()) return true
  const { dial, local } = splitPhone(phone, country)
  if (!dial || !local || dial.length + local.length > 15) return false
  return parsedInternational(dial, local)?.isPossible() ?? false
}
