import { useEffect, useState } from "react"
import { ArrowLeft, Printer } from "lucide-react"
import { Link, useParams } from "react-router-dom"
import { call } from "../lib/api"
import { Button } from "../components/ui/button"
import { cur, moneyLocale } from "../lib/money"
import { serverError } from "../lib/resource"
import { t as translate, useUILanguage } from "../lib/i18n"

/** Printable group quotation / proforma - what the group's rooms cost per
 *  type and night, the deposit asked, and the terms - to send the client
 *  before they confirm. Nothing is posted. */

interface PriceRow {
  room_type: string
  room_type_name: string
  rooms: number
  nightly: Record<string, number>
  room_nights: number
  group_rate: boolean
  rate: number
  before_tax: number
  tax: number
  levy: number
  total: number
}
interface Quote {
  property: {
    property_name: string
    logo_url: string | null
    address: string
    phone: string | null
    email: string | null
    website: string | null
    tax_id: string | null
    tax_id_label: string
    tax_label: string
  }
  group: {
    name: string
    group_name: string
    group_type: string | null
    status: string
    company: string | null
    contact: string | null
    master_pays: string | null
    check_in_date: string
    check_out_date: string
    cutoff_date: string
    attrition_pct: number
    deposit_due: number
  }
  prices: { rows: PriceRow[]; nights: number; before_tax: number; tax: number; levy: number; total: number }
  issued_on: string
}

const money = (n: number) =>
  `${cur()}${Number(n).toLocaleString(moneyLocale(), { maximumFractionDigits: 2 })}`

