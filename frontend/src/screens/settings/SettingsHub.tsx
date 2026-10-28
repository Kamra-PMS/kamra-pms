import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom"
import {
  BarChart3,
  BedDouble,
  Bot,
  Building2,
  CalendarRange,
  ClipboardCheck,
  Code2,
  CreditCard,
  ExternalLink,
  FileCheck2,
  Globe,
  Landmark,
  LayoutGrid,
  ListTodo,
  Palette,
  ScrollText,
  Search,
  ShieldCheck,
  ToggleRight,
  Users,
  UtensilsCrossed,
  Webhook,
  type LucideIcon,
} from "lucide-react"

import { Badge } from "../../components/ui/badge"
import { call, getCurrentProperty } from "../../lib/api"
import { useT, t as translate } from "../../lib/i18n"
import { useLocale } from "../../lib/money"
import { serverError } from "../../lib/resource"
import { cn } from "../../lib/utils"
import { ModulesPage, StaffPage } from "./AccessPages"
import { settingsSchema, setModuleEnabled, type SettingsSchema, type SettingsModule } from "./api"
import {
  AgentAccessCard,
  AiSection,
  AppearanceCard,
  CheckInStepsCard,
  NightAuditScheduleCard,
  HurdleRatesCard,
  KamraVerifyCard,
  LaundryRatesCard,
  PaymentsSection,
  SpeedCheckCard,
  KitchenPrintersCard,
  TIMEZONES,
  ZatcaCard,
} from "./cards"
import { McpAccessPage } from "./McpAccessPage"
import { ModulePage, Switch, type OptionSources } from "./ModulePage"
import { WebhooksPage } from "./WebhooksPage"


/** Settings hub. One place, one left rail: the property, each module's
 *  own page, who can do what, and the integrations - with search across
 *  every setting. Each module page is also linked from its own app. */

const MODULE_ICON: Record<string, LucideIcon> = {
  general: Building2,
  policies: ScrollText,
  privacy: ShieldCheck,
  "front-desk": BedDouble,
  housekeeping: ClipboardCheck,
  operations: ListTodo,
  fnb: UtensilsCrossed,
  events: CalendarRange,
  revenue: BarChart3,
  finance: Landmark,
  "booking-engine": Globe,
}

interface CustomPage {
  id: string
  title: string
  description: string
  group: "access" | "integrations" | "personal"
  icon: LucideIcon
  keywords: string
}

const CUSTOM_PAGES: CustomPage[] = [
  { id: "staff", title: "Staff & access", group: "access", icon: Users,
    description: "Who can sign in, what each person can do and which properties they reach.",
    keywords: "users people invite roles permissions deactivate cashier pin reset team employees matrix rights" },
  { id: "modules", title: "Modules", group: "access", icon: ToggleRight,
    description: "Switch off the parts of Kamra this property doesn't run.",
    keywords: "apps enable disable switch off restaurant banquets events housekeeping" },
  { id: "payments", title: "Payments", group: "integrations", icon: CreditCard,
    description: "The payment-link gateway for advances and folio settlement.",
    keywords: "razorpay cashfree gateway payment link keys webhook" },
  { id: "ai", title: "AI assistant", group: "integrations", icon: Bot,
    description: "Bring your own AI key for Kamra Agent in the console.",
    keywords: "openai gemini groq openrouter key model llm kamra agent chat" },
  { id: "claude", title: "AI access (MCP)", group: "access", icon: LayoutGrid,
    description: "Who may connect Claude or another AI client, what it may do here, and the live connections.",
    keywords: "mcp claude chatgpt n8n desktop connector oauth agent ai access read manage permissions roles block tools disconnect" },
  { id: "webhooks", title: "Webhooks", group: "integrations", icon: Webhook,
    description: "Send bookings, check-ins, folio postings and the night audit to another system as signed events.",
    keywords: "webhook integration events api door lock pos crm data warehouse signature delivery log resend" },
  { id: "verify", title: "Kamra Verify", group: "integrations", icon: FileCheck2,
    description: "Tax ID and guest ID checks through Kamra Connect.",
    keywords: "gstin aadhaar passport verify connect wallet" },
  { id: "zatca", title: "ZATCA e-invoicing", group: "integrations", icon: FileCheck2,
    description: "Saudi Arabia (FATOORA): seller details for every invoice XML.",
    keywords: "saudi vat fatoora e-invoice qr xml" },
  { id: "appearance", title: "Appearance", group: "personal", icon: Palette,
    description: "Theme and language for this browser.",
    keywords: "dark mode theme language arabic rtl spanish español idioma es" },
]

