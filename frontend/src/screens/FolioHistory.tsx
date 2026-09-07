import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Badge } from "../components/ui/badge"
import { moneyLocale } from "../lib/money"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

type FolioRow = {
  name: string
  guest_name: string
  reservation: string
  status: string
  invoice_number?: string
  grand_total: number
  balance: number
  closed_on?: string
  reprints: number
}

export default function FolioHistory() {
  const [q, setQ] = useState("")
  const [status, setStatus] = useState("")
  const [rows, setRows] = useState<FolioRow[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const out = await call<{ folios: FolioRow[] }>(
        "kamra.ledger.folio_history",
        {
          property: getCurrentProperty(),
          query: q || undefined,
          status: status || undefined,
        },
      )
      setRows(out.folios)
    } catch (e) {
      setErr(serverError(e))
    }
  }, [q, status])

  useEffect(() => {
    void load()
  }, [load])

  const toggle = (name: string) =>
    setSelected((s) =>
      s.includes(name) ? s.filter((x) => x !== name) : [...s, name],
    )

  const batchPrint = async () => {
    setBusy(true)
    try {
      await call("kamra.ledger.batch_print_folios", {
        folios: JSON.stringify(selected),
      })
      await load()
      setSelected([])
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
            Billing
          </p>
          <h1 className="text-2xl font-semibold">Folio History</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <input
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm"
            placeholder="Search guest / invoice"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <select
            className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All</option>
            <option value="Open">Open</option>
            <option value="Closed">Closed</option>
          </select>
          <Button
            variant="outline"
            disabled={!selected.length || busy}
            onClick={() => void batchPrint()}
          >
            Batch print ({selected.length})
          </Button>
        </div>
      </div>
      {err ? <p className="text-sm text-rose-600">{err}</p> : null}
      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-xs uppercase text-zinc-400">
            <tr>
              <th className="px-3 py-2" />
              <th className="px-3 py-2">Guest</th>
              <th className="px-3 py-2">Invoice</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Total</th>
              <th className="px-3 py-2">Balance</th>
              <th className="px-3 py-2">Reprints</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} className="border-t border-zinc-50">
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={selected.includes(r.name)}
                    onChange={() => toggle(r.name)}
                  />
                </td>
                <td className="px-3 py-2">
                  <Link
                    to={`/billing/${r.name}`}
                    className="font-medium text-brand-700 hover:underline"
                  >
                    {r.guest_name || r.name}
                  </Link>
                  <div className="text-xs text-zinc-400">{r.reservation}</div>
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  {r.invoice_number || "—"}
                </td>
                <td className="px-3 py-2">
                  <Badge tone={r.status === "Open" ? "green" : "zinc"}>
                    {r.status}
                  </Badge>
                </td>
                <td className="px-3 py-2 tabular-nums">{inr(r.grand_total)}</td>
                <td className="px-3 py-2 tabular-nums">{inr(r.balance)}</td>
                <td className="px-3 py-2">{r.reprints}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
