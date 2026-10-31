import { Globe } from "lucide-react"
import { LANGS, setLang } from "../lib/dir"
import { useT } from "../lib/i18n"

/** Language dropdown for the public guest pages. */
export function LanguageSwitcher(props?: { className?: string }) {
  const { t, lang } = useT()
  return (
    <label
      className={
        "flex shrink-0 items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 " +
        (props?.className ?? "")
      }
    >
      <Globe className="size-3.5 text-zinc-500" aria-hidden />
      <select
        aria-label={t("Language")}
        value={lang}
        onChange={(e) => setLang(e.target.value)}
        className="bg-transparent pe-1 outline-none"
      >
        {LANGS.map((l) => (
          <option key={l.code} value={l.code}>
            {l.nativeLabel}
          </option>
        ))}
      </select>
    </label>
  )
}
