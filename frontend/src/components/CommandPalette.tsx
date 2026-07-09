/*  Command palette (⌘K / Ctrl+K).

    A fast "jump to anything" surface - Opera's "I Want To…" menu, reimagined
    as a fuzzy typeable overlay. Nav shortcuts on a cold prompt; guest /
    reservation search once you start typing; a couple of high-value quick
    actions. Every action it triggers is recorded in the Activity Log.
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
  Bed,
  Command as CmdIcon,
  FileText,
  Loader2,
  Search,
  UserCircle2,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { useAuth } from "../lib/auth"
import { visibleApps, type AppNavItem } from "../lib/apps"
import { cn } from "../lib/utils"

interface Result {
  id: string
  label: string
  hint: string
  icon: React.ComponentType<{ className?: string }>
  onSelect: () => void
}

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

// Nav commands are derived from the same role-filtered app registry the
// sidebar uses, so the palette reaches exactly the pages the user may open -
// no second list to keep in sync, and item-level gates (Developers, Frappe
// Desk) are honoured too.
function navItemsForRoles(roles: string[]): {
  item: AppNavItem
  app: string
}[] {
  const out: { item: AppNavItem; app: string }[] = []
  const seen = new Set<string>()
  for (const app of visibleApps(roles)) {
    for (const item of app.items) {
      if (item.roles && !item.roles.some((r) => roles.includes(r))) continue
      const key = item.to ?? item.href ?? item.label
      if (seen.has(key)) continue
      seen.add(key)
      out.push({ item, app: app.name })
    }
  }
  return out
}

export function CommandPalette() {
  const { roles } = useAuth()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState("")
  const [guests, setGuests] = useState<{ name: string; full_name: string; phone?: string }[]>([])
  const [reservations, setReservations] = useState<{ name: string; guest?: string; guest_name: string; check_in_date: string; status: string; room?: string | null }[]>([])
  const [invoices, setInvoices] = useState<{ name: string; invoice_number: string; reservation?: string; guest?: string; guest_name?: string; grand_total: number; status: string }[]>([])
  const [searching, setSearching] = useState(false)
  const [cursor, setCursor] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
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
      setInvoices([])
      setCursor(0)
    }
  }, [open])

  // typing moves the highlight back to the top of the fresh result set
  useEffect(() => setCursor(0), [q])

  // Debounced remote search once the user has typed at least 2 chars.
  useEffect(() => {
    if (!open || q.trim().length < 2) {
      setGuests([])
      setReservations([])
      setInvoices([])
      return
    }
    let cancelled = false
    setSearching(true)
    const handle = setTimeout(async () => {
      try {
        const [g, r, inv] = await Promise.all([
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
          call<{
            name: string
            invoice_number: string
            reservation?: string
            guest?: string
            guest_name?: string
            grand_total: number
            status: string
          }[]>("kamra.api.find_invoices", {
            property: getCurrentProperty(),
            query: q.trim(),
          }).catch(() => []),
        ])
        if (cancelled) return
        setGuests((g || []).slice(0, 5))
        setReservations((r || []).slice(0, 5))
        setInvoices((inv || []).slice(0, 5))
      } finally {
        if (!cancelled) setSearching(false)
      }
    }, 180)
    return () => {
      cancelled = true
      clearTimeout(handle)
    }
  }, [q, open])

  const navItems = useMemo(() => navItemsForRoles(roles), [roles])

  const navResults = useMemo<Result[]>(
    () =>
      navItems
        .filter(({ item, app }) => fuzzy(`${item.label} ${app}`, q))
        .map(({ item, app }) => ({
          id: `nav:${item.to ?? item.href ?? item.label}`,
          label: item.label,
          hint: app,
          icon: item.icon,
          onSelect: () => {
            setOpen(false)
            if (item.href) window.open(item.href, "_blank", "noreferrer")
            else if (item.to) navigate(item.to)
          },
        })),
    [navItems, q, navigate],
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

  const invoiceResults = useMemo<Result[]>(
    () =>
      invoices.map((f) => ({
        id: `inv:${f.name}`,
        label: `${f.invoice_number} · ${f.guest_name || ""}`.trim(),
        hint: `Invoice · ₹${(f.grand_total || 0).toLocaleString("en-IN")} · ${f.status}`,
        icon: FileText,
        onSelect: () => {
          setOpen(false)
          navigate(`/billing/${encodeURIComponent(f.name)}`)
        },
      })),
    [invoices, navigate],
  )

  const groups: { title: string; items: Result[] }[] = [
    { title: "Reservations", items: reservationResults },
    { title: "Invoices", items: invoiceResults },
    { title: "Guests", items: guestResults },
    { title: "Navigate", items: navResults },
  ]
  // one flat, ordered list for arrow-key navigation across all groups
  const flat = groups.flatMap((g) => g.items)
  const totalCount = flat.length

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setCursor((c) => (totalCount ? (c + 1) % totalCount : 0))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setCursor((c) => (totalCount ? (c - 1 + totalCount) % totalCount : 0))
    } else if (e.key === "Enter") {
      e.preventDefault()
      flat[cursor]?.onSelect()
    }
  }

  if (!open) return null

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
            onKeyDown={onKeyDown}
            placeholder="Search a guest, phone, booking, invoice - or jump to any screen…"
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

        <div ref={listRef} className="max-h-[60vh] overflow-y-auto p-2">
          {totalCount === 0 && (
            <div className="px-3 py-8 text-center text-sm text-zinc-500">
              {q.trim().length >= 2 ? (
                "No matches."
              ) : (
                <>
                  Search a guest, phone, booking or invoice.{" "}
                  <span className="text-zinc-400">Or jump to any screen.</span>
                </>
              )}
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
                    {grp.items.map((item) => {
                      const idx = flat.findIndex((f) => f.id === item.id)
                      const active = idx === cursor
                      return (
                        <li key={item.id}>
                          <button
                            onClick={item.onSelect}
                            onMouseEnter={() => setCursor(idx)}
                            ref={(el) => {
                              if (active && el)
                                el.scrollIntoView({ block: "nearest" })
                            }}
                            className={cn(
                              "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm",
                              active
                                ? "bg-brand-50 text-brand-700"
                                : "hover:bg-brand-50 hover:text-brand-700",
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
                      )
                    })}
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
          <span>Every action is recorded in the Activity Log.</span>
        </div>
      </div>
    </div>
  )
}
