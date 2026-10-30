import { useEffect, useState } from "react"
import { ArrowLeft, Printer } from "lucide-react"
import { Link, useParams } from "react-router-dom"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { moneyLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import type { Itinerary } from "./CRS"

/** Printable confirmation for a whole trip: one reference, every stay in
 * date order with its own hotel, booking number and price. */

const amt = (sym: string, n: number) =>
  `${sym}${Number(n).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })}`

export default function TripConfirmation() {
  const { t } = useT()
  const { name } = useParams()
  const [d, setD] = useState<Itinerary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (name)
      call<Itinerary>("kamra.crs.get_itinerary", { itinerary: name })
        .then(setD).catch((e) => setError(serverError(e)))
  }, [name])

  if (error) return <p className="py-10 text-center text-rose-600">{t(error)}</p>
  if (!d) return <p className="py-10 text-center text-zinc-400">{t("Loading…")}</p>
  const sym = d.legs[0]?.currency_symbol ?? ""

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-center justify-between print:hidden">
        <Link to="/crs" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800">
          <ArrowLeft className="size-4" aria-hidden />{t("Central reservations")}
        </Link>
        <Button onClick={() => window.print()}>
          <Printer className="size-4" aria-hidden />{t("Print")}
        </Button>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-8 print:border-0">
        <div className="mb-6 flex items-start justify-between border-b border-zinc-300 pb-4">
          <div>
            <p className="text-sm font-semibold">{t("TRIP CONFIRMATION")}</p>
            <p className="text-xs text-zinc-500">{d.guest_name}{d.phone && <> · {d.phone}</>}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-zinc-500">{t("Your reference")}</p>
            <p className="text-lg font-bold text-brand-700">{d.name}</p>
          </div>
        </div>

        <ol className="space-y-3">
          {d.legs.map((l, i) => (
            <li key={l.reservation} className="flex gap-3 text-sm">
              <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border border-zinc-300 text-xs font-semibold">{i + 1}</span>
              <div className="flex-1">
                <div className="flex justify-between gap-2">
                  <span className="font-semibold">{l.property_name}{l.city ? `, ${l.city}` : ""}</span>
                  <span className={l.status === "Cancelled" ? "text-zinc-400 line-through" : ""}>
                    {amt(l.currency_symbol, l.amount_after_tax)}
                  </span>
                </div>
                <p className="text-zinc-600">
                  {l.check_in_date} → {l.check_out_date} · {l.room_type_name} · {t("Booking {ref}", { ref: l.reservation })}
                </p>
                {l.status === "Cancelled" && (
                  <p className="text-xs text-rose-700">{t("Cancelled {ref}", { ref: l.cancellation_number ?? "" })}</p>
                )}
              </div>
            </li>
          ))}
        </ol>

        <div className="mt-6 space-y-1.5 rounded-lg bg-zinc-50 px-4 py-3 text-sm">
          {d.total != null ? (
            <>
              <div className="flex justify-between font-medium">
                <span>{t("Trip total, taxes in")}</span><span>{amt(sym, d.total)}</span>
              </div>
              {(d.advance_required ?? 0) > 0 && (
                <div className="flex justify-between text-zinc-500">
                  <span>{t("Advance required")}</span><span>{amt(sym, d.advance_required ?? 0)}</span>
                </div>
              )}
              <div className="flex justify-between text-zinc-500">
                <span>{t("Advance paid")}</span><span>{amt(sym, d.advance_paid ?? 0)}</span>
              </div>
              {(d.advance_due ?? 0) > 0 && (
                <div className="flex justify-between font-medium">
                  <span>{t("Advance still due")}</span><span>{amt(sym, d.advance_due ?? 0)}</span>
                </div>
              )}
            </>
          ) : (
            <p className="text-zinc-500">{t("Each stay is billed in its own currency")}</p>
          )}
        </div>
        <p className="mt-4 text-xs text-zinc-500">
          {t("Each hotel bills its own stay and issues its own invoice. Its own cancellation terms apply.")}
        </p>
      </div>
    </div>
  )
}
