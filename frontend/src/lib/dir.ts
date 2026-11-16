/** Interface direction / language. Stored per device (like the theme) and
 * applied to the document so the whole UI flips together. Direction comes
 * from the language registry (not a hard-coded `=== "ar"`), so another
 * right-to-left language can join later without touching every call site.
 * Which codes a picker offers is the site setting in Settings, Languages. */

import registry from "../i18n/languages.json"
import { effectiveLanguage, listedLanguages } from "./enabledLanguages"

export interface LangDef {
  code: string
  /** Native name shown in the language picker, e.g. "العربية". */
  nativeLabel: string
  /** English label for the picker, e.g. "Arabic". */
  englishLabel: string
  dir: "ltr" | "rtl"
}

/** Supported UI languages. Add a row to i18n/languages.json and a
 * locales/<code>.json to ship another. The Settings toggles read this list. */
export const LANGS: LangDef[] = registry.map((row) => ({
  code: row.code,
  nativeLabel: row.nativeLabel,
  englishLabel: row.englishLabel,
  dir: row.dir === "rtl" ? "rtl" : "ltr",
}))

export type Lang = string

// Guest pages keep their own choice: a guest (or staff previewing /book)
// picking Spanish there must not switch the desk, and the reverse.
const GUEST_PAGE = /^(\/kamra)?\/(book|stay|checkin)(\/|$)/
const key = () => (GUEST_PAGE.test(window.location.pathname) ? "kamra-guest-lang" : "kamra-lang")
const known = LANGS.map((l) => l.code)

// null until the site answers: every known language stays offered, so a
// failed request does not hide languages the hotel has not switched off.
let enabledCodes: Set<string> | null = null
let offeredSnapshot: LangDef[] = LANGS

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
  const fallbacks = key() === "kamra-guest-lang" ? [guestDefault] : []
  return effectiveLanguage(raw || null, enabledCodes, known, fallbacks)
}

/** Languages the pickers may list. The array identity is stable until the
 * enabled set changes, so a subscriber can use it as a snapshot. */
export function offeredLangs(): LangDef[] {
  const next = listedLanguages(LANGS, enabledCodes)
  if (
    next.length === offeredSnapshot.length &&
    next.every((lang, i) => lang.code === offeredSnapshot[i].code)
  ) {
    return offeredSnapshot
  }
  offeredSnapshot = next
  return offeredSnapshot
}

function storeEnabled(codes: readonly string[]) {
  const next = new Set<string>()
  for (const code of codes) if (known.includes(code)) next.add(code)
  next.add("en")
  const same =
    enabledCodes !== null &&
    next.size === enabledCodes.size &&
    [...next].every((code) => enabledCodes?.has(code))
  enabledCodes = next
  return !same
}

/** Replace the site's enabled set and re-apply the language that is still on.
 * A saved choice that was switched off is kept in storage and comes back if
 * an admin switches that language on again. */
export function applyEnabledLanguages(codes: readonly string[]) {
  if (!storeEnabled(codes)) return
  const code = getLang()
  applyLang(code)
  void import("./locales").then(({ ensureDictionary }) =>
    ensureDictionary(code).then(() => {
      window.dispatchEvent(new Event("kamra:lang"))
    }),
  )
}

async function fetchEnabled(): Promise<string[] | null> {
  try {
    const res = await fetch("/api/method/kamra.languages.enabled_ui_languages", {
      credentials: "omit",
    })
    if (!res.ok) return null
    const body = (await res.json()) as { message?: { enabled?: unknown } }
    const enabled = body.message?.enabled
    if (!Array.isArray(enabled)) return null
    return enabled.filter((code): code is string => typeof code === "string")
  } catch {
    return null
  }
}

export function applyLang(l: Lang) {
  const def = langDef(l)
  const el = document.documentElement
  el.setAttribute("lang", def.code)
  el.setAttribute("dir", def.dir)
}

export function setLang(l: Lang) {
  const code = effectiveLanguage(l, enabledCodes, known)
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
 * engine language (`preferred`), else the browser language. A switched-off
 * code is skipped. */
export function adoptGuestLanguage(preferred?: string | null) {
  const browser = navigator.language?.toLowerCase().split("-")[0]
  const next =
    [preferred, browser].find(
      (code) => code && effectiveLanguage(code, enabledCodes, known) === code,
    ) ?? null
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
 *  before React mounts (avoids a flash of English on Arabic desks).
 *  The enabled-language request is best-effort: a dead API must not
 *  hold the sign-in screen, and a late answer still updates the pickers. */
export async function initLang() {
  const fetched = fetchEnabled()
  const first = await Promise.race([
    fetched,
    new Promise<null>((resolve) => setTimeout(() => resolve(null), 3000)),
  ])
  if (first) storeEnabled(first)
  const code = getLang()
  applyLang(code)
  const { ensureDictionary } = await import("./locales")
  await ensureDictionary(code)
  if (!first) {
    void fetched.then((codes) => {
      if (codes) applyEnabledLanguages(codes)
    })
  }
}
