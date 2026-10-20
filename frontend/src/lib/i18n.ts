import { useCallback, useEffect, useState } from "react"
import { getLang, type Lang } from "./dir"
import ar from "../i18n/locales/ar.json"

/** Locale dictionaries keyed by English source string. Missing keys fall back
 * to English so the app never blanks as coverage expands. */
const DICT: Record<string, Record<string, string>> = {
  en: {},
  ar: ar as Record<string, string>,
}

export type Vars = Record<string, string | number>

/** Replace `{name}` placeholders in a template. Arabic (and others) can
 * reorder words by placing the same placeholders differently. */
function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (_, k: string) =>
    vars[k] !== undefined && vars[k] !== null ? String(vars[k]) : `{${k}}`,
  )
}

/** Translate an English string for the current language (falls back to it). */
export function t(s: string, vars?: Vars): string {
  const dict = DICT[getLang()] ?? {}
  return interpolate(dict[s] ?? s, vars)
}

/** English plural form for a count: "one" or "other". Arabic and other
 * languages translate each English form; the count goes in as {n}. */
function pluralForm(n: number, one: string, other: string): string {
  return new Intl.PluralRules("en").select(n) === "one" ? one : other
}

/** Translate a counted phrase: the English singular form for 1, the
 * plural otherwise ("1 child", "2 children"); {n} is the count. */
export function tn(n: number, one: string, other: string, vars?: Vars): string {
  return t(pluralForm(n, one, other), { n, ...vars })
}

/** Subscribe a component to the language: re-renders on change, returns a
 * bound translator. */
export function useT() {
  const [lang, setL] = useState<Lang>(getLang())
  useEffect(() => {
    const on = () => setL(getLang())
    window.addEventListener("kamra:lang", on)
    return () => window.removeEventListener("kamra:lang", on)
  }, [])
  const t = useCallback(
    (s: string, vars?: Vars) => {
      const dict = DICT[lang] ?? {}
      return interpolate(dict[s] ?? s, vars)
    },
    [lang],
  )
  const tnBound = useCallback(
    (n: number, one: string, other: string, vars?: Vars) =>
      t(pluralForm(n, one, other), { n, ...vars }),
    [t],
  )
  return { lang, t, tn: tnBound }
}