export default function GroupQuotation() {
  useUILanguage()
  const { name } = useParams()
  const [d, setD] = useState<Quote | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (name)
      call<Quote>("kamra.api.group_quotation", { group_booking: name })
        .then(setD)
        .catch((e) => setError(serverError(e)))
  }, [name])

  if (error) return <p className="py-10 text-center text-rose-600">{error}</p>
  if (!d) return <p className="py-10 text-center text-zinc-400">{translate("Loading…")}</p>

  const { property: p, group: g, prices } = d
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between print:hidden">
        <Link
          to={`/groups?open=${encodeURIComponent(g.name)}`}
          className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-800"
        >
          <ArrowLeft className="size-4" aria-hidden />{translate("Back to the group")}
        </Link>
        <Button onClick={() => window.print()}>
          <Printer className="size-4" aria-hidden />{translate("Print / Save as PDF")}
        </Button>
      </div>

      <div className="space-y-6 rounded-xl border border-zinc-200 bg-white p-8 text-sm print:border-0 print:p-0">
        <header className="flex items-start justify-between gap-6">
          <div>
            {p.logo_url && <img src={p.logo_url} alt="" className="mb-2 h-12 object-contain" />}
            <div className="text-lg font-semibold text-zinc-900">{p.property_name}</div>
            <div className="text-zinc-500">{p.address}</div>
            <div className="text-zinc-500">{[p.phone, p.email, p.website].filter(Boolean).join(" · ")}</div>
            {p.tax_id && <div className="text-zinc-500">{translate(p.tax_id_label)}: {p.tax_id}</div>}
          </div>
          <div className="text-right">
            <div className="text-xl font-semibold tracking-tight text-zinc-900">
              {g.status === "Open" ? translate("Group quotation") : translate("Group proforma")}
            </div>
            <div className="text-zinc-500">{g.name}</div>
            <div className="text-zinc-500">{translate("Issued {v0}", { v0: d.issued_on })}</div>
          </div>
        </header>

        <section className="grid gap-1 rounded-lg bg-zinc-50 p-4 sm:grid-cols-2">
          <div><span className="text-zinc-500">{translate("Group")}: </span>{g.group_name}{g.group_type ? ` (${translate(g.group_type)})` : ""}</div>
          {g.company && <div><span className="text-zinc-500">{translate("Company")}: </span>{g.company}</div>}
          {g.contact && <div><span className="text-zinc-500">{translate("Contact")}: </span>{g.contact}</div>}
          <div>
            <span className="text-zinc-500">{translate("Stay")}: </span>
            {g.check_in_date} → {g.check_out_date} · {translate("{v0} night(s)", { v0: String(prices.nights) })}
          </div>
        </section>

        <table className="w-full">
          <thead>
            <tr className="border-b border-zinc-200 text-left text-xs text-zinc-500">
              <th className="py-2 pr-2 font-medium">{translate("Room type")}</th>
              <th className="py-2 pr-2 text-right font-medium">{translate("Rooms")}</th>
              <th className="py-2 pr-2 text-right font-medium">{translate("Room-nights")}</th>
              <th className="py-2 pr-2 text-right font-medium">{translate("Rate / night")}</th>
              <th className="py-2 pr-2 text-right font-medium">{translate(p.tax_label)}</th>
              <th className="py-2 text-right font-medium">{translate("Amount")}</th>
            </tr>
          </thead>
          <tbody>
            {prices.rows.map((r) => (
              <tr key={r.room_type} className="border-b border-zinc-100 align-top">
                <td className="py-2 pr-2">
                  {r.room_type_name}
                  {r.group_rate && <span className="ml-1 text-xs text-brand-700">{translate("group rate")}</span>}
                  {Object.keys(r.nightly).length > 0 && (
                    <div className="text-xs text-zinc-500">
                      {Object.entries(r.nightly).map(([date, n]) => `${date.slice(5)}: ${n}`).join(" · ")}
                    </div>
                  )}
                </td>
                <td className="py-2 pr-2 text-right">{r.rooms}</td>
                <td className="py-2 pr-2 text-right">{r.room_nights}</td>
                <td className="py-2 pr-2 text-right">{money(r.rate)}</td>
                <td className="py-2 pr-2 text-right">{money(r.tax)}</td>
                <td className="py-2 text-right font-medium">{money(r.total)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr><td colSpan={5} className="pt-3 text-right text-zinc-500">{translate("Rooms before tax")}</td><td className="pt-3 text-right">{money(prices.before_tax)}</td></tr>
            <tr><td colSpan={5} className="text-right text-zinc-500">{translate(p.tax_label)}</td><td className="text-right">{money(prices.tax)}</td></tr>
            {prices.levy > 0 && (
              <tr><td colSpan={5} className="text-right text-zinc-500">{translate("Room levy")}</td><td className="text-right">{money(prices.levy)}</td></tr>
            )}
            <tr className="text-base font-semibold"><td colSpan={5} className="pt-1 text-right">{translate("Total")}</td><td className="pt-1 text-right">{money(prices.total)}</td></tr>
            {g.deposit_due > 0 && (
              <tr><td colSpan={5} className="pt-2 text-right text-zinc-600">{translate("Deposit to confirm")}</td><td className="pt-2 text-right font-medium">{money(g.deposit_due)}</td></tr>
            )}
          </tfoot>
        </table>

        <section className="space-y-1 text-zinc-600">
          <div className="font-medium text-zinc-800">{translate("Terms")}</div>
          <ul className="list-disc space-y-1 pl-5">
            <li>{translate("Rooms are held until {v0}. Rooms not named by then are released.", { v0: g.cutoff_date })}</li>
            {g.attrition_pct > 0 && (
              <li>{translate("Up to {v0}% of the room-nights can be released without charge; room-nights released beyond that are charged.", { v0: String(g.attrition_pct) })}</li>
            )}
            {g.master_pays && <li>{translate("The main room pays: {v0}. Each guest pays their own extras.", { v0: translate(g.master_pays) })}</li>}
            <li>{translate("Room prices exclude meals and extras unless stated. Tax as applicable on the day of stay.")}</li>
          </ul>
        </section>
      </div>
    </div>
  )
}
