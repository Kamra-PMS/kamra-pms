/** Locale dictionaries are loaded on demand so English (and a single
 *  active language) do not pay for every other language in the entry bundle.
 *  A new locales/<code>.json is picked up here without another import;
 *  register its name and direction in i18n/languages.json so the pickers
 *  and the Settings toggles offer it. */

type Dict = Record<string, string>

const cache: Record<string, Dict> = { en: {} }

const loaders = import.meta.glob<{ default: Dict }>("../i18n/locales/*.json")

const inflight = new Map<string, Promise<Dict>>()

function loaderFor(language: string) {
	const suffix = `/${language}.json`
	for (const [path, load] of Object.entries(loaders)) {
		if (path.endsWith(suffix)) return load
	}
	return undefined
}

/** Ensure `language` is in memory. Safe to call repeatedly; en is a no-op. */
export async function ensureDictionary(language: string): Promise<Dict> {
	if (!language || language === "en") return cache.en
	if (cache[language]) return cache[language]
	const pending = inflight.get(language)
	if (pending) return pending
	const loader = loaderFor(language)
	if (!loader) return cache.en
	const task = loader()
		.then((mod) => {
			const dict = (mod as { default?: Dict }).default ?? (mod as unknown as Dict)
			cache[language] = dict
			inflight.delete(language)
			return dict
		})
		.catch((err) => {
			inflight.delete(language)
			throw err
		})
	inflight.set(language, task)
	return task
}

/** Sync lookup used by t()/tn(). Returns {} until ensureDictionary finishes. */
export const dictionaryFor = (language: string): Dict =>
	cache[language] ?? cache.en
