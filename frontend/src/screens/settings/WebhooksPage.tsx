import { useCallback, useEffect, useState } from "react"
import { Check, Copy, Plus, RefreshCw, RotateCcw, Send, Trash2 } from "lucide-react"

import { Badge } from "../../components/ui/badge"
import { Button } from "../../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card"
import { call } from "../../lib/api"
import { useT } from "../../lib/i18n"
import { serverError } from "../../lib/resource"
import { cn } from "../../lib/utils"
import { Switch } from "./ModulePage"

/** Outbound webhooks: per-property endpoints that receive signed event
 *  notifications, and the delivery log. Backend: kamra.webhooks (Hotel
 *  Admin / System Manager only). Secrets are shown once, never listed. */

interface EventDef {
  event: string
  description: string
}

interface Hook {
  name: string
  label: string | null
  url: string
  active: number
  events: string[]
  has_secret: boolean
  last_status: string | null
  last_delivery_on: string | null
  consecutive_failures: number
}

interface Delivery {
  name: string
  webhook: string
  event: string
  event_id: string
  status: "Pending" | "Delivered" | "Retrying" | "Failed"
  attempts: number
  response_code: number | null
  duration_ms: number | null
  last_error: string | null
  next_retry_at: string | null
  creation: string
}

const STATUS_TONE: Record<Delivery["status"], "green" | "amber" | "rose" | "zinc"> = {
  Delivered: "green",
  Retrying: "amber",
  Failed: "rose",
  Pending: "zinc",
}

const M = "kamra.webhooks."

/** A message meant for the user as-is (serverError would hide it behind a
 *  generic "something went wrong"). */
class ShownError extends Error {}

function SecretOnce({ secret, onDone }: { secret: string; onDone: () => void }) {
  const { t } = useT()
  const [copied, setCopied] = useState(false)
  return (
    <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
      <p className="text-sm font-medium text-amber-800">
        {t("Signing secret - copy it now. It won't be shown again.")}
      </p>
      <div className="flex items-stretch gap-2">
        <code className="flex-1 overflow-x-auto rounded-md bg-white px-3 py-2 font-mono text-xs text-zinc-800">
          {secret}
        </code>
        <Button
          variant="outline"
          onClick={() => {
            navigator.clipboard?.writeText(secret)
            setCopied(true)
          }}
        >
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
          {copied ? t("Copied") : t("Copy")}
        </Button>
      </div>
      <Button variant="ghost" onClick={onDone}>
        {t("I've stored it")}
      </Button>
    </div>
  )
}

