import { useCallback, useEffect, useState } from "react"
import { call, getCurrentProperty } from "../lib/api"
import {
  createResource,
  listResource,
  serverError,
  updateResource,
} from "../lib/resource"
import { getTheme, setTheme, type Theme } from "../lib/theme"
import { getLang, setLang, type Lang } from "../lib/dir"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"

/** Settings hub - everything an owner/GM configures once and forgets:
 * property identity, GST, privacy, booking page, payments, agent access. */

type Doc = Record<string, unknown>

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

interface Spec {
  field: string
  label: string
  type?: "text" | "number" | "time" | "check" | "select" | "textarea" | "password"
  options?: string[]
  hint?: string
}

function Field(props: {
  spec: Spec
  value: unknown
  onChange: (v: unknown) => void
}) {
  const { spec, value, onChange } = props
  if (spec.type === "check")
    return (
      <label className="flex items-center gap-2 py-1 text-sm text-zinc-700">
        <input
          type="checkbox"
          className="size-4 accent-brand-600"
          checked={Boolean(Number(value ?? 0))}
          onChange={(e) => onChange(e.target.checked ? 1 : 0)}
        />
        {spec.label}
        {spec.hint && <span className="text-xs text-zinc-400">{spec.hint}</span>}
      </label>
    )
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-zinc-600">
        {spec.label}
      </span>
      {spec.type === "select" ? (
        <select
          className={inputCls}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        >
          {spec.options?.map((o) => (
            <option key={o} value={o}>
              {o || "-"}
            </option>
          ))}
        </select>
      ) : spec.type === "textarea" ? (
        <textarea
          className={`${inputCls} min-h-20`}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          className={inputCls}
          type={spec.type ?? "text"}
          placeholder={spec.type === "password" ? "unchanged" : undefined}
          value={
            spec.type === "password" ? String(value ?? "") : String(value ?? "")
          }
          onChange={(e) =>
            onChange(
              spec.type === "number"
                ? e.target.value === ""
                  ? null
                  : Number(e.target.value)
                : e.target.value,
            )
          }
        />
      )}
      {spec.hint && (
        <span className="mt-0.5 block text-xs text-zinc-400">{spec.hint}</span>
      )}
    </label>
  )
}

