import { useEffect, useState } from "react"
import { Columns3, Download, Search, Star } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { call } from "../lib/api"
import { Badge } from "../components/ui/badge"
import { cur, moneyLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"

interface GuestRow {
  name: string
  full_name: string
  phone: string | null
  email: string | null
  vip: 0 | 1
  bookings: number
  stays: number
  nights: number
  lifetime_value: number
  last_stay: string | null
}

const inr = (n: number) =>
  Number(n).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

// id, header, CSV value; the cell renders below
const COLUMNS = [
  { id: "full_name", label: "Guest", csv: (g: GuestRow) => g.full_name },
  { id: "phone", label: "Phone", csv: (g: GuestRow) => g.phone ?? "" },
  { id: "email", label: "Email", csv: (g: GuestRow) => g.email ?? "" },
  { id: "bookings", label: "Bookings", csv: (g: GuestRow) => g.bookings },
  { id: "stays", label: "Stays", csv: (g: GuestRow) => g.stays },
  { id: "nights", label: "Nights", csv: (g: GuestRow) => g.nights },
  { id: "lifetime_value", label: "Lifetime value", csv: (g: GuestRow) => g.lifetime_value },
  { id: "last_stay", label: "Last stay", csv: (g: GuestRow) => g.last_stay ?? "" },
] as const
type ColId = (typeof COLUMNS)[number]["id"]

// ponytail: per browser, like ResourceScreen's columns; move to Frappe user settings if desks share PCs
const COLS_KEY = "kamra:cols:Guest"

export default function Guests() {
  const { t } = useT()
  const [hidden, setHidden] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(COLS_KEY) || '["email"]'))
    } catch {
      return new Set(["email"])
    }
  })
  const [colsOpen, setColsOpen] = useState(false)
  const toggleCol = (id: string) =>
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else if (next.size < COLUMNS.length - 1) next.add(id)
      try {
        localStorage.setItem(COLS_KEY, JSON.stringify([...next]))
      } catch {
        /* private window: the choice lasts for this visit */
      }
      return next
    })
  const shown = COLUMNS.filter((c) => !hidden.has(c.id))
  const on = (id: ColId) => !hidden.has(id)
  const [rows, setRows] = useState<GuestRow[]>([])
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(0)
  const PAGE = 25
  const navigate = useNavigate()

  useEffect(() => {
    const timer = setTimeout(() => {
      call<GuestRow[]>("kamra.api.guests_with_stats", {
        search: search || undefined,
      }).then((r) => {
        setRows(r)
        setPage(0)
      })
    }, 250)
    return () => clearTimeout(timer)
  }, [search])

  const visible = rows.slice(page * PAGE, page * PAGE + PAGE)

  function exportCsv() {
    const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`
    const csv = [
      shown.map((c) => esc(t(c.label))).join(","),
      ...rows.map((g) => shown.map((c) => esc(c.csv(g))).join(",")),
    ].join("\n")
    const a = document.createElement("a")
    a.href = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }))
    a.download = `guests-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t("Guests")}</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            {t("Every guest, their stays and lifetime value. Click for the full journey.")}
          </p>
        </div>
        <div className="flex items-center gap-2">
        <button
          onClick={exportCsv}
          disabled={rows.length === 0}
          title={t("Download the current view as CSV (Excel-ready)")}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-sm text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700 disabled:opacity-50"
        >
          <Download className="size-4" aria-hidden />
          {t("Export")}
        </button>
        <div className="relative">
          <button
            onClick={() => setColsOpen((o) => !o)}
            title={t("Choose which columns this table shows")}
            aria-label={t("Configure table columns")}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-sm text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700"
          >
            <Columns3 className="size-4" aria-hidden />
            {t("Columns")}
          </button>
          {colsOpen && (
            <div className="absolute right-0 z-30 mt-1 w-56 rounded-xl border border-zinc-200 bg-white p-2 shadow-xl">
              {COLUMNS.map((c) => (
                <label
                  key={c.id}
                  className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-zinc-50"
                >
                  <input
                    type="checkbox"
                    className="size-4 accent-brand-600"
                    checked={!hidden.has(c.id)}
                    onChange={() => toggleCol(c.id)}
                  />
                  {t(c.label)}
                </label>
              ))}
              <button
                className="mt-1 w-full rounded-lg px-2 py-1 text-left text-xs text-zinc-400 hover:text-zinc-600"
                onClick={() => setColsOpen(false)}
              >
                {t("Done")}
              </button>
            </div>
          )}
        </div>
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-2 size-4 text-zinc-400"
            aria-hidden
          />
          <input
            className="rounded-lg border border-zinc-300 py-1.5 pl-8 pr-3 text-sm focus:outline-2 focus:outline-brand-600"
            placeholder={t("Name or phone…")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                {shown.map((c) => (
                  <th key={c.id} className="py-2 pr-4">
                    {c.id === "lifetime_value" ? t("Lifetime {cur}", { cur: cur() }) : t(c.label)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {visible.map((g) => (
                <tr
                  key={g.name}
                  className="cursor-pointer hover:bg-zinc-50"
                  onClick={() => navigate(`/guests/${encodeURIComponent(g.name)}`)}
                >
                  {on("full_name") && <td className="py-2.5 pr-4">
                    <span className="font-medium">{g.full_name}</span>
                    {Boolean(g.vip) && (
                      <Star
                        className="ml-1.5 inline size-3.5 fill-amber-400 text-amber-400"
                        aria-label={t("VIP")}
                      />
                    )}
                  </td>}
                  {on("phone") && <td className="py-2.5 pr-4 text-zinc-500">
                    {g.phone ?? "-"}
                  </td>}
                  {on("email") && <td className="py-2.5 pr-4 text-zinc-500">{g.email ?? "-"}</td>}
                  {on("bookings") && <td className="py-2.5 pr-4">{g.bookings}</td>}
                  {on("stays") && <td className="py-2.5 pr-4">{g.stays}</td>}
                  {on("nights") && <td className="py-2.5 pr-4">{g.nights}</td>}
                  {on("lifetime_value") && <td className="py-2.5 pr-4 font-medium">
                    {cur()}{inr(g.lifetime_value)}
                  </td>}
                  {on("last_stay") && <td className="py-2.5 pr-4 text-zinc-500">
                    {g.last_stay ? (
                      g.last_stay
                    ) : (
                      <Badge tone="zinc">{t("never")}</Badge>
                    )}
                  </td>}
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={shown.length}
                    className="py-6 text-center text-sm text-zinc-400"
                  >
                    {t("No guests found.")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}
