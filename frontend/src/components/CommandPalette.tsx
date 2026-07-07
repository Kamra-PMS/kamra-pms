/*  Command palette (⌘K / Ctrl+K).

    The humans' agent surface - Opera's "I Want To…" menu, reimagined as a
    fuzzy typeable overlay that dispatches through the same autonomy gate
    as the AI agents. Nav shortcuts on a cold prompt; guest / reservation
    search once you start typing; a couple of high-value quick actions.
*/

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { useNavigate } from "react-router-dom"
import {
  ArrowRight,
  BadgePercent,
  Bed,
  BedDouble,
  Briefcase,
  Building2,
  CalendarDays,
  ClipboardList,
  Clock,
  Command as CmdIcon,
  Home,
  IndianRupee,
  Landmark,
  LayoutGrid,
  ListChecks,
  Loader2,
  PackageSearch,
  PartyPopper,
  Receipt,
  Search,
  Settings as SettingsIcon,
  ShieldCheck,
  Sparkles,
  Tags,
  Ticket as TicketIcon,
  UserCircle2,
  Users,
  UtensilsCrossed,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { cn } from "../lib/utils"

interface NavCmd {
  kind: "nav"
  id: string
  label: string
  hint: string
  path: string
  icon: React.ComponentType<{ className?: string }>
}

interface Result {
  id: string
  label: string
  hint: string
  icon: React.ComponentType<{ className?: string }>
  onSelect: () => void
}

const NAV_COMMANDS: NavCmd[] = [
  { kind: "nav", id: "nav:today", label: "Go to Today", hint: "arrivals, departures, room board", path: "/", icon: Home },
  { kind: "nav", id: "nav:copilot", label: "Open Copilot", hint: "chat with NOVA · AI staff · approvals · activity", path: "/assistant", icon: Sparkles },
  { kind: "nav", id: "nav:reservations", label: "Go to Reservations", hint: "search & manage bookings", path: "/reservations", icon: ClipboardList },
  { kind: "nav", id: "nav:tape", label: "Go to Tape Chart", hint: "rooms × dates grid", path: "/tape", icon: LayoutGrid },
  { kind: "nav", id: "nav:calendar", label: "Go to Calendar", hint: "availability by room type", path: "/calendar", icon: CalendarDays },
  { kind: "nav", id: "nav:guests", label: "Go to Guests", hint: "profiles & stay history", path: "/guests", icon: Users },
  { kind: "nav", id: "nav:hk", label: "Open Housekeeping", hint: "room status board", path: "/housekeeping", icon: ListChecks },
  { kind: "nav", id: "nav:requests", label: "Go to Guest Requests", hint: "open service requests", path: "/tickets", icon: TicketIcon },
  { kind: "nav", id: "nav:lostfound", label: "Go to Lost & Found", hint: "items found & claimed", path: "/lost-found", icon: PackageSearch },
  { kind: "nav", id: "nav:shifts", label: "Go to Shifts", hint: "handover & cash counts", path: "/shifts", icon: Clock },
  { kind: "nav", id: "nav:billing", label: "Go to Billing", hint: "folios, invoices, night audit", path: "/billing", icon: Receipt },
  { kind: "nav", id: "nav:reports", label: "Go to Reports", hint: "occupancy, ADR, RevPAR", path: "/reports", icon: IndianRupee },
  { kind: "nav", id: "nav:companies", label: "Go to Companies", hint: "corporate accounts & rates", path: "/companies", icon: Building2 },
  { kind: "nav", id: "nav:events", label: "Go to Event Bookings", hint: "banquets & functions", path: "/events", icon: PartyPopper },
  { kind: "nav", id: "nav:venuecal", label: "Open Venue Calendar", hint: "function diary", path: "/venue-calendar", icon: CalendarDays },
  { kind: "nav", id: "nav:groups", label: "Go to Groups & Blocks", hint: "room blocks & pickup", path: "/groups", icon: Users },
  { kind: "nav", id: "nav:rooms", label: "Go to Rooms", hint: "room inventory", path: "/rooms", icon: BedDouble },
  { kind: "nav", id: "nav:roomtypes", label: "Go to Room Types", hint: "categories, photos, pricing", path: "/room-types", icon: LayoutGrid },
  { kind: "nav", id: "nav:venues", label: "Go to Venues", hint: "halls, lawns & rates", path: "/venues", icon: Landmark },
  { kind: "nav", id: "nav:rateplans", label: "Go to Rate Plans", hint: "packages & modifiers", path: "/rate-plans", icon: Tags },
  { kind: "nav", id: "nav:seasons", label: "Go to Seasons", hint: "seasonal pricing windows", path: "/seasons", icon: CalendarDays },
  { kind: "nav", id: "nav:guardrails", label: "Go to Guardrails", hint: "rate floors & ceilings", path: "/guardrails", icon: ShieldCheck },
  { kind: "nav", id: "nav:vouchers", label: "Go to Vouchers", hint: "discount codes", path: "/vouchers", icon: BadgePercent },
  { kind: "nav", id: "nav:mealplans", label: "Go to Meal Plans", hint: "CP, MAP, AP rates", path: "/meal-plans", icon: UtensilsCrossed },
  { kind: "nav", id: "nav:agents-ta", label: "Go to Travel Agents", hint: "agents & commissions", path: "/travel-agents", icon: Briefcase },
  { kind: "nav", id: "nav:settings", label: "Go to Settings", hint: "property, GST, booking page, AI", path: "/settings", icon: SettingsIcon },
]

// Simple substring fuzzy: every character of q must appear in order in text.
function fuzzy(text: string, q: string): boolean {
  if (!q) return true
  const t = text.toLowerCase()
  const s = q.toLowerCase()
  let i = 0
  for (const ch of t) {
    if (ch === s[i]) i++
    if (i === s.length) return true
  }
  return false
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState("")
  const [guests, setGuests] = useState<{ name: string; full_name: string; phone?: string }[]>([])
  const [reservations, setReservations] = useState<{ name: string; guest?: string; guest_name: string; check_in_date: string; status: string; room?: string | null }[]>([])
  const [searching, setSearching] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  // Global shortcut: ⌘K on Mac, Ctrl+K elsewhere.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const meta = e.metaKey || e.ctrlKey
      if (meta && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setOpen((prev) => !prev)
      } else if (e.key === "Escape" && open) {
        setOpen(false)
      }
    }
    const onOpen = () => setOpen(true)
    window.addEventListener("keydown", onKey)
    window.addEventListener("kamra:open-palette", onOpen)
    return () => {
      window.removeEventListener("keydown", onKey)
      window.removeEventListener("kamra:open-palette", onOpen)
    }
  }, [open])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 20)
    else {
      setQ("")
      setGuests([])
      setReservations([])
    }
  }, [open])

  // Debounced remote search once the user has typed at least 2 chars.
  useEffect(() => {
    if (!open || q.trim().length < 2) {
      setGuests([])
      setReservations([])
      return
    }
    let cancelled = false
    setSearching(true)
    const handle = setTimeout(async () => {
      try {
        const [g, r] = await Promise.all([
          call<{ name: string; full_name: string; phone?: string }[]>(
            "kamra.api.guest_search",
            { q: q.trim() },
          ).catch(() => []),
          call<{
            name: string
            guest?: string
            guest_name: string
            check_in_date: string
            status: string
            room?: string | null
          }[]>("kamra.api.find_reservations", {
            property: getCurrentProperty(),
            query: q.trim(),
          }).catch(() => []),
        ])
        if (cancelled) return
        setGuests((g || []).slice(0, 5))
        setReservations((r || []).slice(0, 5))
      } finally {
        if (!cancelled) setSearching(false)
      }
    }, 180)
    return () => {
      cancelled = true
      clearTimeout(handle)
    }
  }, [q, open])

  const navResults = useMemo<Result[]>(
    () =>
      NAV_COMMANDS.filter((c) => fuzzy(c.label + " " + c.hint, q)).map((c) => ({
        id: c.id,
        label: c.label,
        hint: c.hint,
        icon: c.icon,
        onSelect: () => {
          setOpen(false)
          navigate(c.path)
        },
      })),
    [q, navigate],
  )

  const guestResults = useMemo<Result[]>(
    () =>
      guests.map((g) => ({
        id: `guest:${g.name}`,
        label: g.full_name || g.name,
        hint: `Guest · ${g.phone || g.name}`,
        icon: UserCircle2,
        onSelect: () => {
          setOpen(false)
          navigate(`/guests/${encodeURIComponent(g.name)}`)
        },
      })),
    [guests, navigate],
  )

  const reservationResults = useMemo<Result[]>(
    () =>
      reservations.map((r) => ({
        id: `res:${r.name}`,
        label: `${r.name} · ${r.guest_name || ""}`.trim(),
        hint: `${r.status} · check-in ${r.check_in_date}${r.room ? ` · ${r.room}` : ""}`,
        icon: Bed,
        onSelect: () => {
          setOpen(false)
          // land on the guest's own screen (their stay, folio, journey),
          // not a filtered list
          navigate(
            r.guest
              ? `/guests/${encodeURIComponent(r.guest)}`
              : `/reservations?q=${encodeURIComponent(r.name)}`,
          )
        },
      })),
    [reservations, navigate],
  )

  if (!open) return null

  const groups: { title: string; items: Result[] }[] = [
    { title: "Reservations", items: reservationResults },
    { title: "Guests", items: guestResults },
    { title: "Navigate", items: navResults },
  ]
  const totalCount = groups.reduce((s, g) => s + g.items.length, 0)

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Concierge"
      className="fixed inset-0 z-50 flex items-start justify-center bg-zinc-900/40 px-4 pt-24 backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-xl"
      >
        <div className="flex items-center gap-3 border-b border-zinc-100 px-4 py-3">
          <Search className="size-4 text-zinc-400" aria-hidden />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Concierge - find a guest, a booking, or jump to any screen…"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-zinc-400"
          />
          {searching ? (
            <Loader2 className="size-4 animate-spin text-zinc-400" aria-hidden />
          ) : (
            <kbd className="hidden rounded-md border border-zinc-200 bg-zinc-50 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500 md:inline">
              esc
            </kbd>
          )}
        </div>

        <div className="max-h-[60vh] overflow-y-auto p-2">
          {totalCount === 0 && (
            <div className="px-3 py-8 text-center text-sm text-zinc-500">
              No matches.{" "}
              <span className="text-zinc-400">Try a name, a phone, or RES-…</span>
            </div>
          )}

          {groups.map(
            (grp) =>
              grp.items.length > 0 && (
                <div key={grp.title} className="mb-2">
                  <div className="px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-400">
                    {grp.title}
                  </div>
                  <ul>
                    {grp.items.map((item) => (
                      <li key={item.id}>
                        <button
                          onClick={item.onSelect}
                          className={cn(
                            "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm",
                            "hover:bg-brand-50 hover:text-brand-700",
                          )}
                        >
                          <item.icon className="size-4 shrink-0 text-zinc-400" aria-hidden />
                          <div className="min-w-0 flex-1">
                            <div className="truncate font-medium">{item.label}</div>
                            <div className="truncate text-xs text-zinc-500">
                              {item.hint}
                            </div>
                          </div>
                          <ArrowRight className="size-3.5 shrink-0 text-zinc-300" aria-hidden />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ),
          )}
        </div>

        <div className="flex items-center justify-between border-t border-zinc-100 bg-zinc-50 px-3 py-2 text-[11px] text-zinc-500">
          <span className="inline-flex items-center gap-1.5">
            <CmdIcon className="size-3" aria-hidden />
            <kbd className="rounded bg-white px-1 font-mono">K</kbd>
            to open · <kbd className="rounded bg-white px-1 font-mono">esc</kbd> to close
          </span>
          <span>Actions log to the Agents Timeline.</span>
        </div>
      </div>
    </div>
  )
}
