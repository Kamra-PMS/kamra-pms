import { useCallback, useSyncExternalStore } from "react"
import { getLang } from "./dir"
import { dictionaryFor } from "./locales"

export type Vars = Record<string, string | number>

/** Replace `{name}` placeholders in a template. Arabic (and others) can
 * reorder words by placing the same placeholders differently. */
function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (_, k: string) =>
    vars[k] !== undefined && vars[k] !== null ? String(vars[k]) : `{${k}}`,
  )
}

// Some settings labels and server messages arrive with values already inserted.
const patternsFor = (dictionary: Record<string, string>) => Object.entries(dictionary)
  .filter(([source, translated]) =>
    source !== translated && /\{\w+\}/.test(source) &&
    source.replace(/\{\w+\}/g, "").replace(/[^A-Za-z]/g, "").length >= 4,
  )
  .sort(([a], [b]) => b.replace(/\{\w+\}/g, "").length - a.replace(/\{\w+\}/g, "").length)
  .map(([source, translated]) => {
    const names: string[] = []
    const escaped = source.split(/(\{\w+\})/).map((part) => {
      if (/^\{\w+\}$/.test(part)) {
        names.push(part.slice(1, -1))
        return "([\\s\\S]*?)"
      }
      return part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    }).join("")
    // Bare room/table labels must contain an identifier with a number.
    // Otherwise a missing phrase such as "Room types and rates" could be
    // mistaken for "Room {n}" and become a partly translated sentence.
    const numberedLabel = /^(?:Room|Table) \{\w+\}$/.test(source)
    return { expression: new RegExp(`^${escaped}$`), names, translated, numberedLabel }
  })

const patternsByLanguage = new Map<string, ReturnType<typeof patternsFor>>()

function translatedTemplate(source: string, language: string): string {
  const dictionary = dictionaryFor(language)
  if (Object.prototype.hasOwnProperty.call(dictionary, source)) return dictionary[source]
  if (!patternsByLanguage.has(language)) patternsByLanguage.set(language, patternsFor(dictionary))
  for (const { expression, names, translated, numberedLabel } of patternsByLanguage.get(language)!) {
    const match = expression.exec(source)
    if (match && (!numberedLabel || /\p{N}/u.test(match[1]))) {
      const values = Object.fromEntries(names.map((name, i) => [name, match[i + 1]]))
      return translated.replace(/\{(\w+)\}/g, (token, name: string) => values[name] ?? token)
    }
  }
  return source
}

/** Translate UI text; non-string React content and missing labels pass through. */
export function t(s: string, vars?: Vars): string
export function t<T>(s: T): T
export function t(s: unknown, vars?: Vars): unknown {
  if (typeof s !== "string") return s
  return interpolate(translatedTemplate(s, getLang()), vars)
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

const subscribe = (onChange: () => void) => {
  window.addEventListener("kamra:lang", onChange)
  return () => window.removeEventListener("kamra:lang", onChange)
}

/** Subscribe presentation components to the same language as t()/tn(). */
export function useUILanguage() {
  return useSyncExternalStore(subscribe, getLang, () => "en")
}

/** Translate month/weekday names while retaining the existing EN/AR date formats. */
export function uiDateLocale(locales?: string | string[]) {
  const language = getLang()
  return language === "en" || language === "ar" ? locales : language
}

/** Subscribe to the language and return its translators. */
export function useT() {
  const lang = useUILanguage()
  const t = useCallback(
    (s: string, vars?: Vars) => {
      return interpolate(translatedTemplate(s, lang), vars)
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