function HookForm({
  property, events, hook, onSaved, onCancel,
}: {
  property: string
  events: EventDef[]
  hook: Hook | null
  onSaved: (secret: string | null) => void
  onCancel: () => void
}) {
  const { t } = useT()
  const [label, setLabel] = useState(hook?.label ?? "")
  const [url, setUrl] = useState(hook?.url ?? "https://")
  const [picked, setPicked] = useState<string[]>(hook?.events ?? events.map((e) => e.event))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      const out = await call<Hook & { secret: string | null }>(`${M}save_webhook`, {
        property, url, events: picked, label, active: hook ? hook.active : 1,
        name: hook?.name,
      })
      onSaved(out.secret)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-zinc-200 bg-zinc-50 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Label")}</span>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={t("e.g. Door lock middleware")}
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Endpoint URL (HTTPS)")}</span>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 font-mono text-xs"
          />
        </label>
      </div>
      <fieldset>
        <legend className="mb-1 text-xs font-medium text-zinc-500">{t("Events")}</legend>
        <div className="grid gap-1.5 sm:grid-cols-2">
          {events.map((ev) => (
            <label key={ev.event} className="flex items-start gap-2 rounded-md px-1 py-1 text-sm hover:bg-white">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={picked.includes(ev.event)}
                onChange={(e) =>
                  setPicked((p) => (e.target.checked ? [...p, ev.event] : p.filter((x) => x !== ev.event)))
                }
              />
              <span>
                <code className="font-mono text-xs text-zinc-800">{ev.event}</code>
                <span className="block text-xs text-zinc-500">{t(ev.description)}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      <div className="flex gap-2">
        <Button onClick={save} disabled={busy || !picked.length}>
          {busy ? t("Saving…") : hook ? t("Save") : t("Add webhook")}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          {t("Cancel")}
        </Button>
      </div>
    </div>
  )
}

export function WebhooksPage({ property }: { property: string }) {
  const { t } = useT()
  const [events, setEvents] = useState<EventDef[]>([])
  const [hooks, setHooks] = useState<Hook[] | null>(null)
  const [log, setLog] = useState<Delivery[]>([])
  const [statusFilter, setStatusFilter] = useState("")
  const [editing, setEditing] = useState<Hook | "new" | null>(null)
  const [secret, setSecret] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [payload, setPayload] = useState<string>("")
  const [note, setNote] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    call<Hook[]>(`${M}list_webhooks`, { property })
      .then(setHooks)
      .catch((e) => setError(serverError(e)))
    call<Delivery[]>(`${M}webhook_deliveries`, { property, status: statusFilter || undefined, limit: 50 })
      .then(setLog)
      .catch(() => setLog([]))
  }, [property, statusFilter])

  useEffect(() => {
    call<EventDef[]>(`${M}webhook_events`).then(setEvents).catch(() => setEvents([]))
  }, [])
  useEffect(load, [load])

  async function act(fn: () => Promise<unknown>, done?: string) {
    setError(null)
    setNote(null)
    try {
      await fn()
      if (done) setNote(done)
      load()
    } catch (e) {
      setError(e instanceof ShownError ? e.message : serverError(e))
    }
  }

  const hookLabel = (name: string) => {
    const h = hooks?.find((x) => x.name === name)
    return h?.label || h?.url || name
  }

  if (!hooks) return <p className="py-6 text-sm text-zinc-400">{error ?? t("Loading…")}</p>

  return (
    <div className="space-y-5">
      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      {note && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{note}</p>}
      {secret && <SecretOnce secret={secret} onDone={() => setSecret(null)} />}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>{t("Endpoints")}</CardTitle>
              <p className="mt-0.5 text-xs text-zinc-400">
                {t("Kamra POSTs a signed JSON event to each endpoint. Failed deliveries are retried for about 8 hours.")}
              </p>
            </div>
            {editing === null && (
              <Button onClick={() => setEditing("new")}>
                <Plus className="size-4" /> {t("Add webhook")}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {editing === "new" && (
            <HookForm
              property={property}
              events={events}
              hook={null}
              onCancel={() => setEditing(null)}
              onSaved={(s) => {
                setEditing(null)
                setSecret(s)
                load()
              }}
            />
          )}
          {hooks.length === 0 && editing === null && (
            <p className="text-sm text-zinc-500">
              {t("No webhooks yet. Add one to send bookings, check-ins, folio postings and the night audit to another system.")}
            </p>
          )}
          {hooks.map((h) =>
            editing !== null && editing !== "new" && editing.name === h.name ? (
              <HookForm
                key={h.name}
                property={property}
                events={events}
                hook={h}
                onCancel={() => setEditing(null)}
                onSaved={() => {
                  setEditing(null)
                  load()
                }}
              />
            ) : (
              <div key={h.name} className="rounded-lg border border-zinc-200 p-3">
                <div className="flex flex-wrap items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-zinc-900">{h.label || t("Webhook")}</p>
                    <p className="truncate font-mono text-xs text-zinc-500">{h.url}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {h.events.map((e) => (
                        <Badge key={e} tone="brand">{e}</Badge>
                      ))}
                    </div>
                    <p className="mt-2 text-xs text-zinc-500">
                      {h.last_status
                        ? t("Last delivery: {status}", { status: h.last_status })
                        : t("Nothing sent yet")}
                      {h.consecutive_failures > 0 && (
                        <span className="ms-2 text-rose-600">
                          {t("{n} failures in a row", { n: String(h.consecutive_failures) })}
                        </span>
                      )}
                    </p>
                  </div>
                  <Switch
                    on={!!h.active}
                    label={t("Active")}
                    onToggle={() =>
                      act(() =>
                        call(`${M}save_webhook`, {
                          property, url: h.url, events: h.events, label: h.label,
                          active: h.active ? 0 : 1, name: h.name,
                        }),
                      )
                    }
                  />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    disabled={!h.active}
                    onClick={() =>
                      act(async () => {
                        const r = await call<{ status: string; response_code: number | null; error: string | null }>(
                          `${M}send_test_event`, { name: h.name, property },
                        )
                        if (r.status !== "Delivered")
                          throw new ShownError(`${t("Test failed")}: ${r.error ?? r.status}`)
                      }, t("Test event delivered."))
                    }
                  >
                    <Send className="size-4" /> {t("Send test")}
                  </Button>
                  <Button variant="outline" onClick={() => setEditing(h)}>
                    {t("Edit")}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      if (!confirm(t("Rotate the signing secret? The receiver must switch to the new one.")))
                        return
                      act(async () => {
                        const r = await call<{ secret: string }>(`${M}rotate_webhook_secret`, {
                          name: h.name, property,
                        })
                        setSecret(r.secret)
                      })
                    }}
                  >
                    <RefreshCw className="size-4" /> {t("Rotate secret")}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      if (!confirm(t("Delete this webhook and its delivery log?"))) return
                      act(() => call(`${M}delete_webhook`, { name: h.name, property }))
                    }}
                  >
                    <Trash2 className="size-4" /> {t("Delete")}
                  </Button>
                </div>
              </div>
            ),
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle>{t("Delivery log")}</CardTitle>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label={t("Filter by status")}
              className="rounded-lg border border-zinc-300 bg-white px-2 py-1 text-sm"
            >
              <option value="">{t("All")}</option>
              {(["Delivered", "Retrying", "Failed", "Pending"] as const).map((s) => (
                <option key={s} value={s}>{t(s)}</option>
              ))}
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {log.length === 0 ? (
            <p className="text-sm text-zinc-500">{t("No deliveries yet.")}</p>
          ) : (
            <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-100">
              {log.map((d) => (
                <div key={d.name} className="px-3 py-2 text-sm">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <Badge tone={STATUS_TONE[d.status]}>{t(d.status)}</Badge>
                    <code className="font-mono text-xs text-zinc-800">{d.event}</code>
                    <span className="text-xs text-zinc-500">{hookLabel(d.webhook)}</span>
                    <span className="ms-auto text-xs text-zinc-400">
                      {d.creation.slice(0, 16)}
                      {d.response_code ? ` · HTTP ${d.response_code}` : ""}
                      {` · ${t("{n} attempts", { n: String(d.attempts) })}`}
                    </span>
                  </div>
                  {d.last_error && d.status !== "Delivered" && (
                    <p className="mt-1 truncate text-xs text-rose-600">{d.last_error}</p>
                  )}
                  {d.status === "Retrying" && d.next_retry_at && (
                    <p className="mt-1 text-xs text-amber-700">
                      {t("Next try {at}", { at: d.next_retry_at.slice(0, 16) })}
                    </p>
                  )}
                  <div className="mt-1 flex gap-3">
                    <button
                      type="button"
                      className="text-xs font-medium text-brand-700 hover:underline"
                      onClick={async () => {
                        if (open === d.name) return setOpen(null)
                        const r = await call<{ payload: string }>(`${M}delivery_detail`, { delivery: d.name })
                        try {
                          setPayload(JSON.stringify(JSON.parse(r.payload), null, 2))
                        } catch {
                          setPayload(r.payload)
                        }
                        setOpen(d.name)
                      }}
                    >
                      {open === d.name ? t("Hide payload") : t("Payload")}
                    </button>
                    {d.status !== "Pending" && (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline"
                        onClick={() =>
                          act(() => call(`${M}resend_delivery`, { delivery: d.name }), t("Queued to resend."))
                        }
                      >
                        <RotateCcw className="size-3" /> {t("Resend")}
                      </button>
                    )}
                  </div>
                  {open === d.name && (
                    <pre className={cn("mt-2 max-h-72 overflow-auto rounded-lg bg-zinc-900 p-3 text-xs text-zinc-100")}>
                      {payload}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("Verifying a delivery")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-zinc-600">
          <p>
            {t("Each request carries X-Kamra-Event, X-Kamra-Event-Id, X-Kamra-Timestamp and X-Kamra-Signature. Recompute the signature over the raw body and reject old timestamps:")}
          </p>
          <pre className="overflow-x-auto rounded-lg bg-zinc-900 p-3 text-xs leading-relaxed text-zinc-100">
{`expected = "sha256=" + HMAC_SHA256(secret, timestamp + "." + raw_body).hex()
valid = constant_time_equal(expected, X-Kamra-Signature)
        and abs(now - timestamp) < 300`}
          </pre>
          <p className="text-xs text-zinc-500">
            {t("Answer 2xx within 10 seconds. Retries keep the same event id, so ignore ids you've already processed.")}{" "}
            <a
              href="https://kamrapms.com/docs/integrations"
              target="_blank"
              rel="noreferrer"
              className="font-medium text-brand-700 hover:underline"
            >
              {t("Integrations guide")} →
            </a>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
