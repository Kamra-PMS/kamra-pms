/*  Command palette (⌘K / Ctrl+K).

    A fast "jump to anything" surface - one box that reaches every screen,
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
  LayoutGrid,
  LogOut,
  Search,
  Settings2,
  Sparkles,
  UserCircle2,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { useAuth } from "../lib/auth"
import { visibleApps, type AppNavItem } from "../lib/apps"
import { FEATURES } from "../lib/searchIndex"
import { cn } from "../lib/utils"
import { cur, moneyLocale } from "../lib/money"
import { useT, t as translate } from "../lib/i18n"


interface Result {
  id: string
  label: string
  hint: string
  icon: React.ComponentType<{ className?: string }>
  onSelect: () => void
}

// Every typed word must start a word of the text ("cash dr" finds "Cash
// drop"), so a few letters never match half the app the way a loose
// in-order letter match does. Score: lower is better.
function rank(text: string, q: string): number | null {
  const words = text.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(Boolean)
  const toks = q.toLowerCase().split(/\s+/).filter(Boolean)
  if (!toks.length) return 0
  let score = 0
  for (const tok of toks) {
    const i = words.findIndex((w) => w.startsWith(tok))
    if (i < 0) {
      if (!text.toLowerCase().includes(tok)) return null
      score += 20
    } else score += i === 0 ? 0 : 2 + Math.min(i, 6)
  }
  return score
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
  const { t } = useT()
  const { roles } = useAuth()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState("")
  const [guests, setGuests] = useState<{ name: string; full_name: string; phone?: string }[]>([])
  const [reservations, setReservations] = useState<{ name: string; guest?: string; guest_name: string; check_in_date: string; status: string; room?: string | null }[]>([])
  const [invoices, setInvoices] = useState<{ name: string; invoice_number: string; reservation?: string; guest?: string; guest_name?: string; grand_total: number; status: string }[]>([])
  const [searching, setSearching] = useState(false)
  const [settingsIdx, setSettingsIdx] = useState<
    { id: string; label: string; where: string; to: string; words: string }[]
  >([])
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

  // The settings registry, once per open: every setting by name, so
  // "refund limit" or "pin" lands on the page that holds it.
  useEffect(() => {
    if (!open || settingsIdx.length) return
    type Schema = {
      modules: {
        id: string
        title: string
        description?: string
        sections: { title: string; settings: { key: string; label: string; hint?: string }[] }[]
      }[]
    }
    call<Schema>("kamra.settings.settings_schema", { property: getCurrentProperty() })
      .then((sc) => {
        const out: typeof settingsIdx = []
        for (const m of sc.modules ?? []) {
          out.push({ id: `set:${m.id}`, label: m.title, where: "Settings", to: `/settings/${m.id}`, words: `${m.title} ${m.description ?? ""} settings` })
          for (const sec of m.sections) {
            for (const st of sec.settings) {
              out.push({
                id: `set:${m.id}:${st.key}`,
                label: st.label,
                where: `${m.title} › ${sec.title}`,
                to: `/settings/${m.id}`,
                words: `${st.label} ${st.hint ?? ""} ${sec.title} ${m.title}`,
              })
            }
          }
        }
        setSettingsIdx(out)
      })
      .catch(() => undefined)
  }, [open, settingsIdx.length])

  // typing moves the highlight back to the top of the fresh result set
  useEffect(() => setCursor(0), [q])

  // Debounced remote search once the user has typed at least 2 chars.
  // "check out 204" searches for "204"
  const searchQ = q.replace(/check\s*-?\s*out/i, "").trim()
  useEffect(() => {
    if (!open || searchQ.length < 2) {
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
            { q: searchQ },
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
            query: searchQ,
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
            query: searchQ,
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
  }, [searchQ, open])

  const navItems = useMemo(() => navItemsForRoles(roles), [roles])

  const navResults = useMemo<Result[]>(
    () =>
      navItems
        .map(({ item, app }) => ({
          item,
          app,
          score: rank(
            `${t(item.label)} ${item.label} ${t(app)} ${item.group ?? ""} ${(item.keywords ?? []).map((k) => `${k} ${t(k)}`).join(" ")}`,
            q,
          ),
        }))
        .filter((r) => r.score !== null)
        .sort((a, b) => (a.score ?? 0) - (b.score ?? 0))
        .map(({ item, app }) => ({
          id: `nav:${item.to ?? item.href ?? item.label}`,
          label: t(item.label),
          hint: item.group ? `${t(app)} · ${t(item.group)}` : t(app),
          icon: item.icon,
          onSelect: () => {
            setOpen(false)
            if (item.href) window.open(item.href, "_blank", "noreferrer")
            else if (item.to) navigate(item.to)
          },
        })),
    [navItems, q, navigate, t],
  )

  // Jobs people ask for by name, and the app (module) each belongs to.
  const reachable = useMemo(() => new Set(navItems.map((n) => n.item.to).filter(Boolean)), [navItems])
  const featureResults = useMemo<Result[]>(() => {
    if (!q.trim()) return []
    return FEATURES.filter((f) => reachable.has(f.to) || f.to === "/")
      .map((f) => ({ f, score: rank(`${t(f.label)} ${f.label} ${f.where} ${f.keywords.join(" ")}`, q) }))
      .filter((r) => r.score !== null)
      .sort((a, b) => (a.score ?? 0) - (b.score ?? 0))
      .slice(0, 6)
      .map(({ f }) => ({
        id: `feat:${f.label}`,
        label: t(f.label),
        hint: t(f.where),
        icon: Sparkles,
        onSelect: () => {
          setOpen(false)
          navigate(f.to)
        },
      }))
  }, [q, reachable, navigate, t])

  const settingResults = useMemo<Result[]>(() => {
    if (!q.trim()) return []
    return settingsIdx
      .map((x) => ({ x, score: rank(x.words, q) }))
      .filter((r) => r.score !== null)
      .sort((a, b) => (a.score ?? 0) - (b.score ?? 0))
      .slice(0, 6)
      .map(({ x }) => ({
        id: x.id,
        label: t(x.label),
        hint: `${t("Setting")} · ${t(x.where)}`,
        icon: Settings2,
        onSelect: () => {
          setOpen(false)
          navigate(x.to)
        },
      }))
  }, [q, settingsIdx, navigate, t])

  // The apps themselves: "revenue", "housekeeping" open that module.
  const moduleResults = useMemo<Result[]>(() => {
    if (!q.trim()) return []
    return visibleApps(roles)
      .map((a) => ({ a, score: rank(`${t(a.name)} ${a.name} ${a.description} module app`, q) }))
      .filter((r) => r.score !== null && r.a.items.some((i) => i.to))
      .sort((x, y) => (x.score ?? 0) - (y.score ?? 0))
      .slice(0, 3)
      .map(({ a }) => ({
        id: `app:${a.id}`,
        label: t(a.name),
        hint: `${t("Module")} · ${t(a.description)}`,
        icon: LayoutGrid,
        onSelect: () => {
          setOpen(false)
          navigate(a.items.find((i) => i.to)!.to!)
        },
      }))
  }, [q, roles, navigate, t])

  const guestResults = useMemo<Result[]>(
    () =>
      guests.map((g) => ({
        id: `guest:${g.name}`,
        label: g.full_name || g.name,
        hint: `${t("Guest")} · ${g.phone || g.name}`,
        icon: UserCircle2,
        onSelect: () => {
          setOpen(false)
          navigate(`/guests/${encodeURIComponent(g.name)}`)
        },
      })),
    [guests, navigate, t],
  )

  const reservationResults = useMemo<Result[]>(
    () =>
      reservations.map((r) => ({
        id: `res:${r.name}`,
        label: `${r.name} · ${r.guest_name || ""}`.trim(),
        hint: `${t(r.status)} · ${t("check-in")} ${r.check_in_date}${r.room ? ` · ${r.room}` : ""}`,
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
    [reservations, navigate, t],
  )

  // check-out shortcut: "check out" (or a room / guest) finds the in-house
  // stay and opens the guided check-out sheet on Today
  const wantsCheckout = /check\s*-?\s*out/i.test(q)
  const checkoutResults = useMemo<Result[]>(() => {
    const stays = reservations.filter((r) => r.status === "Checked In")
    const out: Result[] = stays.map((r) => ({
      id: `checkout:${r.name}`,
      label: t("Check out {guest}", { guest: r.guest_name || r.name }),
      hint: `${r.name}${r.room ? ` · ${r.room}` : ""}`,
      icon: LogOut,
      onSelect: () => {
        setOpen(false)
        navigate("/", { state: { checkout: r.name } })
      },
    }))
    if (!out.length && wantsCheckout)
      out.push({
        id: "checkout:help",
        label: t("Check out a guest"),
        hint: t("Type the room number or the guest's name"),
        icon: LogOut,
        onSelect: () => setQ(""),
      })
    return out
  }, [reservations, wantsCheckout, navigate, t])

  const invoiceResults = useMemo<Result[]>(
    () =>
      invoices.map((f) => ({
        id: `inv:${f.name}`,
        label: `${f.invoice_number} · ${f.guest_name || ""}`.trim(),
        hint: `${t("Invoice")} · ${cur()}${(f.grand_total || 0).toLocaleString(moneyLocale())} · ${t(f.status)}`,
        icon: FileText,
        onSelect: () => {
          setOpen(false)
          navigate(`/billing/${encodeURIComponent(f.name)}`)
        },
      })),
    [invoices, navigate, t],
  )

  const groups: { title: string; items: Result[] }[] = [
    { title: t("Check out"), items: checkoutResults },
    { title: t("Reservations"), items: reservationResults },
    { title: t("Invoices"), items: invoiceResults },
    { title: t("Guests"), items: guestResults },
    { title: t("Screens"), items: navResults },
    { title: t("Features"), items: featureResults },
    { title: t("Settings"), items: settingResults },
    { title: t("Modules"), items: moduleResults },
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
      aria-label={t("Concierge")}
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
            placeholder={t("Search guests, bookings, invoices, screens, features, settings…")}
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
                t("No matches.")
              ) : (
                <>
                  {t("Search a guest, phone, booking or invoice.")}{" "}
                  <span className="text-zinc-400">{t("Or a screen, a feature (cash drop, night audit, BAR rates) or a setting.")}</span>
                </>
              )}
            </div>
          )}

          {groups.map(
            (grp) =>
              grp.items.length > 0 && (
                <div key={grp.title} className="mb-2">
                  <div className="px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-400">
                    {translate(grp.title)}
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
                              <div className="truncate font-medium">{translate(item.label)}</div>
                              <div className="truncate text-xs text-zinc-500">
                                {translate(item.hint)}
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
            {t("to open")} ·{" "}
            <kbd className="rounded bg-white px-1 font-mono">esc</kbd>{" "}
            {t("to close")}
          </span>
          <span>{t("Every action is recorded in the Activity Log.")}</span>
        </div>
      </div>
    </div>
  )
}
