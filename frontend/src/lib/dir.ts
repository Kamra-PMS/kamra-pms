/** Interface direction / language. Stored per device (like the theme) and
 * applied to the document so the whole UI flips together. Direction comes
 * from the language registry (not a hard-coded `=== "ar"`), so Urdu/Hebrew
 * can join later without touching every call site. */

export interface LangDef {
  code: string
  /** Native name shown in the language picker, e.g. "العربية". */
  nativeLabel: string
  /** English label for the picker, e.g. "Arabic". */
  englishLabel: string
  dir: "ltr" | "rtl"
}

/** Supported UI languages. Add a row + a locales/<code>.json to ship another. */
export const LANGS: LangDef[] = [
  { code: "en", nativeLabel: "English", englishLabel: "English", dir: "ltr" },
  { code: "es", nativeLabel: "Español", englishLabel: "Spanish", dir: "ltr" },
  { code: "pt", nativeLabel: "Português", englishLabel: "Portuguese", dir: "ltr" },
  { code: "ar", nativeLabel: "العربية", englishLabel: "Arabic", dir: "rtl" },
  { code: "zh-CN", nativeLabel: "简体中文", englishLabel: "Chinese (Simplified)", dir: "ltr" },
]

export type Lang = string

// Guest pages keep their own choice: a guest (or staff previewing /book)
// picking Spanish there must not switch the desk, and the reverse.
const GUEST_PAGE = /^(\/kamra)?\/(book|stay|checkin)(\/|$)/
const key = () => (GUEST_PAGE.test(window.location.pathname) ? "kamra-guest-lang" : "kamra-lang")
const codes = new Set(LANGS.map((l) => l.code))

export function langDef(code: string): LangDef {
  return LANGS.find((l) => l.code === code) ?? LANGS[0]
}

/** Traditional Chinese tags must not fall back to the Simplified dictionary;
 *  only zh, zh-CN, zh-SG and the zh-Hans* forms are Simplified. */
const ZH_SIMPLIFIED = /^zh(?:-cn|-sg|-hans(?:-.+)?)?$/

/** Map a browser tag or stored setting onto a shipped UI language. Exact
 * tag first ("zh-CN"), then the base language, so plain "zh" and the
 * script/region forms ("zh-Hans", "zh-Hans-CN", "pt-BR") resolve too.
 * Returns null when the tag names a language we do not ship - a Traditional
 * Chinese tag ("zh-TW", "zh-HK", "zh-Hant") is one of those, so it stays
 * English instead of showing Simplified text. */
export function matchLang(tag?: string | null): Lang | null {
  const raw = (tag || "").trim().toLowerCase()
  if (!raw) return null
  const exact = LANGS.find((l) => l.code.toLowerCase() === raw)
  if (exact) return exact.code
  // The base match below would otherwise map zh-TW and zh-HK onto zh-CN.
  if (/^zh(?:-|$)/.test(raw) && !ZH_SIMPLIFIED.test(raw)) return null
  const base = raw.split("-")[0]
  return LANGS.find((l) => l.code.toLowerCase().split("-")[0] === base)?.code ?? null
}

/** The first browser language we ship, or null for the caller's default. */
function browserLanguage(): Lang | null {
  for (const tag of navigator.languages ?? [navigator.language]) {
    const hit = matchLang(tag)
    if (hit) return hit
  }
  return null
}

// A guest page's language before the guest picks one: the hotel's booking
// engine default, else the browser's. Not stored, so a later default applies.
let guestDefault: Lang | null = null

export const getLang = (): Lang => {
  let raw: string | null = null
  try {
    raw = localStorage.getItem(key())
  } catch {
    /* private mode */
  }
  raw = raw || (key() === "kamra-guest-lang" ? guestDefault : null) || "en"
  return codes.has(raw) ? raw : "en"
}

export function applyLang(l: Lang) {
  const def = langDef(l)
  const el = document.documentElement
  el.setAttribute("lang", def.code)
  el.setAttribute("dir", def.dir)
}

export function setLang(l: Lang) {
  const code = codes.has(l) ? l : "en"
  localStorage.setItem(key(), code)
  applyLang(code)
  // Load the dictionary before notifying listeners so the first paint
  // after a switch is already translated (see lib/locales.ts).
  void import("./locales").then(({ ensureDictionary }) =>
    ensureDictionary(code).then(() => {
      window.dispatchEvent(new Event("kamra:lang"))
    }),
  )
}

/** Guest pages: the guest's own pick wins; until then the hotel's booking
 * engine language (`preferred`), else the browser language. */
export function adoptGuestLanguage(preferred?: string | null) {
  const next = matchLang(preferred) ?? browserLanguage()
  if (next === guestDefault) return
  guestDefault = next
  syncLang()
}

/** Re-apply after moving between a guest page and the desk in one tab. */
export function syncLang() {
  const code = getLang()
  applyLang(code)
  void import("./locales").then(({ ensureDictionary }) =>
    ensureDictionary(code).then(() => {
      window.dispatchEvent(new Event("kamra:lang"))
    }),
  )
}

/** Call once at boot. Prefetch the active dictionary so t() is ready
 *  before React mounts (avoids a flash of English on Arabic desks). */
export async function initLang() {
  const code = getLang()
  applyLang(code)
  const { ensureDictionary } = await import("./locales")
  await ensureDictionary(code)
}
