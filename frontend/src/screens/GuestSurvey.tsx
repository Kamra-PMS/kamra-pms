import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { callGuest } from "../lib/api"
import { adoptGuestLanguage } from "../lib/dir"
import { useT } from "../lib/i18n"

/** Guest satisfaction survey. The token is the only credential. */
export default function GuestSurvey() {
  const { token = "" } = useParams()
  const { t } = useT()
  const [propertyName, setPropertyName] = useState("")
  const [done, setDone] = useState(false)
  const [score, setScore] = useState(0)
  const [comment, setComment] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    adoptGuestLanguage()
    callGuest<{ property_name: string; submitted: boolean }>("kamra.enterprise.survey_prompt", { token })
      .then((data) => {
        setPropertyName(data.property_name)
        setDone(data.submitted)
      })
      .catch((err: Error) => setError(err.message || t("This survey link is not valid.")))
  }, [token, t])

  async function submit() {
    setBusy(true)
    setError("")
    try {
      await callGuest("kamra.enterprise.submit_survey", { token, score, comment })
      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Could not save your score."))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="mx-auto max-w-md px-4 py-16">
      <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">{t("Guest survey")}</p>
      <h1 className="mt-2 text-2xl font-semibold text-zinc-900">{propertyName || t("How was your stay?")}</h1>
      {done ? (
        <p className="mt-6 text-sm text-zinc-600">{t("Thank you. Your score is with the hotel.")}</p>
      ) : (
        <>
          <p className="mt-3 text-sm text-zinc-600">{t("How was your stay? 1 is poor, 5 is excellent.")}</p>
          <div className="mt-6 flex gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setScore(n)}
                className={
                  "size-12 rounded-lg border text-sm font-semibold " +
                  (score === n ? "border-brand-700 bg-brand-700 text-white" : "border-zinc-300 bg-white")
                }
              >
                {n}
              </button>
            ))}
          </div>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={t("Anything we should know?")}
            className="mt-4 min-h-28 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
          />
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          <button
            type="button"
            disabled={!score || busy}
            onClick={submit}
            className="mt-4 rounded-lg bg-brand-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {t("Send score")}
          </button>
        </>
      )}
    </main>
  )
}
