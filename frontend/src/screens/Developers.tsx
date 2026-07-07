import { useEffect, useState } from "react"
import { Check, Copy, KeyRound, RefreshCw, Terminal } from "lucide-react"

import {
  developerInfo,
  generateApiKey,
  getCurrentProperty,
} from "../lib/api"
import { serverError } from "../lib/resource"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { Button } from "../components/ui/button"

function Copyable({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-zinc-500">{label}</div>
      <div className="flex items-stretch gap-2">
        <code className="flex-1 overflow-x-auto rounded-lg bg-zinc-100 px-3 py-2 font-mono text-xs text-zinc-800">
          {value}
        </code>
        <button
          onClick={() => {
            navigator.clipboard?.writeText(value)
            setCopied(true)
            setTimeout(() => setCopied(false), 1200)
          }}
          className="flex items-center gap-1 rounded-lg border border-zinc-200 px-2.5 text-xs font-medium text-zinc-600 hover:border-brand-600 hover:text-brand-700"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  )
}

const ENDPOINTS: { group: string; rows: [string, string][] }[] = [
  {
    group: "Availability & booking",
    rows: [
      ["availability_calendar", "Rooms × dates with live rates"],
      ["booking_options", "Room types, meal & rate plans, add-ons"],
      ["get_quote", "Deterministic priced quote for a stay"],
      ["create_booking", "Create a reservation (guest deduped by phone)"],
    ],
  },
  {
    group: "Front desk",
    rows: [
      ["front_desk_snapshot", "Arrivals, departures, in-house, room board"],
      ["reservation_detail", "Full 360 for one booking"],
      ["check_in / check_out", "Move a stay through its lifecycle"],
      ["amend_stay / move_reservation", "Change dates or room (re-prices)"],
    ],
  },
  {
    group: "Money",
    rows: [
      ["get_folio / reservation_folios", "Folios for a stay"],
      ["add_folio_charge / add_folio_payment", "Post charges & payments"],
      ["folio_invoice / close_folio", "GST invoice + number assignment"],
      ["record_advance / folio_payment_link", "Deposits & payment links"],
    ],
  },
]

export default function Developers() {
  const [info, setInfo] = useState<{
    user: string
    has_key: boolean
    base_url: string
  } | null>(null)
  const [key, setKey] = useState<{ api_key: string; api_secret: string } | null>(
    null,
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const property = getCurrentProperty()

  useEffect(() => {
    developerInfo()
      .then(setInfo)
      .catch((e) => setError(serverError(e)))
  }, [])

  async function generate() {
    if (
      info?.has_key &&
      !confirm(
        "Rotating your key invalidates the old one. Any integration using it will stop working. Continue?",
      )
    )
      return
    setBusy(true)
    setError(null)
    try {
      const k = await generateApiKey()
      setKey(k)
      setInfo((i) => (i ? { ...i, has_key: true } : i))
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const base = info?.base_url ?? window.location.origin
  const authHeader = key
    ? `token ${key.api_key}:${key.api_secret}`
    : "token <api_key>:<api_secret>"

  return (
    <div className="mx-auto max-w-3xl space-y-5 py-2">
      <div>
        <h1 className="text-xl font-semibold">Developers</h1>
        <p className="mt-0.5 text-sm text-zinc-500">
          Your API key, the REST surface, and how to connect AI agents. Every
          call runs with your roles and lands in the audit log.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      {/* API key */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="size-4 text-zinc-400" /> Your API key
            </CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              Signed in as <code className="text-zinc-500">{info?.user}</code>.
              The secret is shown once - copy it now.
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {key ? (
            <>
              <Copyable label="API key" value={key.api_key} />
              <Copyable label="API secret" value={key.api_secret} />
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                Store the secret somewhere safe now - it can't be shown again.
                Rotate any time from here.
              </p>
            </>
          ) : (
            <p className="text-sm text-zinc-600">
              {info?.has_key
                ? "You already have an API key. Rotate it below to get a fresh key + secret."
                : "You don't have an API key yet. Generate one to call the REST API or connect an agent."}
            </p>
          )}
          <Button onClick={generate} disabled={busy}>
            <RefreshCw className="size-4" />
            {busy
              ? "Generating…"
              : info?.has_key
                ? "Rotate API key"
                : "Generate API key"}
          </Button>
        </CardContent>
      </Card>

      {/* REST quickstart */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="size-4 text-zinc-400" /> REST API
            </CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              Base URL <code className="text-zinc-500">{base}</code>. Authenticate
              with the token header on every request.
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <Copyable label="Authorization header" value={`Authorization: ${authHeader}`} />
          <div>
            <div className="mb-1 text-xs font-medium text-zinc-500">
              Example - today's front desk
            </div>
            <pre className="overflow-x-auto rounded-lg bg-zinc-900 p-3 text-xs leading-relaxed text-zinc-100">
{`curl -X POST ${base}/api/method/kamra.api.front_desk_snapshot \\
  -H "Authorization: ${authHeader}" \\
  -H "Content-Type: application/json" \\
  -d '{"property": "${property}"}'`}
            </pre>
          </div>
          <p className="text-xs text-zinc-400">
            Full reference:{" "}
            <a
              href="https://github.com/Kamra-PMS/kamra-pms/blob/main/docs/ai-and-api.md"
              target="_blank"
              rel="noreferrer"
              className="font-medium text-brand-700 hover:underline"
            >
              docs/ai-and-api.md →
            </a>
          </p>
        </CardContent>
      </Card>

      {/* endpoint reference */}
      <Card>
        <CardHeader>
          <CardTitle>Key endpoints</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            All under <code className="text-zinc-500">/api/method/kamra.api.&lt;name&gt;</code>{" "}
            (POST, JSON). Role-gated the same as the UI.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {ENDPOINTS.map((sec) => (
            <div key={sec.group}>
              <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-zinc-400">
                {sec.group}
              </div>
              <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-100">
                {sec.rows.map(([name, desc]) => (
                  <div
                    key={name}
                    className="flex flex-col gap-0.5 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <code className="font-mono text-xs text-zinc-800">{name}</code>
                    <span className="text-xs text-zinc-500">{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* MCP */}
      <Card>
        <CardHeader>
          <CardTitle>Connect an AI agent (MCP)</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            Point Claude (or any MCP client) at this property's governed tool
            layer, authenticated with the key above.
          </p>
        </CardHeader>
        <CardContent>
          <pre className="overflow-x-auto rounded-lg bg-zinc-100 p-3 text-xs leading-relaxed text-zinc-700">
{`claude mcp add kamra \\
  -e KAMRA_URL=${base} \\
  -e KAMRA_API_KEY=${key?.api_key ?? "<api key>"} \\
  -e KAMRA_API_SECRET=${key?.api_secret ?? "<api secret>"} \\
  -e KAMRA_PROPERTY="${property}" \\
  -- python apps/kamra/mcp/kamra_mcp.py`}
          </pre>
        </CardContent>
      </Card>
    </div>
  )
}
