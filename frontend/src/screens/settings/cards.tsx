import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { call } from "../../lib/api"
import {
  createResource,
  listResource,
  serverError,
  updateResource,
} from "../../lib/resource"
import { getTheme, setTheme, type Theme } from "../../lib/theme"
import { getLang, setLang, LANGS, type Lang } from "../../lib/dir"
import { useT } from "../../lib/i18n"
import { probeSocket } from "../../lib/realtime"
import { Button } from "../../components/ui/button"
import ImageField from "../../components/ImageField"
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card"
import { cur, moneyLocale, useLocale } from "../../lib/money"

/** Self-contained cards the settings hub (./SettingsHub) places on its
 * module and integration pages: payments, AI, ZATCA, Verify, rate cards. */

type Doc = Record<string, unknown>

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

interface Spec {
  field: string
  label: string
  type?: "text" | "number" | "time" | "check" | "select" | "textarea" | "password" | "image"
  options?: string[]
  hint?: string
}

function Field(props: {
  spec: Spec
  value: unknown
  onChange: (v: unknown) => void
}) {
  const { t } = useT()
  const { spec, value, onChange } = props
  if (spec.type === "image")
    return (
      <ImageField
        label={t(spec.label)}
        hint={spec.hint ? t(spec.hint) : ""}
        value={String(value ?? "")}
        onChange={onChange}
      />
    )
  if (spec.type === "check")
    return (
      <label className="flex items-center gap-2 py-1 text-sm text-zinc-700">
        <input
          type="checkbox"
          className="size-4 accent-brand-600"
          checked={Boolean(Number(value ?? 0))}
          onChange={(e) => onChange(e.target.checked ? 1 : 0)}
        />
        {t(spec.label)}
        {spec.hint && <span className="text-xs text-zinc-400">{t(spec.hint)}</span>}
      </label>
    )
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-zinc-600">
        {t(spec.label)}
      </span>
      {spec.type === "select" ? (
        <select
          className={inputCls}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        >
          {spec.options?.map((o) => (
            <option key={o} value={o}>
              {o ? t(o) : "-"}
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
          placeholder={spec.type === "password" ? t("unchanged") : undefined}
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
        <span className="mt-0.5 block text-xs text-zinc-400">{t(spec.hint)}</span>
      )}
    </label>
  )
}

export function SettingsCard(props: {
  title: string
  description?: string
  specs: Spec[]
  doc: Doc
  onSave: (changes: Doc) => Promise<void>
  columns?: number
}) {
  const { t } = useT()
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
          <CardTitle>{t(props.title)}</CardTitle>
          {props.description && (
            <p className="mt-0.5 text-xs text-zinc-400">{t(props.description)}</p>
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
            {busy ? t("Saving…") : t("Save")}
          </Button>
          {state === "saved" && (
            <span className="text-xs text-emerald-600">{t("Saved")}</span>
          )}
          {state !== "idle" && state !== "saved" && (
            <span className="text-xs text-rose-600">{state}</span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export const TIMEZONES = [
  "Asia/Aden",
  "Asia/Riyadh",
  "Asia/Dubai",
  "Asia/Muscat",
  "Asia/Kolkata",
  "Asia/Jakarta",
  "Asia/Bangkok",
  "Asia/Singapore",
  "Europe/London",
  "Europe/Paris",
  "Africa/Cairo",
  "Africa/Nairobi",
  "America/New_York",
  "America/Los_Angeles",
  "UTC",
]

const ZATCA_SPECS: Spec[] = [
  { field: "enabled", label: "Generate e-invoices", type: "check",
    hint: "QR code, UBL XML and hash chain on every invoice, credit note and paid outlet bill." },
  { field: "seller_name", label: "Seller name (as registered)" },
  { field: "vat_number", label: "VAT registration number", hint: "15 digits, starts and ends with 3." },
  { field: "cr_number", label: "Commercial Registration (CRN)" },
  { field: "building_number", label: "Building number", hint: "4 digits" },
  { field: "street_name", label: "Street" },
  { field: "district", label: "District" },
  { field: "city_name", label: "City" },
  { field: "postal_code", label: "Postal code", hint: "5 digits" },
  { field: "additional_number", label: "Additional number" },
  { field: "environment", label: "Environment (Phase 2)", type: "select",
    options: ["Sandbox", "Simulation", "Production"] },
  { field: "egs_serial", label: "EGS serial (Phase 2)", hint: "1-Kamra|2-PMS|3-<unit serial>" },
]

/** Saudi e-invoicing (ZATCA / FATOORA): seller details the XML needs, what
 *  is still missing, and how far the invoice chain has run. */
export function ZatcaCard({ property }: { property: string }) {
  const { t } = useT()
  const [info, setInfo] = useState<{
    name: string
    missing: string[]
    issued: number
    last_icv: number
    onboarding_status: string
  } | null>(null)
  const [doc, setDoc] = useState<Doc | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(() => {
    call<NonNullable<typeof info>>("kamra.api.zatca_settings", { property })
      .then(async (i) => {
        setInfo(i)
        const rows = await listResource("ZATCA Settings", {
          fields: ["name", ...ZATCA_SPECS.map((s) => s.field)],
          filters: [["name", "=", i.name]],
        })
        setDoc(rows[0] ?? {})
      })
      .catch((e) => setError(serverError(e)))
  }, [property])
  useEffect(load, [load])
  if (error) return <p className="text-sm text-rose-600">{error}</p>
  if (!info || !doc) return null
  return (
    <div className="space-y-2">
      <div
        className={
          "rounded-lg border px-4 py-3 text-sm " +
          (info.missing.length
            ? "border-amber-200 bg-amber-50 text-amber-800"
            : "border-emerald-200 bg-emerald-50 text-emerald-800")
        }
      >
        {info.missing.length
          ? t("ZATCA: still needed for valid e-invoices - {fields}.", {
              fields: info.missing.join(", "),
            })
          : t("ZATCA Phase 1 ready - QR and XML on every invoice.")}{" "}
        {t("{n} documents issued · last ICV {icv} · Phase 2: {status}.", {
          n: info.issued,
          icv: info.last_icv,
          status: info.onboarding_status,
        })}
      </div>
      <SettingsCard
        title="ZATCA e-invoicing"
        description="Saudi Arabia (FATOORA). Seller details printed in every invoice XML."
        specs={ZATCA_SPECS}
        doc={doc}
        onSave={async (changes) => {
          await updateResource("ZATCA Settings", info.name, changes)
          load()
        }}
      />
    </div>
  )
}

/** The gateways on offer come from the property's country pack. */
function gatewaySpecs(gateways: string[]): Spec[] {
  return [
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
      options: gateways,
      hint: "money goes straight to this property's own gateway account",
    },
    {
      field: "key_id",
      label: "Key ID / App ID",
      hint: "Razorpay: Account & Settings → API Keys. Cashfree: Developers → API Keys (App ID)",
    },
    { field: "key_secret", label: "Key secret / Secret key", type: "password" },
    {
      field: "webhook_secret",
      label: "Webhook secret",
      type: "password",
      hint: "Razorpay only: set the same secret on the Razorpay webhook. Cashfree signs with the secret key",
    },
  ]
}

type GatewayInfo = {
  gateway: string
  webhook_url: string
  signup_url: string
  needs_webhook: boolean
}

/** Setup help under the Payments card: where the gateway should send
 *  payment events, and a way to open an account if the property has none. */
function GatewayHelp({ property, gateway, hasKeys }: {
  property: string
  gateway: string
  hasKeys: boolean
}) {
  const { t } = useT()
  const [info, setInfo] = useState<GatewayInfo | null>(null)
  useEffect(() => {
    call<GatewayInfo>("kamra.payments.gateway_info", { property, gateway })
      .then(setInfo).catch(() => setInfo(null))
  }, [property, gateway])
  if (!info) return null
  return (
    <div className="-mt-2 space-y-2 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-600">
      {!hasKeys && (
        <p>
          {t("No {gateway} account yet?", { gateway: info.gateway })}{" "}
          <a className="font-medium text-brand-700 underline" href={info.signup_url}
             target="_blank" rel="noopener">{t("Create one free")}</a>
          {" "}{t("and take UPI, cards and netbanking for advances and bills.")}
        </p>
      )}
      {info.needs_webhook ? (
        <p>
          {t("In Razorpay, add a webhook for the payment_link.paid event pointing to")}{" "}
          <code className="select-all break-all rounded bg-white px-1 py-0.5 text-xs">{info.webhook_url}</code>
        </p>
      ) : (
        <p>
          {t("Nothing to set up in Cashfree: every link reports back to")}{" "}
          <code className="select-all break-all rounded bg-white px-1 py-0.5 text-xs">{info.webhook_url}</code>
          . {t("Guests need a mobile number on their profile to receive a Cashfree link.")}
        </p>
      )}
    </div>
  )
}

/** Kamra Verify (GSTIN lookup, reading a guest's ID) runs on the Kamra
 *  Connect hub and is charged to its wallet - this links the install. */
export function KamraVerifyCard() {
  const { t } = useT()
  const [linked, setLinked] = useState<boolean | null>(null)
  const [key, setKey] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    call<{ linked: boolean }>("kamra.connect.client.status")
      .then((s) => setLinked(s.linked)).catch(() => setLinked(false))
  }, [])
  async function run(method: "link" | "unlink") {
    setBusy(true); setErr(null)
    try {
      const s = await call<{ linked: boolean }>(`kamra.connect.client.${method}`,
        method === "link" ? { connect_key: key } : {})
      setLinked(s.linked); setKey("")
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t("Kamra Verify")}</CardTitle>
          <p className="mt-1 text-sm text-zinc-500">
            {t("Check a company's GSTIN and read a guest's Aadhaar, passport or licence into the profile. Charged per check to your Kamra Connect wallet.")}
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {linked ? (
          <div className="flex items-center gap-3">
            <span className="text-emerald-700">{t("Linked to Kamra Connect.")}</span>
            <Button variant="ghost" disabled={busy} onClick={() => run("unlink")}>{t("Unlink")}</Button>
          </div>
        ) : (
          <div className="flex gap-2">
            <input className={inputCls} type="password" value={key} placeholder={t("Connect key")}
                   onChange={(e) => setKey(e.target.value)} />
            <Button disabled={busy || !key.trim()} onClick={() => run("link")}>{t("Link")}</Button>
          </div>
        )}
        {err && <p className="text-rose-600">{err}</p>}
      </CardContent>
    </Card>
  )
}

type AiPreset = {
  id: string
  label: string
  base_url: string
  model: string
  hint: string
  processor_note?: string
}

/** Which preset a saved base URL belongs to. The provider isn't stored -
 *  only the URL is - so on load the dropdown is derived from it rather than
 *  defaulting to OpenAI (which then showed the wrong provider). */
function presetForBaseUrl(presets: AiPreset[], baseUrl: string): string | null {
  const norm = (u: string) => u.trim().replace(/\/+$/, "").toLowerCase()
  const url = norm(baseUrl || "")
  if (!presets.length) return null
  const has = (id: string) => presets.some((p) => p.id === id)
  if (!url) return has("openai") ? "openai" : presets[0].id
  const exact = presets.find((p) => p.base_url && norm(p.base_url) === url)
  if (exact) return exact.id
  if (url.includes(".openai.azure.com") && has("azure")) return "azure"
  if (url.includes(":11434") && has("ollama")) return "ollama"
  if (has("custom")) return "custom"
  return presets[0].id
}

function AiAssistantCard({
  property,
  doc,
  onSaved,
}: {
  property: string
  doc: Doc
  onSaved: () => void
}) {
  const { t } = useT()
  const [presets, setPresets] = useState<AiPreset[]>([])
  const [provider, setProvider] = useState("openai")
  const [enabled, setEnabled] = useState(Boolean(Number(doc.enabled ?? 0)))
  const [baseUrl, setBaseUrl] = useState(String(doc.base_url ?? "https://api.openai.com/v1"))
  const [model, setModel] = useState(String(doc.model ?? "gpt-4o-mini"))
  const [apiKey, setApiKey] = useState("")
  const [extra, setExtra] = useState(String(doc.extra_instructions ?? ""))
  const [redactContact, setRedactContact] = useState(
    doc.redact_guest_contact_details == null
      ? true
      : Boolean(Number(doc.redact_guest_contact_details)),
  )
  const [busy, setBusy] = useState(false)
  const [testing, setTesting] = useState(false)
  const [state, setState] = useState<"idle" | "saved" | string>("idle")
  const [testMsg, setTestMsg] = useState<string | null>(null)

  useEffect(() => {
    call<{ presets: AiPreset[] }>("kamra.assistant.provider_presets")
      .then((r) => setPresets(r.presets || []))
      .catch(() =>
        setPresets([
          {
            id: "openai",
            label: "OpenAI",
            base_url: "https://api.openai.com/v1",
            model: "gpt-4o-mini",
            hint: "Paste an sk-… key",
          },
        ]),
      )
  }, [])

  useEffect(() => {
    setEnabled(Boolean(Number(doc.enabled ?? 0)))
    setBaseUrl(String(doc.base_url ?? "https://api.openai.com/v1"))
    setModel(String(doc.model ?? "gpt-4o-mini"))
    setExtra(String(doc.extra_instructions ?? ""))
    setRedactContact(
      doc.redact_guest_contact_details == null
        ? true
        : Boolean(Number(doc.redact_guest_contact_details)),
    )
    setApiKey("")
  }, [doc])

  // initialise the provider from what was saved, once presets are known
  const savedBaseUrl = String(doc.base_url ?? "")
  useEffect(() => {
    const id = presetForBaseUrl(presets, savedBaseUrl || "https://api.openai.com/v1")
    if (id) setProvider(id)
  }, [presets, savedBaseUrl])

  const activePreset = presets.find((p) => p.id === provider)
  const activeHint = activePreset?.hint || "Any OpenAI-compatible Chat Completions host"
  const processorNote =
    activePreset?.processor_note ||
    (baseUrl.includes("11434") || baseUrl.includes("127.0.0.1")
      ? "Local endpoint: chat may stay on your infrastructure when Ollama runs on this server or LAN."
      : "Your configured endpoint processes chat messages and tool results under that provider's terms and region.")

  function applyPreset(id: string) {
    setProvider(id)
    const p = presets.find((x) => x.id === id)
    if (!p) return
    if (p.base_url) setBaseUrl(p.base_url)
    if (p.model) setModel(p.model)
    setState("idle")
    setTestMsg(null)
  }

  async function save() {
    setBusy(true)
    setState("idle")
    try {
      const payload: Doc = {
        enabled: enabled ? 1 : 0,
        base_url: baseUrl,
        model,
        extra_instructions: extra,
        redact_guest_contact_details: redactContact ? 1 : 0,
      }
      if (apiKey) payload.api_key = apiKey
      if (doc.name) {
        await updateResource("AI Assistant Settings", String(doc.name), payload)
      } else {
        await createResource("AI Assistant Settings", { ...payload, property })
      }
      setApiKey("")
      setState("saved")
      onSaved()
    } catch (e) {
      setState(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function test() {
    setTesting(true)
    setTestMsg(null)
    try {
      const r = await call<{
        ok: boolean
        error?: string
        reply?: string
        latency_ms?: number
        status?: number
      }>("kamra.assistant.test_connection", {
        property,
        base_url: baseUrl,
        model,
        api_key: apiKey || undefined,
      })
      if (r.ok) {
        setTestMsg(
          t("Connected ({ms} ms) — {reply}", {
            ms: r.latency_ms ?? "?",
            reply: (r.reply || "ok").slice(0, 80),
          }),
        )
      } else {
        setTestMsg(
          t("Failed{status}: {err}", {
            status: r.status ? ` (${r.status})` : "",
            err: r.error || "unknown error",
          }),
        )
      }
    } catch (e) {
      setTestMsg(serverError(e))
    } finally {
      setTesting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t("AI assistant (bring your own key)")}</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            {t(
              "Kamra Agent for staff. Pick a provider, paste the key, Test. Claude Desktop is MCP (Kamra Agent → Connect your AI) — not an Anthropic key in this form.",
            )}
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="flex items-center gap-2 py-1 text-sm text-zinc-700">
          <input
            type="checkbox"
            className="size-4 accent-brand-600"
            checked={enabled}
            onChange={(e) => {
              setEnabled(e.target.checked)
              setState("idle")
            }}
          />
          {t("Enabled")}
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-zinc-600">
            {t("Provider")}
          </span>
          <select
            className={inputCls}
            value={provider}
            onChange={(e) => applyPreset(e.target.value)}
          >
            {presets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
          <span className="mt-0.5 block text-xs text-zinc-400">{activeHint}</span>
          <span className="mt-2 block rounded-lg border border-amber-100 bg-amber-50/80 px-3 py-2 text-xs text-amber-950">
            {processorNote}
          </span>
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-zinc-600">
              {t("Base URL")}
            </span>
            <input
              className={inputCls}
              value={baseUrl}
              onChange={(e) => {
                setBaseUrl(e.target.value)
                setState("idle")
              }}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-zinc-600">
              {t("Model")}
            </span>
            <input
              className={inputCls}
              value={model}
              onChange={(e) => {
                setModel(e.target.value)
                setState("idle")
              }}
            />
          </label>
        </div>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-zinc-600">
            {t("API key")}
          </span>
          <input
            className={inputCls}
            type="password"
            placeholder={t("unchanged")}
            value={apiKey}
            onChange={(e) => {
              setApiKey(e.target.value)
              setState("idle")
            }}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-zinc-600">
            {t("Extra instructions")}
          </span>
          <textarea
            className={`${inputCls} min-h-20`}
            value={extra}
            onChange={(e) => {
              setExtra(e.target.value)
              setState("idle")
            }}
          />
          <span className="mt-0.5 block text-xs text-zinc-400">
            {t("property-specific guidance - upsell priorities, tone")}
          </span>
        </label>
        <label className="flex items-start gap-2 py-1 text-sm text-zinc-700">
          <input
            type="checkbox"
            className="mt-0.5 size-4 accent-brand-600"
            checked={redactContact}
            onChange={(e) => {
              setRedactContact(e.target.checked)
              setState("idle")
            }}
          />
          <span>
            {t("Never send guest contact details to the AI provider")}
            <span className="mt-0.5 block text-xs font-normal text-zinc-400">
              {t(
                "When off, phone and ID numbers in tool results are shortened to the last four digits before they leave Kamra.",
              )}
            </span>
          </span>
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={busy} onClick={save}>
            {busy ? t("Saving…") : t("Save")}
          </Button>
          <Button variant="outline" disabled={testing} onClick={test}>
            {testing ? t("Testing…") : t("Test connection")}
          </Button>
          {state === "saved" && (
            <span className="text-xs text-emerald-600">{t("Saved")}</span>
          )}
          {state !== "idle" && state !== "saved" && (
            <span className="text-xs text-rose-600">{state}</span>
          )}
        </div>
        {testMsg && (
          <p
            className={
              testMsg.startsWith("Connected") || testMsg.includes("Connected")
                ? "text-sm text-emerald-700"
                : "text-sm text-rose-600"
            }
          >
            {testMsg}
          </p>
        )}
        <p className="text-xs text-zinc-400">
          {t("Want Claude the app?")}{" "}
          <a href="/kamra/assistant" className="font-medium text-brand-700 hover:underline">
            {t("Kamra Agent → Connect your AI")}
          </a>
          . {t("Want Claude the model in this chat? Use the OpenRouter preset.")}
        </p>
      </CardContent>
    </Card>
  )
}

/** Payment-link gateway for this property - which gateways are on offer
 *  comes from the country pack. Secrets are write-only. */
export function PaymentsSection({ property }: { property: string }) {
  const { t } = useT()
  const loc = useLocale()
  const [gateway, setGateway] = useState<Doc | null>(null)
  const load = useCallback(() => {
    listResource("Payment Gateway Settings", {
      fields: ["name", "gateway", "enabled", "test_mode", "key_id"],
      filters: [["property", "=", property]],
    }).then((rows) => setGateway(rows[0] ?? {}))
  }, [property])
  useEffect(load, [load])
  const gateways = loc.integrations.payment_gateways
  if (!gateways.length)
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("Payments")}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-zinc-500">
          {t("Online payment links are not available for this country yet. Take payments at the desk.")}
        </CardContent>
      </Card>
    )
  if (!gateway) return null
  return (
    <div className="space-y-4">
      <SettingsCard
        title="Payment gateway"
        description="Payment links for advances and folio settlement. Money goes straight to this property's own account. Secrets are write-only."
        specs={gatewaySpecs(gateways)}
        doc={{ ...gateway, gateway: gateway.gateway || gateways[0] }}
        onSave={async (changes) => {
          // never send empty secrets - blank means "unchanged"
          const payload = Object.fromEntries(
            Object.entries(changes).filter(
              ([k, v]) =>
                !["key_secret", "webhook_secret"].includes(k) || v !== "",
            ),
          )
          if (gateway.name) {
            await updateResource("Payment Gateway Settings", String(gateway.name), payload)
          } else {
            await createResource("Payment Gateway Settings", {
              gateway: gateways[0],
              ...payload,
              property,
            })
          }
          load()
        }}
      />
      <GatewayHelp
        property={property}
        gateway={gateways.includes(String(gateway.gateway)) ? String(gateway.gateway) : gateways[0]}
        hasKeys={!!gateway.key_id}
      />
    </div>
  )
}

export function AiSection({ property }: { property: string }) {
  const [ai, setAi] = useState<Doc | null>(null)
  const load = useCallback(() => {
    listResource("AI Assistant Settings", {
      fields: ["name", "enabled", "base_url", "model", "extra_instructions",
               "redact_guest_contact_details"],
      filters: [["property", "=", property]],
    }).then((rows) => setAi(rows[0] ?? {}))
  }, [property])
  useEffect(load, [load])
  if (!ai) return null
  return <AiAssistantCard property={property} doc={ai} onSaved={load} />
}

export function AgentAccessCard() {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Claude & MCP</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            Connect Claude to this property's governed tools. It acts as the
            signed-in person, within their role, and every action lands in the
            Activity log.
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-zinc-600">
          Staff open{" "}
          <Link to="/assistant" className="font-medium text-brand-700 hover:underline">
            Kamra Agent → Connect your AI
          </Link>{" "}
          and click <strong>Connect Claude</strong>. Claude opens with this
          hotel&apos;s MCP URL filled in; they confirm and sign in as themselves.
          No API keys on a laptop.
        </p>
        <pre className="overflow-x-auto rounded-lg bg-zinc-100 p-3 text-xs leading-relaxed text-zinc-700">
          {`claude mcp add --transport http kamra ${window.location.origin}/mcp`}
        </pre>
        <p className="text-xs text-zinc-400">
          Service keys for unattended agents are issued by IT under Developers.
        </p>
      </CardContent>
    </Card>
  )
}

export function AppearanceCard() {
  const { t } = useT()
  const [theme, setThemeState] = useState<Theme>(getTheme())
  const [lang, setLangState] = useState<Lang>(getLang())
  const selectCls =
    "rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t("Appearance")}</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">{t("applies to this browser only")}</p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <label className="flex flex-wrap items-center gap-3">
          <span className="w-24 text-sm font-medium text-zinc-600">{t("Theme")}</span>
          <select
            className={selectCls}
            value={theme}
            onChange={(e) => {
              const next = e.target.value as Theme
              setTheme(next)
              setThemeState(next)
            }}
          >
            <option value="light">{t("Light")}</option>
            <option value="dark">{t("Dark")}</option>
            <option value="system">{t("System")}</option>
          </select>
        </label>
        <label className="flex flex-wrap items-center gap-3">
          <span className="w-24 text-sm font-medium text-zinc-600">{t("Language")}</span>
          <select
            className={selectCls}
            value={lang}
            onChange={(e) => {
              const l = e.target.value as Lang
              setLang(l)
              setLangState(l)
            }}
          >
            {LANGS.map((l) => (
              <option key={l.code} value={l.code}>
                {l.nativeLabel}
                {l.code !== "en" ? ` (${l.englishLabel})` : ""}
              </option>
            ))}
          </select>
          <span className="text-xs text-zinc-400">
            {t("Arabic switches the interface to right-to-left")}
          </span>
        </label>
      </CardContent>
    </Card>
  )
}

interface LaundryRate {
  name: string
  item_name: string
  service_type: string
  rate: number
  express_rate: number
}

/** The laundry rate card - what the floor team quotes and bills from.
 * Express defaults to 1.5x when its column is left blank. */
export function LaundryRatesCard({ property }: { property: string }) {
  const [rates, setRates] = useState<LaundryRate[]>([])
  const [form, setForm] = useState<{ name?: string; item: string; service: string; rate: string; express: string } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [importMsg, setImportMsg] = useState<string | null>(null)

  const load = useCallback(() => {
    call<LaundryRate[]>("kamra.laundry.laundry_rates", { property }).then(setRates).catch(() => {})
  }, [property])
  useEffect(load, [load])

  function exportCsv() {
    const lines = ["item,service,rate,express rate",
      ...rates.map((r) =>
        `"${r.item_name.replace(/"/g, '""')}",${r.service_type},${r.rate},${r.express_rate}`)]
    const blob = new Blob([lines.join("\n") + "\n"], { type: "text/csv" })
    const a = document.createElement("a")
    a.href = URL.createObjectURL(blob)
    a.download = "laundry-rates.csv"
    a.click()
    URL.revokeObjectURL(a.href)
  }

  async function importCsv(file: File) {
    setErr(null)
    setImportMsg(null)
    try {
      const res = await call<{ created: number; updated: number; issues: { row: number; item: string; error: string }[] }>(
        "kamra.laundry.import_laundry_rates",
        { property, csv_text: await file.text() },
      )
      setImportMsg(
        `${res.created} added, ${res.updated} updated` +
        (res.issues.length ? ` — ${res.issues.length} row(s) skipped: ` +
          res.issues.slice(0, 3).map((i) => `row ${i.row} (${i.error})`).join("; ") : ""))
      load()
    } catch (e) {
      setErr(serverError(e))
    }
  }

  async function save() {
    if (!form) return
    setErr(null)
    try {
      await call("kamra.laundry.save_laundry_rate", {
        property, name: form.name || null, item_name: form.item,
        service_type: form.service, rate: form.rate,
        express_rate: form.express || null,
      })
      setForm(null)
      load()
    } catch (e) {
      setErr(serverError(e))
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Laundry rate card</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            Per-item prices the housekeeping app quotes and bills from.
            A blank express price uses the express multiplier above.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" disabled={rates.length === 0} onClick={exportCsv}>
            Export CSV
          </Button>
          <label className="inline-flex cursor-pointer items-center rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-800 transition-colors hover:bg-zinc-100">
            Import CSV
            <input type="file" accept=".csv,text/csv" className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) importCsv(f)
                e.target.value = ""
              }} />
          </label>
          <Button variant="outline" onClick={() => setForm({ item: "", service: "Wash & Iron", rate: "", express: "" })}>
            Add rate
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {err && <p className="mb-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}
        {importMsg && <p className="mb-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{importMsg}</p>}
        {form && (
          <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl bg-zinc-50 p-2">
            <input className="w-36 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm" placeholder="Item (Shirt…)"
              value={form.item} onChange={(e) => setForm({ ...form, item: e.target.value })} autoFocus />
            <select className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
              value={form.service} onChange={(e) => setForm({ ...form, service: e.target.value })}>
              {["Wash & Iron", "Dry Clean", "Iron Only"].map((s) => <option key={s}>{s}</option>)}
            </select>
            <input className="w-24 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm" placeholder={`Rate ${cur()}`} inputMode="numeric"
              value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value.replace(/[^\d.]/g, "") })} />
            <input className="w-28 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm" placeholder={`Express ${cur()} (opt)`} inputMode="numeric"
              value={form.express} onChange={(e) => setForm({ ...form, express: e.target.value.replace(/[^\d.]/g, "") })} />
            <Button disabled={!form.item.trim() || !form.rate} onClick={save}>Save</Button>
            <Button variant="ghost" onClick={() => setForm(null)}>Cancel</Button>
          </div>
        )}
        {rates.length === 0 ? (
          <p className="py-3 text-sm text-zinc-400">No rates yet — add the first item.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-zinc-400">
                <th className="py-1.5">Item</th><th>Service</th>
                <th className="text-right">Rate</th><th className="text-right">Express</th><th />
              </tr>
            </thead>
            <tbody>
              {rates.map((r) => (
                <tr key={r.name} className="border-t border-zinc-100">
                  <td className="py-1.5 font-medium">{r.item_name}</td>
                  <td className="text-zinc-500">{r.service_type}</td>
                  <td className="text-right tabular-nums">{cur()}{r.rate.toLocaleString(moneyLocale())}</td>
                  <td className="text-right tabular-nums text-zinc-500">{cur()}{r.express_rate.toLocaleString(moneyLocale())}</td>
                  <td className="text-right">
                    <button className="text-xs font-medium text-brand-700 hover:underline"
                      onClick={() => setForm({ name: r.name, item: r.item_name, service: r.service_type, rate: String(r.rate), express: "" })}>
                      Edit
                    </button>
                    <button className="ml-2 text-xs text-zinc-400 hover:text-rose-600"
                      onClick={async () => { await call("kamra.laundry.delete_laundry_rate", { name: r.name }); load() }}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  )
}

interface HurdleTier {
  name: string
  room_type: string | null
  room_type_name?: string | null
  occupancy_from: number
  premium_pct: number
  min_rate: number
}

/** Demand tiers: at each occupancy threshold, quotes carry a premium and
 * manual rates can't undercut the hurdle (the minimum sell rate). */
export function HurdleRatesCard({ property }: { property: string }) {
  const [tiers, setTiers] = useState<HurdleTier[]>([])
  const [form, setForm] = useState<{
    name?: string
    from: string
    premium: string
    min: string
    room_type: string
  } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  // a tier can target one room type; blank = every room type
  const [roomTypes, setRoomTypes] = useState<{ name: string; room_type_name: string }[]>([])

  const load = useCallback(() => {
    call<HurdleTier[]>("kamra.api.hurdle_rates", { property }).then(setTiers).catch(() => {})
  }, [property])
  useEffect(load, [load])
  useEffect(() => {
    listResource("Room Type", {
      fields: ["name", "room_type_name"],
      filters: [
        ["property", "=", property],
        ["disabled", "=", 0],
      ],
      orderBy: "base_price asc",
      limit: 200,
    })
      .then((rows) => setRoomTypes(rows as { name: string; room_type_name: string }[]))
      .catch(() => setRoomTypes([]))
  }, [property])

  async function save() {
    if (!form) return
    setErr(null)
    try {
      await call("kamra.api.save_hurdle_rate", {
        property, name: form.name || null, occupancy_from: form.from,
        premium_pct: form.premium || 0, min_rate: form.min || 0,
        room_type: form.room_type || null,
      })
      setForm(null)
      load()
    } catch (e) {
      setErr(serverError(e))
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Demand pricing (hurdle rates)</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            When forecast occupancy for a date crosses a threshold, quotes
            carry the premium automatically and no rate may sell below the
            hurdle. A room-type tier beats the all-types tier. Guardrails
            (floor and ceiling) only bound rates set through set_room_rate -
            Kamra Agent, MCP or the API - not these premiums, staff seasons
            or quotes.
          </p>
        </div>
        <Button variant="outline" className="shrink-0" onClick={() => setForm({ from: "", premium: "", min: "", room_type: "" })}>
          Add tier
        </Button>
      </CardHeader>
      <CardContent>
        {err && <p className="mb-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}
        {form && (
          <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl bg-zinc-50 p-2">
            <label className="flex items-center gap-1 text-sm text-zinc-600">
              Occupancy ≥
              <input className="w-16 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm" placeholder="80" inputMode="numeric"
                value={form.from} onChange={(e) => setForm({ ...form, from: e.target.value.replace(/[^\d.]/g, "") })} autoFocus />
              %
            </label>
            <label className="flex items-center gap-1 text-sm text-zinc-600">
              Premium +
              <input className="w-16 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm" placeholder="15" inputMode="numeric"
                value={form.premium} onChange={(e) => setForm({ ...form, premium: e.target.value.replace(/[^\d.]/g, "") })} />
              %
            </label>
            <label className="flex items-center gap-1 text-sm text-zinc-600">
              Hurdle {cur()}
              <input className="w-24 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm" placeholder="min rate" inputMode="numeric"
                value={form.min} onChange={(e) => setForm({ ...form, min: e.target.value.replace(/[^\d.]/g, "") })} />
            </label>
            <label className="flex items-center gap-1 text-sm text-zinc-600">
              For
              <select
                aria-label="Room type"
                className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                value={form.room_type}
                onChange={(e) => setForm({ ...form, room_type: e.target.value })}
              >
                <option value="">All room types</option>
                {roomTypes.map((rt) => (
                  <option key={rt.name} value={rt.name}>{rt.room_type_name}</option>
                ))}
                {form.room_type && !roomTypes.some((rt) => rt.name === form.room_type) && (
                  <option value={form.room_type}>{form.room_type}</option>
                )}
              </select>
            </label>
            <Button disabled={!form.from} onClick={save}>Save</Button>
            <Button variant="ghost" onClick={() => setForm(null)}>Cancel</Button>
          </div>
        )}
        {tiers.length === 0 ? (
          <p className="py-3 text-sm text-zinc-400">
            No tiers yet — e.g. `at 80% occupancy, +15% premium, minimum ${cur()}6,000`.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-zinc-400">
                <th className="py-1.5">When occupancy ≥</th>
                <th>Room type</th>
                <th className="text-right">Premium</th>
                <th className="text-right">Hurdle (min rate)</th><th />
              </tr>
            </thead>
            <tbody>
              {tiers.map((t) => (
                <tr key={t.name} className="border-t border-zinc-100">
                  <td className="py-1.5 font-medium">{t.occupancy_from}%</td>
                  <td className="text-zinc-600">{t.room_type ? (t.room_type_name || t.room_type) : <span className="text-zinc-400">All</span>}</td>
                  <td className="text-right tabular-nums">{t.premium_pct ? `+${t.premium_pct}%` : "—"}</td>
                  <td className="text-right tabular-nums">{t.min_rate ? `${cur()}${t.min_rate.toLocaleString(moneyLocale())}` : "—"}</td>
                  <td className="text-right">
                    <button className="text-xs font-medium text-brand-700 hover:underline"
                      onClick={() => setForm({ name: t.name, from: String(t.occupancy_from), premium: String(t.premium_pct || ""), min: String(t.min_rate || ""), room_type: t.room_type || "" })}>
                      Edit
                    </button>
                    <button className="ml-2 text-xs text-zinc-400 hover:text-rose-600"
                      onClick={async () => { await call("kamra.api.delete_hurdle_rate", { name: t.name }); load() }}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  )
}

interface SpeedResult {
  rtt: number
  server: { database_ms?: number; open_bills_ms?: number; kitchen_display_ms?: number }
  setup: { background_workers: number | null; developer_mode: boolean; socketio_configured: boolean }
  socketMs: number | null
}

/** "Why is the POS slow here?" - one button that separates our code from
 *  the network and the hosting. Read-only. */
export function SpeedCheckCard({ property }: { property: string }) {
  const { t } = useT()
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<SpeedResult | null>(null)
  const [err, setErr] = useState<string | null>(null)

  async function run() {
    setBusy(true); setErr(null); setRes(null)
    try {
      type R = { server: SpeedResult["server"]; setup: SpeedResult["setup"] }
      const rtts: number[] = []
      let last: R | null = null
      for (let i = 0; i < 5; i++) {
        const t0 = performance.now()
        last = await call<R>("kamra.pos.speed_check", { property })
        rtts.push(performance.now() - t0)
      }
      rtts.sort((a, b) => a - b)
      const socketMs = await probeSocket(() => call("kamra.pos.speed_check", { property, echo: 1 }))
      setRes({ rtt: Math.round(rtts[2]), server: last!.server, setup: last!.setup, socketMs })
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const verdicts: { ok: boolean; text: string }[] = []
  if (res) {
    const srv = Math.max(res.server.open_bills_ms ?? 0, res.server.kitchen_display_ms ?? 0)
    verdicts.push(res.rtt <= 300
      ? { ok: true, text: t("Network round trip {ms} ms - fine.", { ms: res.rtt }) }
      : { ok: false, text: t("Network round trip {ms} ms - slow. The server is far from the hotel or the connection is weak; every POS action waits this long.", { ms: res.rtt }) })
    verdicts.push(srv <= 300
      ? { ok: true, text: t("Server work {ms} ms - fine.", { ms: Math.round(srv) }) }
      : { ok: false, text: t("Server work {ms} ms - slow. The server is busy or under-sized.", { ms: Math.round(srv) }) })
    verdicts.push(res.socketMs !== null
      ? { ok: true, text: t("Live updates arrive in {ms} ms.", { ms: res.socketMs }) }
      : { ok: false, text: t("Live updates are not reaching this browser, so the kitchen display only refreshes every few seconds. Check that socket.io is running and proxied by the web server.") })
    if (res.setup.background_workers === 0) {
      verdicts.push({ ok: false, text: t("No background workers are running.") })
    }
    if (res.setup.developer_mode) {
      verdicts.push({ ok: false, text: t("Developer mode is on - turn it off in production.") })
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{t("POS speed check")}</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              {t("Run this on a till when service feels slow. It tells you whether the network, the server or live updates are the cause.")}
            </p>
          </div>
          <Button variant="outline" disabled={busy} onClick={run}>
            {busy ? t("Checking…") : t("Check speed")}
          </Button>
        </div>
      </CardHeader>
      {(res || err) && (
        <CardContent>
          {err && <p className="text-sm text-rose-700">{err}</p>}
          <ul className="space-y-1.5 text-sm">
            {verdicts.map((v, i) => (
              <li key={i} className={v.ok ? "text-emerald-700" : "text-amber-800"}>
                {v.ok ? "✓ " : "! "}{v.text}
              </li>
            ))}
          </ul>
        </CardContent>
      )}
    </Card>
  )
}

const STATIONS = ["Kitchen", "Tandoor", "Grill", "Fryer", "Bar"]

interface KitchenPrinter {
  name: string
  printer_name: string
  connection: "Print station" | "Direct IP"
  paper_width: string
  copies: number
  ip_address: string | null
  port: number | null
  fallback_printer: string | null
  disabled: 0 | 1
  last_seen: string | null
  last_printed: string | null
  last_error: string | null
  queued: number
  failed_today: number
  online: boolean | null
  routes: { outlet: string; prep_station: string }[]
}

type PrinterDraft = Omit<KitchenPrinter, "name" | "last_seen" | "last_printed" | "last_error" | "queued" | "failed_today" | "online"> & { name?: string }

const blankPrinter = (): PrinterDraft => ({
  printer_name: "", connection: "Print station", paper_width: "80 mm", copies: 1,
  ip_address: "", port: 9100, fallback_printer: null, disabled: 0, routes: [],
})

/** Kitchen printers and what each one prints - Settings > F&B. */
export function KitchenPrintersCard({ property }: { property: string }) {
  const { t } = useT()
  const [printers, setPrinters] = useState<KitchenPrinter[]>([])
  const [outlets, setOutlets] = useState<{ name: string; outlet_name: string }[]>([])
  const [form, setForm] = useState<PrinterDraft | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    call<KitchenPrinter[]>("kamra.printing.printers", { property }).then(setPrinters).catch(() => {})
  }, [property])
  useEffect(() => {
    load()
    call<{ name: string; outlet_name: string }[]>("kamra.pos.outlets", { property }).then(setOutlets).catch(() => {})
    const tm = setInterval(load, 15_000) // status dots stay current
    return () => clearInterval(tm)
  }, [load, property])

  const outletName = (o: string) => outlets.find((x) => x.name === o)?.outlet_name || o
  const has = (o: string, st: string) => !!form?.routes.some((r) => r.outlet === o && r.prep_station === st)
  function toggle(o: string, st: string) {
    if (!form) return
    let routes = form.routes
    if (st === "") {
      // "All stations" replaces the outlet's single-station rows
      routes = has(o, "") ? routes.filter((r) => r.outlet !== o)
        : [...routes.filter((r) => r.outlet !== o), { outlet: o, prep_station: "" }]
    } else {
      routes = routes.filter((r) => !(r.outlet === o && r.prep_station === ""))
      routes = has(o, st) ? routes.filter((r) => !(r.outlet === o && r.prep_station === st))
        : [...routes, { outlet: o, prep_station: st }]
    }
    setForm({ ...form, routes })
  }

  async function save() {
    if (!form) return
    setBusy(true); setErr(null)
    try {
      const { name, ...printer } = form
      await call("kamra.printing.save_printer", { property, name: name || null, printer: JSON.stringify(printer) })
      setForm(null); setNote(t("Printer saved.")); load()
    } catch (e) { setErr(serverError(e)) } finally { setBusy(false) }
  }
  async function remove(p: KitchenPrinter) {
    setErr(null)
    try { await call("kamra.printing.delete_printer", { name: p.name }); setNote(t("Printer removed.")); load() }
    catch (e) { setErr(serverError(e)) }
  }
  async function test(p: KitchenPrinter) {
    setErr(null)
    try {
      await call("kamra.printing.test_print", { name: p.name })
      setNote(p.connection === "Print station"
        ? t("Test page sent. It prints on the kitchen screen set to print for {printer}.", { printer: p.printer_name })
        : t("Test page sent to {ip}.", { ip: p.ip_address || "" }))
      setTimeout(load, 4000)
    } catch (e) { setErr(serverError(e)) }
  }

  const status = (p: KitchenPrinter) => {
    if (p.disabled) return { tone: "bg-zinc-300", text: t("Disabled") }
    if (p.last_error && p.failed_today) return { tone: "bg-rose-500", text: p.last_error }
    if (p.connection === "Print station") {
      return p.online
        ? { tone: "bg-emerald-500", text: t("A kitchen screen is printing for it") }
        : { tone: "bg-amber-500", text: t("No kitchen screen is printing for it right now") }
    }
    return p.last_printed
      ? { tone: "bg-emerald-500", text: t("Last printed {at}", { at: p.last_printed.slice(0, 16) }) }
      : { tone: "bg-zinc-300", text: t("Not used yet") }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{t("Kitchen printers")}</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              {t("Which printer gets which KOTs. Two restaurants can share a kitchen printer, and the bar's drinks can print at the bar. With no printers here, each till prints its own KOTs.")}
            </p>
          </div>
          {!form && (
            <Button variant="outline" className="shrink-0 whitespace-nowrap"
              onClick={() => { setForm(blankPrinter()); setNote(null) }}>
              {t("Add printer")}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {err && <p className="text-sm text-rose-700">{err}</p>}
        {note && <p className="text-sm text-emerald-700">{note}</p>}

        {!form && printers.length === 0 && (
          <p className="text-sm text-zinc-500">{t("No kitchen printers yet.")}</p>
        )}

        {!form && printers.map((p) => {
          const st = status(p)
          return (
            <div key={p.name} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-zinc-200 px-3 py-2.5">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-semibold text-zinc-900">
                  <span className={`size-2 shrink-0 rounded-full ${st.tone}`} title={st.text} />
                  {p.printer_name}
                  <span className="text-xs font-normal text-zinc-400">
                    {p.connection === "Direct IP" ? `${p.ip_address}:${p.port || 9100}` : t("Print station")} · {p.paper_width}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-zinc-500">
                  {p.routes.length
                    ? p.routes.map((r) => `${outletName(r.outlet)} · ${r.prep_station || t("all stations")}`).join(", ")
                    : t("Prints nothing yet - choose outlets and stations.")}
                </p>
                <p className="mt-0.5 text-xs text-zinc-400">
                  {st.text}
                  {p.queued ? ` · ${t("{n} waiting", { n: p.queued })}` : ""}
                  {p.failed_today ? ` · ${t("{n} failed today", { n: p.failed_today })}` : ""}
                </p>
              </div>
              <div className="flex shrink-0 gap-1.5">
                <Button variant="ghost" onClick={() => test(p)}>{t("Test print")}</Button>
                <Button variant="ghost" onClick={() => {
                  setNote(null)
                  setForm({
                    name: p.name, printer_name: p.printer_name, connection: p.connection,
                    paper_width: p.paper_width, copies: p.copies, ip_address: p.ip_address || "",
                    port: p.port || 9100, fallback_printer: p.fallback_printer, disabled: p.disabled,
                    routes: p.routes,
                  })
                }}>{t("Edit")}</Button>
                <Button variant="ghost" onClick={() => remove(p)}>{t("Remove")}</Button>
              </div>
            </div>
          )
        })}

        {form && (
          <div className="space-y-4 rounded-lg border border-zinc-200 p-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm">
                <span className="mb-1 block font-medium text-zinc-700">{t("Printer name")}</span>
                <input className={inputCls} value={form.printer_name} placeholder={t("Main kitchen")}
                  onChange={(e) => setForm({ ...form, printer_name: e.target.value })} />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block font-medium text-zinc-700">{t("Connection")}</span>
                <select className={inputCls} value={form.connection}
                  onChange={(e) => setForm({ ...form, connection: e.target.value as PrinterDraft["connection"] })}>
                  <option value="Print station">{t("Print station (a kitchen screen prints it)")}</option>
                  <option value="Direct IP">{t("Direct IP (Kamra on the hotel network)")}</option>
                </select>
                <span className="mt-1 block text-xs text-zinc-400">
                  {form.connection === "Print station"
                    ? t("Any printer - USB, network or Bluetooth - attached to a device in the kitchen. On that device, open the kitchen display and pick this printer under Print for.")
                    : t("Kamra sends the ticket straight to the printer's network address. Only works when the Kamra server is on the same network as the printer, not on a cloud server.")}
                </span>
              </label>
              {form.connection === "Direct IP" && (
                <>
                  <label className="block text-sm">
                    <span className="mb-1 block font-medium text-zinc-700">{t("IP address")}</span>
                    <input className={inputCls} value={form.ip_address || ""} placeholder="192.168.1.50"
                      onChange={(e) => setForm({ ...form, ip_address: e.target.value })} />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1 block font-medium text-zinc-700">{t("Port")}</span>
                    <input className={inputCls} type="number" value={form.port ?? 9100}
                      onChange={(e) => setForm({ ...form, port: Number(e.target.value) || 9100 })} />
                  </label>
                </>
              )}
              <label className="block text-sm">
                <span className="mb-1 block font-medium text-zinc-700">{t("Paper width")}</span>
                <select className={inputCls} value={form.paper_width}
                  onChange={(e) => setForm({ ...form, paper_width: e.target.value })}>
                  <option>80 mm</option>
                  <option>58 mm</option>
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block font-medium text-zinc-700">{t("Copies")}</span>
                <select className={inputCls} value={form.copies}
                  onChange={(e) => setForm({ ...form, copies: Number(e.target.value) })}>
                  {[1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block font-medium text-zinc-700">{t("Fallback printer")}</span>
                <select className={inputCls} value={form.fallback_printer || ""}
                  onChange={(e) => setForm({ ...form, fallback_printer: e.target.value || null })}>
                  <option value="">{t("None")}</option>
                  {printers.filter((p) => p.name !== form.name).map((p) => (
                    <option key={p.name} value={p.name}>{p.printer_name}</option>
                  ))}
                </select>
                <span className="mt-1 block text-xs text-zinc-400">{t("Where a ticket goes if this printer fails.")}</span>
              </label>
              <label className="flex items-center gap-2 self-end pb-2 text-sm">
                <input type="checkbox" checked={!!form.disabled}
                  onChange={(e) => setForm({ ...form, disabled: e.target.checked ? 1 : 0 })} />
                {t("Disabled")}
              </label>
            </div>

            <div>
              <p className="mb-1.5 text-sm font-medium text-zinc-700">{t("Prints KOTs for")}</p>
              {outlets.length === 0 ? (
                <p className="text-sm text-zinc-500">{t("Add an outlet first.")}</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[28rem] text-sm">
                    <thead>
                      <tr className="text-xs text-zinc-500">
                        <th className="py-1 text-start font-medium">{t("Outlet")}</th>
                        <th className="px-2 py-1 font-medium">{t("All stations")}</th>
                        {STATIONS.map((st) => <th key={st} className="px-2 py-1 font-medium">{t(st)}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {outlets.map((o) => (
                        <tr key={o.name} className="border-t border-zinc-100">
                          <td className="py-1.5 pe-2">{o.outlet_name}</td>
                          <td className="px-2 text-center">
                            <input type="checkbox" checked={has(o.name, "")} onChange={() => toggle(o.name, "")}
                              aria-label={`${o.outlet_name} - ${t("All stations")}`} />
                          </td>
                          {STATIONS.map((st) => (
                            <td key={st} className="px-2 text-center">
                              <input type="checkbox" checked={has(o.name, "") || has(o.name, st)}
                                disabled={has(o.name, "")} onChange={() => toggle(o.name, st)}
                                aria-label={`${o.outlet_name} - ${st}`} />
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="mt-1.5 text-xs text-zinc-400">
                {t("A station comes from each menu item. Tick the same outlet on several printers to print a copy on each.")}
              </p>
            </div>

            <div className="flex gap-2">
              <Button disabled={busy} onClick={save}>{busy ? t("Saving…") : t("Save printer")}</Button>
              <Button variant="ghost" onClick={() => { setForm(null); setErr(null) }}>{t("Cancel")}</Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
