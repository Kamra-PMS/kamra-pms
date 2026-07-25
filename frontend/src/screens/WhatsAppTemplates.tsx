import { useCallback, useEffect, useState } from "react"
import {
  ArrowLeft, Check, Copy, ExternalLink, Phone, Plus, RefreshCw, Send,
} from "lucide-react"
import { Link } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"

/* Template builder: design a WhatsApp template with a live phone-style
   preview, save drafts locally, submit to Meta and track approval.
   Modeled on frappe_whatsapp's builder (PR #247), grown into Kamra. */

interface Btn {
  type: "Quick reply" | "URL" | "Phone number"
  text: string
  url?: string
  phone_number?: string
}
interface Tpl {
  name: string | null
  template_name: string
  category: string
  language: string
  header_type: "None" | "Text"
  header_text: string
  body: string
  footer: string
  buttons_json: string
  samples_json: string
  meta_status: string
  meta_id: string | null
  rejection_reason: string | null
}

const empty = (): Tpl => ({
  name: null,
  template_name: "",
  category: "Utility",
  language: "en",
  header_type: "None",
  header_text: "",
  body: "",
  footer: "",
  buttons_json: "[]",
  samples_json: "[]",
  meta_status: "Draft",
  meta_id: null,
  rejection_reason: null,
})

