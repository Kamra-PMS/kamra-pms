/** Which registered UI languages a picker may offer, and which code to
 * use when a saved choice was switched off. `enabled === null` means the
 * site list has not loaded yet: every known language is still offered, so
 * a slow request does not flash the list down to English. */

export function effectiveLanguage(
  saved: string | null | undefined,
  enabled: ReadonlySet<string> | null,
  known: readonly string[],
  fallbacks: readonly (string | null | undefined)[] = [],
): string {
  const knownSet = new Set(known)
  const allow = (code: string) =>
    code === "en" || (knownSet.has(code) && (enabled === null || enabled.has(code)))
  for (const code of [saved, ...fallbacks, "en"]) {
    if (code && allow(code)) return code
  }
  return "en"
}

export function listedLanguages<T extends { code: string }>(
  langs: readonly T[],
  enabled: ReadonlySet<string> | null,
): T[] {
  if (enabled === null) return [...langs]
  return langs.filter((lang) => lang.code === "en" || enabled.has(lang.code))
}
