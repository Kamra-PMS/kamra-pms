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
  // let listeners (React trees) re-render with the new direction/strings
  window.dispatchEvent(new Event("kamra:lang"))
}

/** Guest pages: the guest's own pick wins; until then the hotel's booking
 * engine language (`preferred`), else the browser language. */
export function adoptGuestLanguage(preferred?: string | null) {
  const browser = navigator.language?.toLowerCase().split("-")[0]
  const next = [preferred, browser].find((c) => c && codes.has(c)) ?? null
  if (next === guestDefault) return
  guestDefault = next
  syncLang()
}

/** Re-apply after moving between a guest page and the desk in one tab. */
export function syncLang() {
  applyLang(getLang())
  window.dispatchEvent(new Event("kamra:lang"))
}

/** Call once at boot. */
export function initLang() {
  applyLang(getLang())
}
