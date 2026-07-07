import { useEffect, useState } from "react"
import { Search, Star } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { call } from "../lib/api"
import { Badge } from "../components/ui/badge"
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
  Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })

export default function Guests() {
  const [rows, setRows] = useState<GuestRow[]>([])
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(0)
  const PAGE = 25
  const navigate = useNavigate()

  useEffect(() => {
    const t = setTimeout(() => {
      call<GuestRow[]>("kamra.api.guests_with_stats", {
        search: search || undefined,
      }).then((r) => {
        setRows(r)
        setPage(0)
      })
    }, 250)
    return () => clearTimeout(t)
  }, [search])

  const visible = rows.slice(page * PAGE, page * PAGE + PAGE)

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Guests</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            Every guest, their stays and lifetime value. Click for the full
            journey.
          </p>
        </div>
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-2 size-4 text-zinc-400"
            aria-hidden
          />
          <input
            className="rounded-lg border border-zinc-300 py-1.5 pl-8 pr-3 text-sm focus:outline-2 focus:outline-brand-600"
            placeholder="Name or phone…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                <th className="py-2 pr-4">Guest</th>
                <th className="py-2 pr-4">Phone</th>
                <th className="py-2 pr-4">Bookings</th>
                <th className="py-2 pr-4">Stays</th>
                <th className="py-2 pr-4">Nights</th>
                <th className="py-2 pr-4">Lifetime ₹</th>
                <th className="py-2 pr-4">Last stay</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {visible.map((g) => (
                <tr
                  key={g.name}
                  className="cursor-pointer hover:bg-zinc-50"
                  onClick={() => navigate(`/guests/${encodeURIComponent(g.name)}`)}
                >
                  <td className="py-2.5 pr-4">
                    <span className="font-medium">{g.full_name}</span>
                    {Boolean(g.vip) && (
                      <Star
                        className="ml-1.5 inline size-3.5 fill-amber-400 text-amber-400"
                        aria-label="VIP"
                      />
                    )}
                  </td>
                  <td className="py-2.5 pr-4 text-zinc-500">
                    {g.phone ?? "-"}
                  </td>
                  <td className="py-2.5 pr-4">{g.bookings}</td>
                  <td className="py-2.5 pr-4">{g.stays}</td>
                  <td className="py-2.5 pr-4">{g.nights}</td>
                  <td className="py-2.5 pr-4 font-medium">
                    ₹{inr(g.lifetime_value)}
                  </td>
                  <td className="py-2.5 pr-4 text-zinc-500">
                    {g.last_stay ? (
                      g.last_stay
                    ) : (
                      <Badge tone="zinc">never</Badge>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="py-6 text-center text-sm text-zinc-400"
                  >
                    No guests found.
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
