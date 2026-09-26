/** The notice a guest sees where their data is collected (DPDP Act s.5 and
 *  Rule 3): what, why, for how long, their rights, whom to ask, and where
 *  to complain. One short line; the detail opens on tap so it never costs
 *  the booking. Wording follows the property's real settings, so it never
 *  promises what the hotel does not do. */
export default function PrivacyNotice({
  propertyName, contact, retentionMonths, idRetention, collectsId = false,
}: {
  propertyName: string
  contact?: string | null
  retentionMonths?: number | null
  idRetention?: string | null
  collectsId?: boolean
}) {
  const months = Number(retentionMonths || 0)
  return (
    <details className="text-xs text-zinc-500">
      <summary className="cursor-pointer select-none">
        {propertyName} uses your details for this stay. <span className="underline">Privacy notice</span>
      </summary>
      <div className="mt-2 space-y-1.5 leading-relaxed">
        <p>
          <b>What and why:</b> your name and contact details to make and manage this booking
          and reach you about it{collectsId ? "; your ID and address because hotels must register guests under the law (for foreign nationals, Form C to the immigration authorities)" : ""}.
          Payments are handled by the hotel's payment gateway; the hotel does not see your card.
        </p>
        <p>
          <b>How long:</b>{" "}
          {collectsId && (idRetention === "Verify & Discard"
            ? "ID photos are deleted and ID numbers cut to the last 4 digits at checkout. "
            : "the hotel keeps a copy of your ID with its registration records. ")}
          {months > 0
            ? `Your profile is erased ${months} months after your last stay. Bills are kept as tax law requires.`
            : "Your profile is kept for future stays until you ask for it to be erased. Bills are kept as tax law requires."}
        </p>
        <p>
          <b>Your rights:</b> ask to see, correct or erase your data, or withdraw consent,
          {contact ? <> by contacting <b>{contact}</b></> : " by contacting the hotel"}.
          If you are not satisfied, you can complain to the Data Protection Board of India.
        </p>
      </div>
    </details>
  )
}