const statusTone: Record<string, string> = {
  Draft: "bg-zinc-100 text-zinc-600",
  Pending: "bg-amber-100 text-amber-800",
  Approved: "bg-emerald-100 text-emerald-800",
  Rejected: "bg-rose-100 text-rose-700",
  Paused: "bg-orange-100 text-orange-800",
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

function varsIn(body: string): number {
  return new Set(body.match(/\{\{(\d+)\}\}/g) ?? []).size
}

/** Substitute {{n}} with sample values and render *bold* WhatsApp-style. */
function previewText(body: string, samples: string[]): string {
  return body.replace(/\{\{(\d+)\}\}/g, (_, n) => {
    const s = samples[Number(n) - 1]
    return s?.trim() ? s : `{{${n}}}`
  })
}

export default function WhatsAppTemplates() {
  const property = getCurrentProperty()
  const [list, setList] = useState<Tpl[]>([])
  const [tpl, setTpl] = useState<Tpl>(empty())
  const [buttons, setButtons] = useState<Btn[]>([])
  const [samples, setSamples] = useState<string[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(() => {
    call<Tpl[]>("kamra.whatsapp.list_templates", { property })
      .then(setList)
      .catch((e) => setError(serverError(e)))
  }, [property])
  useEffect(load, [load])

  function open(t: Tpl) {
    setTpl(t)
    setButtons(JSON.parse(t.buttons_json || "[]"))
    setSamples(JSON.parse(t.samples_json || "[]"))
    setError(null)
    setNotice(null)
  }

  const locked = Boolean(tpl.meta_id)
  const nvars = varsIn(tpl.body)

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(label)
    setError(null)
    setNotice(null)
    try {
      await fn()
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  const payload = () => ({
    ...tpl,
    property,
    buttons_json: JSON.stringify(buttons),
    samples_json: JSON.stringify(samples.slice(0, nvars)),
  })

  const saveDraft = () =>
    run("save", async () => {
      const r = await call<{ name: string }>("kamra.whatsapp.save_template", {
        payload: payload(),
      })
      setTpl((t) => ({ ...t, name: r.name }))
      setNotice("Draft saved - it lives only in Kamra until you submit.")
    })

  const submit = () =>
    run("submit", async () => {
      if (!tpl.name) {
        const r = await call<{ name: string }>("kamra.whatsapp.save_template", {
          payload: payload(),
        })
        tpl.name = r.name
      } else {
        await call("kamra.whatsapp.save_template", { payload: payload() })
      }
      const s = await call<{ status: string }>(
        "kamra.whatsapp.submit_template",
        { name: tpl.name },
      )
      setNotice(`Submitted - Meta says ${s.status}. Sync to track approval.`)
    })

  const sync = () =>
    run("sync", async () => {
      const r = await call<{ updated: number; on_meta: number }>(
        "kamra.whatsapp.sync_templates",
        { property },
      )
      setNotice(`Synced with Meta: ${r.updated} template(s) updated.`)
    })

  const duplicate = () => {
    setTpl({
      ...tpl,
      name: null,
      template_name: `${tpl.template_name}_v2`,
      meta_id: null,
      meta_status: "Draft",
      rejection_reason: null,
    })
    setNotice("Duplicated as a new draft - rename and submit.")
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        <Link
          to="/whatsapp"
          className="flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800"
        >
          <ArrowLeft className="size-4" aria-hidden /> WhatsApp
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">
          Template Builder
        </h1>
        <p className="text-sm text-zinc-500">
          Design it here, submit to Meta, use it the moment it's approved.
        </p>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" disabled={busy !== null} onClick={sync}>
            <RefreshCw className={cn("size-4", busy === "sync" && "animate-spin")} aria-hidden />
            Sync status
          </Button>
          <Button variant="outline" onClick={() => open(empty())}>
            <Plus className="size-4" aria-hidden /> New
          </Button>
        </div>
      </header>

      <div className="grid gap-4 xl:grid-cols-4">
        {/* saved templates */}
        <div className="rounded-2xl border border-zinc-200 bg-white">
          <ul className="max-h-[75vh] divide-y divide-zinc-100 overflow-y-auto">
            {list.map((t) => (
              <li key={t.name}>
                <button
                  onClick={() => open(t)}
                  className={cn(
                    "w-full px-4 py-3 text-left hover:bg-zinc-50",
                    tpl.name === t.name && "bg-brand-50/60",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-xs font-semibold text-zinc-800">
                      {t.template_name}
                    </span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                        statusTone[t.meta_status] ?? statusTone.Draft,
                      )}
                    >
                      {t.meta_status}
                    </span>
                  </div>
                  <p className="mt-0.5 truncate text-xs text-zinc-500">{t.body}</p>
                </button>
              </li>
            ))}
            {list.length === 0 && (
              <li className="px-4 py-6 text-center text-sm text-zinc-400">
                No templates yet - design your first on the right.
              </li>
            )}
          </ul>
        </div>

        {/* editor */}
        <div className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-5 xl:col-span-2">
          {locked && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Registered with Meta - submitted templates can't be edited.
              Duplicate it to make changes.
            </p>
          )}
          {tpl.meta_status === "Rejected" && tpl.rejection_reason && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">
              Rejected: {tpl.rejection_reason}
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="sm:col-span-1">
              <span className="mb-1 block text-xs font-medium text-zinc-500">Template name</span>
              <input
                className={`${inputCls} font-mono`}
                placeholder="booking_update"
                value={tpl.template_name}
                disabled={locked}
                onChange={(e) =>
                  setTpl({ ...tpl, template_name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })
                }
              />
            </label>
            <label>
              <span className="mb-1 block text-xs font-medium text-zinc-500">Category</span>
              <select
                className={inputCls}
                value={tpl.category}
                disabled={locked}
                onChange={(e) => setTpl({ ...tpl, category: e.target.value })}
              >
                {["Utility", "Marketing", "Authentication"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="mb-1 block text-xs font-medium text-zinc-500">Language</span>
              <input
                className={inputCls}
                value={tpl.language}
                disabled={locked}
                onChange={(e) => setTpl({ ...tpl, language: e.target.value })}
              />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <label>
              <span className="mb-1 block text-xs font-medium text-zinc-500">Header</span>
              <select
                className={inputCls}
                value={tpl.header_type}
                disabled={locked}
                onChange={(e) =>
                  setTpl({ ...tpl, header_type: e.target.value as Tpl["header_type"] })
                }
              >
                <option>None</option>
                <option>Text</option>
              </select>
            </label>
            {tpl.header_type === "Text" && (
              <label className="sm:col-span-2">
                <span className="mb-1 block text-xs font-medium text-zinc-500">Header text</span>
                <input
                  className={inputCls}
                  value={tpl.header_text}
                  disabled={locked}
                  maxLength={60}
                  onChange={(e) => setTpl({ ...tpl, header_text: e.target.value })}
                />
              </label>
            )}
          </div>

          <label className="block">
            <span className="mb-1 flex items-center justify-between text-xs font-medium text-zinc-500">
              <span>Body · variables as {"{{1}}"}, {"{{2}}"} …</span>
              <span>{tpl.body.length}/1024</span>
            </span>
            <textarea
              className={`${inputCls} min-h-32`}
              maxLength={1024}
              value={tpl.body}
              disabled={locked}
              onChange={(e) => setTpl({ ...tpl, body: e.target.value })}
            />
          </label>
          {!locked && (
            <button
              className="text-xs font-medium text-brand-700 hover:underline"
              onClick={() => setTpl({ ...tpl, body: tpl.body + `{{${nvars + 1}}}` })}
            >
              + Add variable {`{{${nvars + 1}}}`}
            </button>
          )}

          {nvars > 0 && (
            <div className="rounded-xl border border-zinc-200 p-3">
              <p className="mb-2 text-xs font-medium text-zinc-500">
                Sample values (Meta reviews the template with these)
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {Array.from({ length: nvars }, (_, i) => (
                  <label key={i} className="flex items-center gap-2 text-xs text-zinc-500">
                    <span className="font-mono">{`{{${i + 1}}}`}</span>
                    <input
                      className={inputCls}
                      value={samples[i] ?? ""}
                      disabled={locked}
                      onChange={(e) =>
                        setSamples((s) => {
                          const c = [...s]
                          c[i] = e.target.value
                          return c
                        })
                      }
                    />
                  </label>
                ))}
              </div>
            </div>
          )}

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">Footer</span>
            <input
              className={inputCls}
              maxLength={60}
              placeholder="Reply STOP to unsubscribe"
              value={tpl.footer}
              disabled={locked}
              onChange={(e) => setTpl({ ...tpl, footer: e.target.value })}
            />
          </label>

          <div className="rounded-xl border border-zinc-200 p-3">
            <p className="mb-2 text-xs font-medium text-zinc-500">Buttons (up to 10)</p>
            <div className="space-y-2">
              {buttons.map((b, i) => (
                <div key={i} className="flex flex-wrap items-center gap-1.5">
                  <select
                    className={`${inputCls} w-32`}
                    value={b.type}
                    disabled={locked}
                    onChange={(e) =>
                      setButtons((bs) =>
                        bs.map((x, j) => (j === i ? { ...x, type: e.target.value as Btn["type"] } : x)),
                      )
                    }
                  >
                    {["Quick reply", "URL", "Phone number"].map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                  <input
                    className={`${inputCls} w-36`}
                    placeholder="Button label"
                    maxLength={25}
                    value={b.text}
                    disabled={locked}
                    onChange={(e) =>
                      setButtons((bs) => bs.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))
                    }
                  />
                  {b.type === "URL" && (
                    <input
                      className={`${inputCls} flex-1`}
                      placeholder="https://…"
                      value={b.url ?? ""}
                      disabled={locked}
                      onChange={(e) =>
                        setButtons((bs) => bs.map((x, j) => (j === i ? { ...x, url: e.target.value } : x)))
                      }
                    />
                  )}
                  {b.type === "Phone number" && (
                    <input
                      className={`${inputCls} w-40`}
                      placeholder="+91…"
                      value={b.phone_number ?? ""}
                      disabled={locked}
                      onChange={(e) =>
                        setButtons((bs) =>
                          bs.map((x, j) => (j === i ? { ...x, phone_number: e.target.value } : x)),
                        )
                      }
                    />
                  )}
                  {!locked && (
                    <button
                      className="text-xs text-zinc-400 hover:text-rose-500"
                      onClick={() => setButtons((bs) => bs.filter((_, j) => j !== i))}
                    >
                      remove
                    </button>
                  )}
                </div>
              ))}
            </div>
            {!locked && buttons.length < 10 && (
              <Button
                variant="outline"
                className="mt-2"
                onClick={() => setButtons((bs) => [...bs, { type: "Quick reply", text: "" }])}
              >
                <Plus className="size-4" aria-hidden /> Add button
              </Button>
            )}
          </div>

          {error && <p className="text-sm text-rose-600">{error}</p>}
          {notice && <p className="text-sm text-emerald-700">{notice}</p>}
          <div className="flex flex-wrap items-center gap-2">
            {locked ? (
              <>
                <Button variant="outline" onClick={duplicate}>
                  <Copy className="size-4" aria-hidden /> Duplicate as new
                </Button>
                {tpl.meta_status === "Approved" && (
                  <AssignMenu property={property} template={tpl.template_name} onDone={() => setNotice("Wired into the automatic flow.")} />
                )}
              </>
            ) : (
              <>
                <Button variant="outline" disabled={busy !== null || !tpl.template_name || !tpl.body} onClick={saveDraft}>
                  {busy === "save" ? "Saving…" : "Save draft"}
                </Button>
                <Button disabled={busy !== null || !tpl.template_name || !tpl.body} onClick={submit}>
                  <Send className="size-4" aria-hidden />
                  {busy === "submit" ? "Submitting…" : "Submit to Meta"}
                </Button>
              </>
            )}
          </div>
        </div>

        {/* live preview */}
        <div className="rounded-2xl bg-zinc-900 p-4">
          <p className="mb-3 text-center text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
            Live preview · sample values applied
          </p>
          <div className="mx-auto max-w-xs rounded-2xl bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%224%22 height=%224%22><rect width=%224%22 height=%224%22 fill=%22%23121b17%22/></svg>')] bg-zinc-800/80 p-3">
            <div className="rounded-xl rounded-tl-sm bg-[#1f2c24] p-3 text-[13px] leading-snug text-zinc-100 shadow">
              {tpl.header_type === "Text" && tpl.header_text && (
                <p className="mb-1 font-semibold text-white">{tpl.header_text}</p>
              )}
              <p className="whitespace-pre-wrap">
                {previewText(tpl.body, samples) || (
                  <span className="text-zinc-500">Your message body appears here…</span>
                )}
              </p>
              {tpl.footer && (
                <p className="mt-1.5 text-[11px] text-zinc-400">{tpl.footer}</p>
              )}
              <p className="mt-1 text-right text-[10px] text-zinc-500">
                10:24 AM <Check className="inline size-3" aria-hidden />
              </p>
            </div>
            {buttons.filter((b) => b.text.trim()).length > 0 && (
              <div className="mt-1 space-y-1">
                {buttons
                  .filter((b) => b.text.trim())
                  .map((b, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-center gap-1.5 rounded-lg bg-[#1f2c24] py-2 text-center text-[13px] font-medium text-sky-400"
                    >
                      {b.type === "URL" && <ExternalLink className="size-3.5" aria-hidden />}
                      {b.type === "Phone number" && <Phone className="size-3.5" aria-hidden />}
                      {b.text}
                    </div>
                  ))}
              </div>
            )}
          </div>
          <p className="mt-3 text-center text-[11px] text-zinc-500">
            {nvars > 0
              ? `${nvars} variable${nvars === 1 ? "" : "s"} · fill samples to preview`
              : "No variables"}
          </p>
        </div>
      </div>
    </div>
  )
}

function AssignMenu(props: {
  property: string
  template: string
  onDone: () => void
}) {
  const [slot, setSlot] = useState("")
  return (
    <div className="flex items-center gap-1.5">
      <select
        className={inputCls}
        value={slot}
        onChange={(e) => setSlot(e.target.value)}
      >
        <option value="">Use for…</option>
        <option value="booking_confirmation">Booking confirmation</option>
        <option value="precheckin">Self check-in link</option>
        <option value="payment_request">Payment request</option>
      </select>
      <Button
        variant="outline"
        disabled={!slot}
        onClick={async () => {
          await call("kamra.whatsapp.assign_template", {
            property: props.property,
            slot,
            template_name: props.template,
          })
          props.onDone()
        }}
      >
        Wire it
      </Button>
    </div>
  )
}