function SettingsCard(props: {
  title: string
  description?: string
  specs: Spec[]
  doc: Doc
  onSave: (changes: Doc) => Promise<void>
  columns?: number
}) {
  const [draft, setDraft] = useState<Doc>({})
  const [busy, setBusy] = useState(false)
  const [state, setState] = useState<"idle" | "saved" | string>("idle")

  const value = (f: string) => (f in draft ? draft[f] : props.doc[f])

  async function save() {
    setBusy(true)
    setState("idle")
    try {
      await props.onSave(draft)
      setDraft({})
      setState("saved")
    } catch (e) {
      setState(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{props.title}</CardTitle>
          {props.description && (
            <p className="mt-0.5 text-xs text-zinc-400">{props.description}</p>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div
          className={
            props.columns === 1 ? "space-y-3" : "grid gap-3 sm:grid-cols-2"
          }
        >
          {props.specs.map((s) => (
            <Field
              key={s.field}
              spec={s}
              value={value(s.field)}
              onChange={(v) => {
                setState("idle")
                setDraft((d) => ({ ...d, [s.field]: v }))
              }}
            />
          ))}
        </div>
        <div className="mt-4 flex items-center gap-2">
          <Button
            disabled={busy || Object.keys(draft).length === 0}
            onClick={save}
          >
            {busy ? "Saving…" : "Save"}
          </Button>
          {state === "saved" && (
            <span className="text-xs text-emerald-600">Saved</span>
          )}
          {state !== "idle" && state !== "saved" && (
            <span className="text-xs text-rose-600">{state}</span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

const PROPERTY_SPECS: Spec[] = [
  { field: "property_name", label: "Property name" },
  { field: "legal_name", label: "Legal name" },
  {
    field: "country",
    label: "Country",
    hint: "Selects the tax & invoicing pack. India today; more via the Marketplace.",
  },
  { field: "phone", label: "Phone" },
  { field: "email", label: "Email" },
  { field: "website", label: "Website" },
  { field: "gstin", label: "GSTIN" },
  { field: "address_line", label: "Address" },
  { field: "city", label: "City" },
  { field: "state", label: "State" },
  { field: "pincode", label: "PIN code" },
]

const STAY_TAX_SPECS: Spec[] = [
  { field: "checkin_time", label: "Check-in time", type: "time" },
  { field: "checkout_time", label: "Check-out time", type: "time" },
  {
    field: "gst_mode",
    label: "GST mode",
    type: "select",
    options: ["Slab", "Fixed"],
    hint: "Slab: rate switches at the threshold per night",
  },
  {
    field: "gst_slab_threshold",
    label: "Slab threshold (₹)",
    type: "number",
  },
  { field: "gst_rate_low", label: "GST % below threshold", type: "number" },
  { field: "gst_rate_high", label: "GST % above threshold", type: "number" },
  {
    field: "rates_include_tax",
    label: "Displayed rates include GST",
    type: "check",
  },
  {
    field: "id_retention",
    label: "Guest ID retention",
    type: "select",
    options: ["Store", "Verify & Discard"],
    hint: "Verify & Discard masks ID numbers to the last 4 digits at checkout",
  },
  {
    field: "require_cashier_pin",
    label: "Require cashier PIN on money actions",
    type: "check",
    hint: "Payments, invoices, allowances and settlements re-confirm who is acting with a personal PIN - agents are exempt (the action log covers them)",
  },
]

const BOOKING_SPECS: Spec[] = [
  {
    field: "booking_engine_enabled",
    label: "Public booking page (/book)",
    type: "check",
  },
  {
    field: "star_category",
    label: "Category",
    type: "select",
    options: ["", "1 Star", "2 Star", "3 Star", "4 Star", "5 Star", "Boutique", "Homestay"],
  },
  { field: "showcase_description", label: "Description", type: "textarea" },
  {
    field: "sell_message",
    label: "Sell message",
    type: "textarea",
    hint: "Shown to staff in the booking dialog and used by the AI agent as its upsell prompt",
  },
  { field: "property_amenities", label: "Amenities (one per line)", type: "textarea" },
  { field: "google_reviews_url", label: "Google reviews URL" },
  { field: "tripadvisor_url", label: "TripAdvisor URL" },
  { field: "logo_url", label: "Logo URL" },
  { field: "hero_image", label: "Hero image URL" },
]

const POLICY_SPECS: Spec[] = [
  {
    field: "free_cancel_days",
    label: "Free cancellation window (days before arrival)",
    type: "number",
    hint: "Cancellations earlier than this are always free",
  },
  {
    field: "cancellation_fee",
    label: "Late cancellation fee",
    type: "select",
    options: ["None", "First Night", "Full Stay"],
  },
  {
    field: "no_show_charge",
    label: "No-show charge",
    type: "select",
    options: ["None", "First Night", "Full Stay"],
    hint: "Posted automatically by the night audit",
  },
  {
    field: "deposit_pct",
    label: "Deposit expected at booking (%)",
    type: "number",
  },
]

const AI_SPECS: Spec[] = [
  { field: "enabled", label: "Enabled", type: "check" },
  {
    field: "base_url",
    label: "Provider base URL",
    hint: "any OpenAI-compatible endpoint: OpenAI, OpenRouter, Groq, Ollama…",
  },
  { field: "model", label: "Model" },
  { field: "api_key", label: "API key", type: "password" },
  {
    field: "extra_instructions",
    label: "Extra instructions",
    type: "textarea",
    hint: "property-specific guidance - upsell priorities, tone",
  },
]

const GATEWAY_SPECS: Spec[] = [
  { field: "enabled", label: "Enabled", type: "check" },
  {
    field: "test_mode",
    label: "Test mode",
    type: "check",
    hint: "generates fake payment links for demos",
  },
  {
    field: "gateway",
    label: "Gateway",
    type: "select",
    options: ["Razorpay"],
    hint: "more gateways via the Frappe payments app",
  },
  { field: "key_id", label: "Key ID" },
  { field: "key_secret", label: "Key secret", type: "password" },
  { field: "webhook_secret", label: "Webhook secret", type: "password" },
]

export default function Settings() {
  const property = getCurrentProperty()
  const [prop, setProp] = useState<Doc | null>(null)
  const [gateway, setGateway] = useState<Doc | null>(null)
  const [ai, setAi] = useState<Doc | null>(null)
  const [theme, setThemeState] = useState<Theme>(getTheme())
  const [lang, setLangState] = useState<Lang>(getLang())

  const load = useCallback(() => {
    call<Doc>("frappe.client.get", {
      doctype: "Property",
      name: property,
    }).then(setProp)
    listResource("Payment Gateway Settings", {
      fields: ["name", "gateway", "enabled", "test_mode", "key_id"],
      filters: [["property", "=", property]],
    }).then((rows) => setGateway(rows[0] ?? {}))
    listResource("AI Assistant Settings", {
      fields: ["name", "enabled", "base_url", "model", "extra_instructions"],
      filters: [["property", "=", property]],
    }).then((rows) => setAi(rows[0] ?? {}))
  }, [property])

  useEffect(load, [load])

  if (!prop || !gateway || !ai)
    return <p className="py-10 text-center text-zinc-400">Loading…</p>

  return (
    <div className="space-y-4">
      <SettingsCard
        title="Property"
        description="Identity and contact details - printed on invoices and the GRC."
        specs={PROPERTY_SPECS}
        doc={prop}
        onSave={async (changes) => {
          await updateResource("Property", property, changes)
          load()
        }}
      />
      <SettingsCard
        title="Stay, tax & privacy"
        description="Check-in/out times, GST slabs and how long guest IDs are kept."
        specs={STAY_TAX_SPECS}
        doc={prop}
        onSave={async (changes) => {
          await updateResource("Property", property, changes)
          load()
        }}
      />
      <SettingsCard
        title="Booking page"
        description="What guests see on the public booking engine."
        specs={BOOKING_SPECS}
        doc={prop}
        onSave={async (changes) => {
          await updateResource("Property", property, changes)
          load()
        }}
      />
      <SettingsCard
        title="Cancellation, no-show & deposit"
        description="The money rules quoted at booking and enforced by cancel and the night audit."
        specs={POLICY_SPECS}
        doc={prop}
        onSave={async (changes) => {
          await updateResource("Property", property, changes)
          load()
        }}
      />
      <SettingsCard
        title="Payments"
        description="Payment-link gateway for advances and folio settlement. Secrets are write-only."
        specs={GATEWAY_SPECS}
        doc={gateway}
        onSave={async (changes) => {
          // never send empty secrets - blank means "unchanged"
          const payload = Object.fromEntries(
            Object.entries(changes).filter(
              ([k, v]) =>
                !["key_secret", "webhook_secret"].includes(k) || v !== "",
            ),
          )
          if (gateway.name) {
            await updateResource(
              "Payment Gateway Settings",
              String(gateway.name),
              payload,
            )
          } else {
            await createResource("Payment Gateway Settings", {
              ...payload,
              property,
            })
          }
          load()
        }}
      />

      <SettingsCard
        title="AI assistant (bring your own key)"
        description="Optional in-app copilot for staff. Your key, your data - the model can only act through Kamra's governed tools, and every action is audit-logged."
        specs={AI_SPECS}
        doc={ai}
        onSave={async (changes) => {
          const payload = Object.fromEntries(
            Object.entries(changes).filter(
              ([k, v]) => k !== "api_key" || v !== "",
            ),
          )
          if (ai.name) {
            await updateResource("AI Assistant Settings", String(ai.name), payload)
          } else {
            await createResource("AI Assistant Settings", {
              ...payload,
              property,
            })
          }
          load()
        }}
      />

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Agent access (MCP)</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              Connect Claude (or any MCP client) to this property's governed
              tool layer. Every agent action lands in the Agent Action Log.
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-zinc-600">
            The MCP server ships with the app at{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">
              apps/kamra/mcp/kamra_mcp.py
            </code>
            . It authenticates as the scoped{" "}
            <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">
              agent@kamra.local
            </code>{" "}
            user (Kamra Agent role). Generate an API key &amp; secret - and see
            the full REST reference - on the{" "}
            <a href="/kamra/developers" className="font-medium text-brand-700 hover:underline">
              Developers
            </a>{" "}
            page.
          </p>
          <pre className="overflow-x-auto rounded-lg bg-zinc-100 p-3 text-xs leading-relaxed text-zinc-700">
            {`claude mcp add kamra \\
  -e KAMRA_URL=${window.location.origin} \\
  -e KAMRA_API_KEY=<api key> \\
  -e KAMRA_API_SECRET=<api secret> \\
  -e KAMRA_PROPERTY="${property}" \\
  -- python apps/kamra/mcp/kamra_mcp.py`}
          </pre>
          <p className="text-xs text-zinc-400">
            Tools include availability, quotes, bookings, check-in/out, folio
            posting (billing-rule routed), occupant register, rate changes
            (guardrail-bound), night audit and the owner briefing.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <span className="w-20 text-sm font-medium text-zinc-600">Theme</span>
            <select
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
              value={theme}
              onChange={(e) => {
                const t = e.target.value as Theme
                setTheme(t)
                setThemeState(t)
              }}
            >
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="system">System</option>
            </select>
            <span className="text-xs text-zinc-400">
              applies to this browser only
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="w-20 text-sm font-medium text-zinc-600">Language</span>
            <select
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
              value={lang}
              onChange={(e) => {
                const l = e.target.value as Lang
                setLang(l)
                setLangState(l)
              }}
            >
              <option value="en">English</option>
              <option value="ar">العربية (Arabic)</option>
            </select>
            <span className="text-xs text-zinc-400">
              Arabic switches the interface to right-to-left · this browser only
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
