/** Locale dictionaries are loaded on demand so English (and a single
 *  active language) do not pay for ar + es + pt in the entry bundle.
 *  ~1.4 MB of JSON otherwise ships on every first paint. */

type Dict = Record<string, string>

const cache: Record<string, Dict> = { en: {} }

const loaders: Record<string, () => Promise<{ default: Dict }>> = {
	ar: () => import("../i18n/locales/ar.json"),
	es: () => import("../i18n/locales/es.json"),
	pt: () => import("../i18n/locales/pt.json"),
	"zh-CN": () => import("../i18n/locales/zh-CN.json"),
}

const inflight = new Map<string, Promise<Dict>>()

/** Ensure `language` is in memory. Safe to call repeatedly; en is a no-op. */
export async function ensureDictionary(language: string): Promise<Dict> {
	if (!language || language === "en") return cache.en
	if (cache[language]) return cache[language]
	const pending = inflight.get(language)
	if (pending) return pending
	const loader = loaders[language]
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
