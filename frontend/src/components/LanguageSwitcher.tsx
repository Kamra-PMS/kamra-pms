import { LANGS, setLang } from "../lib/dir"
import { useT } from "../lib/i18n"

/** Compact language toggle for public pages and shells. */
export function LanguageSwitcher(props?: { className?: string }) {
  const { t, lang } = useT()
  return (
    <div
      className={
        "flex shrink-0 rounded-lg border border-zinc-200 bg-white p-0.5 text-xs " +
        (props?.className ?? "")
      }
      role="group"
      aria-label={t("Language")}
    >
      {LANGS.map((l) => (
        <button
          key={l.code}
          type="button"
          aria-pressed={lang === l.code}
          onClick={() => setLang(l.code)}
          className={
            "rounded-md px-2 py-1 " +
            (lang === l.code ? "bg-zinc-900 text-white" : "text-zinc-600")
          }
        >
          {l.nativeLabel}
        </button>
      ))}
    </div>
  )
}
