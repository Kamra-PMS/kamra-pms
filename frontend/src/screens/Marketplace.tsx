import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Check, Copy, Store, Terminal } from "lucide-react"

import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"

interface Card {
  kind: "module" | "connector" | "bench_app" | "enterprise"
  name: string
  blurb: string
  status: string
  detail?: string | null
  action?: string | null
  route?: string | null
  channel?: string | null
  key?: string
  command?: string | null
  connection?: string | null
}
interface Category {
  category: string
  blurb: string
  cards: Card[]
}

interface HeyKoalaResult {
  connection: string
  channel: string
  phone_number: string
  webhook_url: string
  webhook_secret: string
  signature_header: string
  signature_note: string
}

const STATUS_STYLE: Record<string, string> = {
  included: "bg-emerald-50 text-emerald-700",
  connected: "bg-emerald-50 text-emerald-700",
  configure: "bg-amber-50 text-amber-700",
  available: "bg-sky-50 text-sky-700",
  enterprise: "bg-violet-50 text-violet-700",
  planned: "bg-zinc-100 text-zinc-500",
}
const STATUS_LABEL: Record<string, string> = {
  included: "Included",
  connected: "Connected",
  configure: "Set up",
  available: "Available",
  enterprise: "Enterprise",
  planned: "Planned",
}

function Copyable({ value }: { value: string }) {
  const [done, setDone] = useState(false)
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(value)
        setDone(true)
        setTimeout(() => setDone(false), 1400)
      }}
      className="inline-flex items-center gap-1 text-zinc-400 hover:text-zinc-700"
      aria-label="Copy"
    >
      {done ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </button>
  )
}

export default function Marketplace() {
  const [cats, setCats] = useState<Category[]>([])
  const [error, setError] = useState<string | null>(null)
  const [wizard, setWizard] = useState<string | null>(null) // card name
  const [phone, setPhone] = useState("")
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<HeyKoalaResult | null>(null)
  const [enquired, setEnquired] = useState<Set<string>>(new Set())
  const navigate = useNavigate()
  const property = getCurrentProperty()

  const load = useCallback(() => {
    call<Category[]>("kamra.marketplace.registry", { property })
      .then(setCats)
      .catch((e) => setError(serverError(e)))
  }, [property])
  useEffect(load, [load])

  async function connectHeyKoala(channel: string) {
    setBusy(true)
    setError(null)
    try {
      const r = await call<HeyKoalaResult>(
        "kamra.marketplace.connect_heykoala",
        { property, channel, phone_number: phone.trim() },
      )
      setResult(r)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-2">
        <Store className="size-5 text-brand-600" aria-hidden />
        <h1 className="text-xl font-semibold tracking-tight">Marketplace</h1>
        <p className="ml-2 text-sm text-zinc-500">
          Your plan, plus the channels, payments, accounting and country packs
          you can plug in.
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      {cats.map((cat) => (
        <section key={cat.category} className="space-y-3">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">
              {cat.category}
            </h2>
            <p className="mt-0.5 text-xs text-zinc-400">{cat.blurb}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {cat.cards.map((c) => {
              const isKoala = c.key === "heykoala"
              return (
                <div
                  key={c.name + (c.channel ?? "")}
                  className="flex flex-col rounded-2xl border border-zinc-200 bg-white p-4"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-zinc-800">
                      {c.name}
                    </span>
                    <span
                      className={
                        "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider " +
                        (STATUS_STYLE[c.status] ?? STATUS_STYLE.planned)
                      }
                    >
                      {c.detail && c.status === "included"
                        ? c.detail
                        : STATUS_LABEL[c.status] ?? c.status}
                    </span>
                  </div>
                  <p className="mt-1 flex-1 text-sm text-zinc-500">{c.blurb}</p>

                  {c.status === "connected" && c.detail && (
                    <p className="mt-2 text-xs text-emerald-700">{c.detail}</p>
                  )}

                  {/* actions */}
                  {c.kind === "bench_app" && c.command && (
                    <div className="mt-3 flex items-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 font-mono text-xs text-zinc-100">
                      <Terminal className="size-3.5 shrink-0 text-zinc-400" />
                      <span className="truncate">{c.command}</span>
                      <span className="ml-auto">
                        <Copyable value={c.command} />
                      </span>
                    </div>
                  )}
                  {c.kind === "enterprise" && (
                    enquired.has(c.name) ? (
                      <p className="mt-3 text-sm text-violet-700">
                        Thanks - our team will reach out about {c.name}.
                      </p>
                    ) : (
                      <Button
                        variant="outline"
                        className="mt-3"
                        onClick={() =>
                          call("kamra.marketplace.enterprise_enquiry", {
                            property,
                            item: c.name,
                          }).then(() =>
                            setEnquired((s) => new Set(s).add(c.name)),
                          )
                        }
                      >
                        Request implementation
                      </Button>
                    )
                  )}
                  {c.kind === "connector" &&
                    c.action === "route" &&
                    c.route && (
                      <Button
                        variant="outline"
                        className="mt-3"
                        onClick={() => navigate(c.route!)}
                      >
                        {c.status === "connected" ? "Manage" : "Set up"}
                      </Button>
                    )}
                  {isKoala && c.status !== "connected" && (
                    <Button
                      variant="outline"
                      className="mt-3"
                      onClick={() => {
                        setWizard(c.name)
                        setResult(null)
                        setPhone("")
                      }}
                    >
                      Connect
                    </Button>
                  )}
                  {isKoala && c.status === "connected" && c.connection && (
                    <Button
                      variant="ghost"
                      className="mt-3"
                      disabled={busy}
                      onClick={() =>
                        call("kamra.marketplace.disconnect_channel", {
                          connection: c.connection,
                        }).then(load)
                      }
                    >
                      Disconnect
                    </Button>
                  )}

                  {/* HeyKoala inline wizard */}
                  {isKoala && wizard === c.name && (
                    <div className="mt-3 space-y-2 rounded-lg bg-zinc-50 p-3">
                      {!result ? (
                        <>
                          <label className="block text-xs font-medium text-zinc-600">
                            {c.channel} number
                          </label>
                          <input
                            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm"
                            placeholder="+91 80 4000 8000"
                            value={phone}
                            onChange={(e) => setPhone(e.target.value)}
                          />
                          <div className="flex gap-2">
                            <Button
                              disabled={busy || !phone.trim()}
                              onClick={() => connectHeyKoala(c.channel!)}
                            >
                              {busy ? "Connecting..." : "Connect"}
                            </Button>
                            <Button
                              variant="ghost"
                              onClick={() => setWizard(null)}
                            >
                              Cancel
                            </Button>
                          </div>
                        </>
                      ) : (
                        <div className="space-y-2 text-xs">
                          <p className="font-medium text-emerald-700">
                            Connected. Paste these into HeyKoala:
                          </p>
                          <div>
                            <div className="text-zinc-500">Webhook URL</div>
                            <div className="flex items-center gap-1 break-all font-mono text-zinc-700">
                              {result.webhook_url}
                              <Copyable value={result.webhook_url} />
                            </div>
                          </div>
                          <div>
                            <div className="text-zinc-500">
                              Secret (shown once)
                            </div>
                            <div className="flex items-center gap-1 break-all font-mono text-zinc-700">
                              {result.webhook_secret}
                              <Copyable value={result.webhook_secret} />
                            </div>
                          </div>
                          <p className="text-zinc-400">
                            {result.signature_note} Goes live once HeyKoala
                            confirms.
                          </p>
                          <Button
                            variant="ghost"
                            onClick={() => setWizard(null)}
                          >
                            Done
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}