const GROUPS: { id: string; label: string }[] = [
  { id: "organisation", label: "Property" },
  { id: "modules", label: "Modules" },
  { id: "access", label: "Access" },
  { id: "integrations", label: "Integrations" },
  { id: "personal", label: "You" },
]

interface NavEntry {
  id: string
  title: string
  description: string
  group: string
  icon: LucideIcon
  off?: boolean
}

interface SearchHit {
  page: string
  pageTitle: string
  label: string
  sub?: string
  key?: string
}

export default function SettingsHub() {
  const { t } = useT()
  const { section } = useParams()
  const [search] = useSearchParams()
  const navigate = useNavigate()
  const loc = useLocale()
  const property = getCurrentProperty()

  const [schema, setSchema] = useState<SettingsSchema | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [countries, setCountries] = useState<string[]>([])
  const [dirty, setDirty] = useState(false)
  const [q, setQ] = useState("")
  const [searchOpen, setSearchOpen] = useState(false)
  const [toggleBusy, setToggleBusy] = useState(false)
  const searchRef = useRef<HTMLInputElement>(null)

  const load = useCallback(() => {
    settingsSchema().then(setSchema).catch((e) => setError(serverError(e)))
  }, [])
  useEffect(() => {
    load()
    call<{ country: string }[]>("kamra.api.localization_countries")
      .then((cs) => setCountries(cs.map((c) => c.country)))
      .catch(() => setCountries([]))
  }, [load, property])

  // "/" focuses settings search, like most enterprise consoles
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) && !el.isContentEditable) {
        e.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  // leaving the tab with unsaved changes asks first
  useEffect(() => {
    if (!dirty) return
    const onUnload = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener("beforeunload", onUnload)
    return () => window.removeEventListener("beforeunload", onUnload)
  }, [dirty])

  const country = String(schema?.modules.find((m) => m.id === "general")?.values.country ?? "")
  const verifyOn = loc.integrations.verify_tax_id || loc.integrations.verify_guest_id

  const nav: NavEntry[] = useMemo(() => {
    if (!schema) return []
    const mods: NavEntry[] = schema.modules.map((m) => ({
      id: m.id, title: m.title, description: m.description, group: m.group,
      icon: MODULE_ICON[m.id] ?? LayoutGrid, off: m.toggle && !m.enabled,
    }))
    const custom = CUSTOM_PAGES.filter((p) => {
      if (p.group === "personal") return true
      if (!schema.is_admin) return false
      if (p.id === "zatca") return country === "Saudi Arabia"
      if (p.id === "verify") return verifyOn
      return true
    })
    return [...mods, ...custom]
  }, [schema, country, verifyOn])

  const sources: OptionSources = useMemo(
    () => ({ countries, timezones: TIMEZONES }),
    [countries],
  )

  const hits: SearchHit[] = useMemo(() => {
    const terms = q.trim().toLowerCase().split(/\s+/).filter(Boolean)
    if (!terms.length || !schema) return []
    const out: SearchHit[] = []
    // every term must start a word somewhere ("pin" finds PIN, not housekeeping)
    const words = (x: string) => x.toLowerCase().split(/[^\p{L}\p{N}]+/u)
    const has = (...xs: (string | undefined)[]) => {
      const pool = xs.flatMap((x) => (x ? [...words(x), ...words(t(x))] : []))
      return terms.every((term) => pool.some((w) => w.startsWith(term)))
    }
    for (const m of schema.modules) {
      if (has(m.title, m.description)) out.push({ page: m.id, pageTitle: m.title, label: m.title, sub: m.description })
      for (const sec of m.sections)
        for (const s of sec.settings)
          if (has(s.label, s.hint, sec.title))
            out.push({ page: m.id, pageTitle: m.title, label: s.label, sub: sec.title, key: s.key })
    }
    for (const p of CUSTOM_PAGES)
      if (nav.some((n) => n.id === p.id) && has(p.title, p.description, p.keywords))
        out.push({ page: p.id, pageTitle: p.title, label: p.title, sub: p.description })
    return out.slice(0, 12)
  }, [q, schema, nav, t])

  const go = useCallback(
    (page: string, key?: string) => {
      if (dirty && !confirm(t("Leave without saving your changes?"))) return
      setDirty(false)
      navigate(`/settings/${page}${key ? `?focus=${key}` : ""}`)
    },
    [dirty, navigate, t],
  )

  if (error)
    return <p className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-600">{translate(error)}</p>
  if (!schema) return <p className="py-10 text-center text-sm text-zinc-400">{t("Loading…")}</p>
  if (!nav.length)
    return <p className="py-10 text-center text-sm text-zinc-500">{t("Your role has no settings to manage.")}</p>

  const current = nav.find((n) => n.id === section)
  if (!section || !current) return <Navigate to={`/settings/${nav[0].id}`} replace />

  const mod = schema.modules.find((m) => m.id === section)
  const focus = search.get("focus")

  return (
    // Full width of the shell - list and settings pages should use the desk.
    <div className="w-full lg:grid lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-8">
      {/* rail */}
      <aside className="mb-6 lg:mb-0">
        <div className="lg:sticky lg:top-20">
          <h1 className="mb-3 text-xl font-semibold tracking-tight">{t("Settings")}</h1>
          <div className="relative mb-4">
            <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
            <input
              ref={searchRef}
              value={q}
              onChange={(e) => {
                setQ(e.target.value)
                setSearchOpen(true)
              }}
              onFocus={() => setSearchOpen(true)}
              onBlur={() => setTimeout(() => setSearchOpen(false), 150)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && hits[0]) {
                  go(hits[0].page, hits[0].key)
                  setQ("")
                  searchRef.current?.blur()
                }
                if (e.key === "Escape") {
                  setQ("")
                  searchRef.current?.blur()
                }
              }}
              placeholder={t("Search settings")}
              aria-label={t("Search settings")}
              className="w-full rounded-lg border border-zinc-200 bg-white py-1.5 ps-9 pe-8 text-sm placeholder:text-zinc-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
            <kbd className="pointer-events-none absolute end-2 top-1/2 -translate-y-1/2 rounded border border-zinc-200 px-1.5 text-[10px] text-zinc-400">/</kbd>
            {searchOpen && q.trim() && (
              <div className="absolute inset-x-0 top-full z-40 mt-1 max-h-96 overflow-y-auto rounded-xl border border-zinc-200 bg-white p-1 shadow-lg lg:w-96">
                {hits.length === 0 ? (
                  <p className="px-3 py-3 text-sm text-zinc-400">{t("No setting matches.")}</p>
                ) : (
                  hits.map((h, i) => (
                    <button
                      key={`${h.page}-${h.key ?? i}`}
                      type="button"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => {
                        go(h.page, h.key)
                        setQ("")
                        searchRef.current?.blur()
                      }}
                      className="block w-full rounded-lg px-3 py-2 text-start hover:bg-zinc-50"
                    >
                      <span className="block text-sm font-medium text-zinc-800">{t(h.label)}</span>
                      <span className="block truncate text-xs text-zinc-500">
                        {t(h.pageTitle)}
                        {h.sub && h.sub !== h.pageTitle ? ` · ${t(h.sub)}` : ""}
                      </span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* phone / tablet: a picker instead of the rail */}
          <select
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm lg:hidden"
            value={section}
            onChange={(e) => go(e.target.value)}
            aria-label={t("Settings page")}
          >
            {GROUPS.map((g) => {
              const items = nav.filter((n) => n.group === g.id)
              return items.length ? (
                <optgroup key={g.id} label={t(g.label)}>
                  {items.map((n) => (
                    <option key={n.id} value={n.id}>{t(n.title)}</option>
                  ))}
                </optgroup>
              ) : null
            })}
          </select>

          <nav className="hidden space-y-5 lg:block" aria-label={t("Settings")}>
            {GROUPS.map((g) => {
              const items = nav.filter((n) => n.group === g.id)
              if (!items.length) return null
              return (
                <div key={g.id}>
                  <p className="mb-1 px-2.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">{t(g.label)}</p>
                  <ul className="space-y-0.5">
                    {items.map((n) => (
                      <li key={n.id}>
                        <button
                          type="button"
                          onClick={() => go(n.id)}
                          aria-current={n.id === section ? "page" : undefined}
                          className={cn(
                            "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-start text-sm",
                            n.id === section
                              ? "bg-brand-50 font-medium text-brand-800"
                              : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900",
                          )}
                        >
                          <n.icon className="size-4 shrink-0" aria-hidden />
                          <span className="flex-1 truncate">{t(n.title)}</span>
                          {n.off && <span className="text-[10px] font-medium uppercase text-zinc-400">{t("Off")}</span>}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
            {schema.is_it_admin && (
              <div>
                <p className="mb-1 px-2.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">{t("IT")}</p>
                <Link
                  to="/developers"
                  className="flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
                >
                  <Code2 className="size-4" aria-hidden />
                  <span className="flex-1">{t("Developers & API keys")}</span>
                  <ExternalLink className="size-3.5 text-zinc-400" aria-hidden />
                </Link>
              </div>
            )}
          </nav>
        </div>
      </aside>

      {/* page */}
      <div className="min-w-0">
        <PageHeader
          entry={current}
          module={mod}
          canToggle={schema.is_admin}
          busy={toggleBusy}
          onToggle={async (on) => {
            if (!mod) return
            if (!on && !confirm(t("Switch off {name} for this property?", { name: t(mod.title) }))) return
            setToggleBusy(true)
            try {
              await setModuleEnabled(mod.id, on)
              window.dispatchEvent(new Event("kamra:modules-changed"))
              load()
            } catch (e) {
              setError(serverError(e))
            } finally {
              setToggleBusy(false)
            }
          }}
        />
        {mod ? (
          <ModulePage
            module={mod}
            sources={sources}
            focusKey={focus}
            taxIdLabel={loc.tax_id_label}
            onDirtyChange={setDirty}
            onSaved={(values) =>
              setSchema((s) =>
                s && {
                  ...s,
                  modules: s.modules.map((m) => (m.id === mod.id ? { ...m, values } : m)),
                },
              )
            }
          >
            {mod.id === "front-desk" && <CheckInStepsCard property={property} />}
            {mod.id === "front-desk" && (
              <NightAuditScheduleCard
                key={["night_audit_auto", "night_audit_time", "night_audit_grace_minutes"]
                  .map((k) => String(mod.values[k])).join("|")}
                property={property}
              />
            )}
            {mod.id === "housekeeping" && <LaundryRatesCard property={property} />}
            {mod.id === "revenue" && <HurdleRatesCard property={property} />}
            {mod.id === "fnb" && <KitchenPrintersCard property={property} />}
            {mod.id === "fnb" && <SpeedCheckCard property={property} />}
          </ModulePage>
        ) : (
          <CustomPageBody
            id={section}
            schema={schema}
            property={property}
            onModulesChanged={load}
          />
        )}
      </div>
    </div>
  )
}

function PageHeader({
  entry, module, canToggle, busy, onToggle,
}: {
  entry: NavEntry
  module?: SettingsModule
  canToggle: boolean
  busy: boolean
  onToggle: (on: boolean) => void
}) {
  const { t } = useT()
  return (
    <header className="mb-6 border-b border-zinc-200 pb-5">
      <div className="flex flex-wrap items-start gap-x-4 gap-y-3">
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight text-zinc-900">
            <entry.icon className="size-5 text-brand-600" aria-hidden />
            {t(entry.title)}
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-zinc-500">{t(entry.description)}</p>
          {module && (
            <p className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-zinc-500">
              {t("Changed by")}
              {["Hotel Admin", ...module.editors.filter((r) => r !== "Hotel Admin")].map((r) => (
                <Badge key={r} tone="zinc">{t(r)}</Badge>
              ))}
            </p>
          )}
        </div>
        {module?.toggle && (
          <label className="flex items-center gap-3 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm">
            <span className={module.enabled ? "text-zinc-700" : "text-zinc-500"}>
              {module.enabled ? t("Module on") : t("Module off")}
            </span>
            <Switch
              on={module.enabled}
              label={t("{name} module", { name: t(module.title) })}
              disabled={!canToggle || busy}
              onToggle={() => onToggle(!module.enabled)}
            />
          </label>
        )}
      </div>
      {module?.toggle && !module.enabled && (
        <p className="mt-4 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-600">
          {t("This module is off, so its apps are hidden for everyone. Settings are kept for when you switch it back on.")}
        </p>
      )}
    </header>
  )
}

function CustomPageBody({
  id, schema, property, onModulesChanged,
}: {
  id: string
  schema: SettingsSchema
  property: string
  onModulesChanged: () => void
}) {
  switch (id) {
    case "staff":
      return <StaffPage />
    case "roles":
      // Roles are fixed in code; assignment lives on Staff & access.
      return <Navigate to="/settings/staff" replace />
    case "modules":
      return <ModulesPage modules={schema.modules} canToggle={schema.is_admin} onChanged={onModulesChanged} />
    case "payments":
      return <PaymentsSection property={property} />
    case "ai":
      return <AiSection property={property} />
    case "claude":
      return (
        <div className="space-y-4">
          <McpAccessPage />
          <AgentAccessCard />
        </div>
      )
    case "webhooks":
      return <WebhooksPage property={property} />
    case "verify":
      return <KamraVerifyCard />
    case "zatca":
      return <ZatcaCard property={property} />
    case "appearance":
      return <AppearanceCard />
    default:
      return null
  }
}
