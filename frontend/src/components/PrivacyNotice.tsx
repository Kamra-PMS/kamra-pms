import { useT } from "../lib/i18n"

/** Who a guest complains to and the statutory guest report the hotel files
 *  come from the property's country pack (public pages pass them in with
 *  their ui_locale) - India's DPDP wording must not reach a Saudi guest. */
let terms: { privacy_authority?: string | null; guest_report?: string | null } = {}

export function setPrivacyTerms(ui?: {
  privacy_authority?: string | null
  guest_report?: string | null
} | null) {
  if (ui) terms = { privacy_authority: ui.privacy_authority, guest_report: ui.guest_report }
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
  const { t } = useT()
  const months = Number(retentionMonths || 0)
  const authority = terms.privacy_authority || t("your local data protection authority")
  return (
    <details className="text-xs text-zinc-500">
      <summary className="cursor-pointer select-none">
        {t("{property} uses your details for this stay.", { property: propertyName })}{" "}
        <span className="underline">{t("Privacy notice")}</span>
      </summary>
      <div className="mt-2 space-y-1.5 leading-relaxed">
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
