import { useState } from "react"
import { useT, type Vars, t as translate } from "../lib/i18n"
import { LANGS } from "../lib/dir"
import bn from "../i18n/notice/bn.json"
import hi from "../i18n/notice/hi.json"
import kn from "../i18n/notice/kn.json"
import ml from "../i18n/notice/ml.json"
import mr from "../i18n/notice/mr.json"
import ta from "../i18n/notice/ta.json"
import te from "../i18n/notice/te.json"


/** Who a guest complains to and the statutory guest report the hotel files
 *  come from the property's country pack (public pages pass them in with
 *  their ui_locale) - India's DPDP wording must not reach a Saudi guest. */
interface Terms {
  privacy_authority?: string | null
  guest_report?: string | null
  adult_age?: number | null
  notice_languages?: string[] | null
}

let terms: Terms = {}

export function setPrivacyTerms(ui?: Terms | null) {
  if (ui) terms = {
    privacy_authority: ui.privacy_authority,
    guest_report: ui.guest_report,
    adult_age: ui.adult_age,
    notice_languages: ui.notice_languages,
  }
}

/** Notice-only translations: a guest may read the notice in a language the
 *  rest of the page does not offer yet. */
const NOTICE: Record<string, { label: string; dict: Record<string, string> }> = {
  hi: { label: "हिन्दी", dict: hi },
  kn: { label: "ಕನ್ನಡ", dict: kn },
  ta: { label: "தமிழ்", dict: ta },
  te: { label: "తెలుగు", dict: te },
  ml: { label: "മലയാളം", dict: ml },
  mr: { label: "मराठी", dict: mr },
  bn: { label: "বাংলা", dict: bn },
}

function browserNoticeLang(offered: string[]): string {
  for (const l of navigator.languages ?? [navigator.language]) {
    const base = (l || "").toLowerCase().split("-")[0]
    if (offered.includes(base)) return base
  }
  return ""
}

/** The notice a guest sees where their data is collected: what, why, for
 *  how long, their rights, whom to ask, and where to complain. One short
 *  line; the detail opens on tap so it never costs the booking. Wording
 *  follows the property's real settings and country, so it never promises
 *  what the hotel does not do. */
export default function PrivacyNotice({
  propertyName, contact, retentionMonths, idRetention, collectsId = false,
}: {
  propertyName: string
  contact?: string | null
  retentionMonths?: number | null
  idRetention?: string | null
  collectsId?: boolean
}) {
  const { t: pageT, lang: pageLang } = useT()
  const offered = (terms.notice_languages ?? []).filter((c) => NOTICE[c])
  // "" reads the notice in the page's own language
  const [lang, setLang] = useState(() => browserNoticeLang(offered))
  const dict = NOTICE[lang]?.dict
  const t = (s: string, vars?: Vars) => {
    const own = dict?.[s]
    return own === undefined ? pageT(s, vars)
      : own.replace(/\{(\w+)\}/g, (_, k: string) => String(vars?.[k] ?? `{${k}}`))
  }
  const months = Number(retentionMonths || 0)
  const authority = terms.privacy_authority || "your local data protection authority"
  return (
    <details className="text-xs text-zinc-500" lang={lang || undefined}>
      <summary className="cursor-pointer select-none">
        {t("{property} uses your details for this stay.", { property: propertyName })}{" "}
        <span className="underline">{t("Privacy notice")}</span>
      </summary>
      <div className="mt-2 space-y-1.5 leading-relaxed">
        {offered.length > 0 && (
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>{t("Read this notice in:")}</span>
            {[["", LANGS.find((l) => l.code === pageLang)?.nativeLabel ?? "English"] as const, ...offered.map((c) => [c, NOTICE[c].label] as const)].map(
              ([code, label]) => (
                <button
                  key={code || "page"}
                  type="button"
                  lang={code || undefined}
                  aria-pressed={lang === code}
                  onClick={() => setLang(code)}
                  className={lang === code ? "font-semibold text-zinc-700" : "underline"}
                >
                  {translate(label)}
                </button>
              ),
            )}
          </p>
        )}
        <p>
          <b>{t("What and why:")}</b>{" "}
          {t("your name and contact details to make and manage this booking and reach you about it")}
          {collectsId &&
            (terms.guest_report
              ? t("; your ID and address because hotels must register guests under the law ({report})", {
                  report: t(terms.guest_report),
                })
              : t("; your ID and address because hotels must register guests under the law"))}
          {". "}
          {t("Payments are handled by the hotel's payment gateway; the hotel does not see your card.")}
        </p>
        <p>
          <b>{t("How long:")}</b>{" "}
          {collectsId &&
            (idRetention === "Verify & Discard"
              ? t("ID photos are deleted and ID numbers cut to the last 4 digits at checkout.")
              : t("The hotel keeps a copy of your ID with its registration records.")) + " "}
          {months > 0
            ? t("Your profile is erased {months} months after your last stay. Bills are kept as tax law requires.", { months })
            : t("Your profile is kept for future stays until you ask for it to be erased. Bills are kept as tax law requires.")}
        </p>
        {collectsId && (
          <p>
            <b>{t("Children:")}</b>{" "}
            {t("for guests under {age} the hotel records only what registration law requires, usually name and age, and never uses it for marketing.", {
              age: terms.adult_age || 18,
            })}
          </p>
        )}
        <p>
          <b>{t("Your rights:")}</b>{" "}
          {contact
            ? t("ask to see, correct or erase your data, or withdraw consent, by contacting {contact}.", { contact })
            : t("ask to see, correct or erase your data, or withdraw consent, by contacting the hotel.")}{" "}
          {t("If you are not satisfied, you can complain to {authority}.", { authority: t(authority) })}
        </p>
      </div>
    </details>
  )
}
