/** Finish setting up: what is done and what is left for this property,
 *  with a link to do each and one to its guide. Reached from Quick setup
 *  and from the banner until everything is done. */
import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Check, Circle } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { InfoTip } from "../components/InfoTip"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"

export interface ChecklistItem {
  key: string
  label: string
  done: boolean
  detail: string
  to: string
  doc: string | null
}

export interface Checklist {
  items: ChecklistItem[]
  done: number
  total: number
  percent: number
}

export default function FinishSetup() {
  const { t } = useT()
  const [data, setData] = useState<Checklist | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    call<Checklist>("kamra.onboarding.setup_checklist", { property: getCurrentProperty() })
      .then(setData)
      .catch((e) => setErr(serverError(e)))
  }, [])

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-lg font-semibold">{t("Finish setting up")}</h1>
        <p className="text-sm text-zinc-500">
          {t("Your property is created. These are the things still to do, in any order. Each one links to where you do it.")}
        </p>
      </div>
      {err && <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}
      {data && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>{t("{done} of {total} done", { done: data.done, total: data.total })}</span>
              <span className="text-sm font-normal text-zinc-400">{data.percent}%</span>
            </CardTitle>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-100" aria-hidden>
              <div className="h-full bg-brand-600" style={{ width: `${data.percent}%` }} />
            </div>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-zinc-100">
              {data.items.map((i) => (
                <li key={i.key} className="flex items-start gap-3 py-3">
                  <span
                    className={cn(
                      "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full",
                      i.done ? "bg-brand-600 text-white" : "border border-zinc-300 text-zinc-300",
                    )}
                  >
                    {i.done ? <Check className="size-3" aria-hidden /> : <Circle className="size-2" aria-hidden />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className={cn("flex items-center gap-1.5 text-sm font-medium", i.done && "text-zinc-400 line-through")}>
                      {t(i.label)}
                      {i.doc && <InfoTip doc={i.doc}>{t(i.detail)}</InfoTip>}
                    </p>
                    <p className="text-xs text-zinc-500">{t(i.detail)}</p>
                  </div>
                  {!i.done && (
                    <Link to={i.to} className="shrink-0 text-sm font-medium text-brand-700 hover:underline">
                      {t("Do it")} →
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
