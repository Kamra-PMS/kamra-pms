import ar from "../i18n/locales/ar.json"
import es from "../i18n/locales/es.json"

/** Add each new locale here and to the language picker registry in dir.ts. */
const dictionaries: Record<string, Record<string, string>> = { en: {}, ar, es }

export const dictionaryFor = (language: string): Record<string, string> =>
  dictionaries[language] ?? {}
