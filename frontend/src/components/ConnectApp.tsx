import { useCallback, useEffect, useState } from "react"
import { Check, Copy, PlugZap, ShieldAlert, ShieldCheck } from "lucide-react"

import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "./ui/button"
import ConnectedAppIcon from "./ConnectedAppIcon"
import { useT, t as translate } from "../lib/i18n"

interface Preview {
  app_id: string
  name: string
  icon?: string
  url: string
  manifest_url: string
  signed: boolean
  redirect_uri?: string
  roles: string[]
  scopes: { scope: string; label: string }[]
  properties: { name: string; property_name: string }[]
  status?: string | null
}
interface Code {
  app_id: string
  code: string
  expires_at: string
  pair_link?: string
}
interface AppRow {
  app_id: string
  app_name: string
  status: "Pending" | "Paired" | "Disconnected"
  url: string
  icon?: string
  scopes: string[]
  properties: string[]
  roles: string[]
  signed: number
}
interface Registry {
  apps: AppRow[]
  unsigned_allowed: boolean
  trusted_keys: number
}

function CopyCode({ value }: { value: string }) {
  const { t } = useT()
  const [done, setDone] = useState(false)
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(value)
        setDone(true)
        setTimeout(() => setDone(false), 1400)
      }}
      className="inline-flex items-center text-zinc-400 hover:text-zinc-700"
      aria-label={t("Copy")}
    >
      {done ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </button>
  )
}

const toggle = (list: string[], value: string) =>
  list.includes(value) ? list.filter((v) => v !== value) : [...list, value]

/** Marketplace, Connected apps (IT only): read an app's signed manifest,
 *  consent to its scopes and properties, hand over a one-time pairing code,
 *  and disconnect. */
export default function ConnectApp() {
  const { t } = useT()
  const [reg, setReg] = useState<Registry | null>(null)
  const [url, setUrl] = useState("")
  const [preview, setPreview] = useState<Preview | null>(null)
  const [scopes, setScopes] = useState<string[]>([])
  const [props, setProps] = useState<string[]>([])
  const [code, setCode] = useState<Code | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    call<Registry>("kamra.apps.list_apps")
      .then(setReg)
      .catch((e) => setError(serverError(e)))
  }, [])
  useEffect(load, [load])

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true)
    setError(null)
    try {
      return await fn()
    } catch (e) {
      setError(serverError(e))
      return undefined
    } finally {
      setBusy(false)
    }
  }

  async function check() {
    setCode(null)
    const p = await run(() => call<Preview>("kamra.apps.preview", { app_url: url.trim() }))
    if (!p) return
    setPreview(p)
    setScopes(p.scopes.map((s) => s.scope))
    const here = getCurrentProperty()
    setProps(p.properties.some((x) => x.name === here) && here ? [here] : [])
  }

  async function approve() {
    const c = await run(() =>
      call<Code>("kamra.apps.connect", { app_url: url.trim(), scopes, properties: props }),
    )
    if (!c) return
    setCode(c)
    setPreview(null)
    load()
  }

  const apps = (reg?.apps ?? []).filter((a) => a.status !== "Disconnected")

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">
          {t("Connected apps")}
        </h2>
        <p className="mt-0.5 text-xs text-zinc-400">
          {t("Add-on apps on their own site. Each gets its own key, limited to the scopes and properties you approve.")}
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {translate(error)}
        </div>
      )}

      <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4">
        <label className="block text-xs font-medium text-zinc-600" htmlFor="app-url">
          {t("App address")}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id="app-url"
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm"
            placeholder="https://"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <Button disabled={busy || !url.trim()} onClick={check}>
            <PlugZap className="size-4" aria-hidden />
            {t("Connect")}
          </Button>
        </div>
        <label className="flex items-center gap-2 text-xs text-zinc-500">
          <input
            type="checkbox"
            checked={!!reg?.unsigned_allowed}
            disabled={busy || !reg}
            onChange={(e) =>
              run(() => call("kamra.apps.set_trust", { unsigned: e.target.checked ? 1 : 0 })).then(load)
            }
          />
          {t("Allow unsigned apps (self-hosted apps you run yourself)")}
        </label>

        {preview && (
          <div className="space-y-3 rounded-lg bg-zinc-50 p-3">
            <div className="flex items-center gap-3">
              <span className="flex size-9 items-center justify-center rounded-md border border-zinc-200 bg-white text-zinc-600">
                <ConnectedAppIcon src={preview.icon} />
              </span>
              <div className="min-w-0">
                <div className="font-semibold text-zinc-800">{preview.name}</div>
                <div className="truncate text-xs text-zinc-500">{preview.url}</div>
              </div>
            </div>
            {preview.signed ? (
              <p className="flex items-center gap-1.5 text-xs text-emerald-700">
                <ShieldCheck className="size-3.5" aria-hidden />
                {t("Signed by a trusted publisher.")}
              </p>
            ) : (
              <p className="flex items-center gap-1.5 text-xs text-amber-700">
                <ShieldAlert className="size-3.5" aria-hidden />
                {t("Not signed. Connect it only if you run this app yourself.")}
              </p>
            )}

            <fieldset className="space-y-1">
              <legend className="text-xs font-medium text-zinc-600">{t("It asks to")}</legend>
              {preview.scopes.map((s) => (
                <label key={s.scope} className="flex items-start gap-2 text-sm text-zinc-700">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={scopes.includes(s.scope)}
                    onChange={() => setScopes((x) => toggle(x, s.scope))}
                  />
                  <span>
                    {translate(s.label)} <span className="font-mono text-xs text-zinc-400">{s.scope}</span>
                  </span>
                </label>
              ))}
            </fieldset>

            <fieldset className="space-y-1">
              <legend className="text-xs font-medium text-zinc-600">{t("For these properties")}</legend>
              {preview.properties.map((p) => (
                <label key={p.name} className="flex items-center gap-2 text-sm text-zinc-700">
                  <input
                    type="checkbox"
                    checked={props.includes(p.name)}
                    onChange={() => setProps((x) => toggle(x, p.name))}
                  />
                  {p.property_name}
                </label>
              ))}
            </fieldset>

            {preview.redirect_uri && (
              <p className="text-xs text-zinc-500">
                {t("Staff sign in to it with their own Kamra login, through {uri}.", {
                  uri: preview.redirect_uri,
                })}
              </p>
            )}
            {preview.status && preview.status !== "Disconnected" && (
              <p className="text-xs text-amber-700">
                {t("Already connected. Disconnect it below first.")}
              </p>
            )}
            <div className="flex gap-2">
              <Button disabled={busy || !scopes.length || !props.length} onClick={approve}>
                {t("Approve and connect")}
              </Button>
              <Button variant="ghost" onClick={() => setPreview(null)}>
                {t("Cancel")}
              </Button>
            </div>
          </div>
        )}

        {code && (
          <div className="space-y-2 rounded-lg bg-emerald-50 p-3 text-sm">
            <p className="font-medium text-emerald-800">
              {t("Enter this pairing code in the app. It works once, for 10 minutes.")}
            </p>
            <div className="flex items-center gap-2 font-mono text-lg tracking-widest text-zinc-900">
              {code.code}
              <CopyCode value={code.code} />
            </div>
            {code.pair_link && (
              <a
                href={code.pair_link}
                target="_blank"
                rel="noreferrer"
                className="text-xs font-medium text-emerald-800 underline"
              >
                {t("Open the app with the code filled in")}
              </a>
            )}
          </div>
        )}
      </div>

      {apps.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {apps.map((a) => (
            <div key={a.app_id} className="flex flex-col rounded-2xl border border-zinc-200 bg-white p-4">
              <div className="flex items-start justify-between gap-2">
                <span className="flex items-center gap-2 font-semibold text-zinc-800">
                  <ConnectedAppIcon src={a.icon} />
                  {a.app_name}
                </span>
                <span
                  className={
                    "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider " +
                    (a.status === "Paired" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700")
                  }
                >
                  {a.status === "Paired" ? t("Connected") : t("Waiting to pair")}
                </span>
              </div>
              <p className="mt-1 flex-1 text-xs text-zinc-500">
                <span className="font-mono">{a.scopes.join(", ")}</span>
                <br />
                {a.properties.join(", ")}
              </p>
              <div className="mt-3 flex gap-2">
                {a.status === "Pending" && (
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() =>
                      run(() => call<Code>("kamra.apps.new_pairing_code", { app_id: a.app_id })).then(
                        (c) => c && setCode(c),
                      )
                    }
                  >
                    {t("New pairing code")}
                  </Button>
                )}
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={() => {
                    if (!window.confirm(t("Disconnect {name}? Its key stops working at once.", { name: a.app_name })))
                      return
                    run(() => call("kamra.apps.disconnect", { app_id: a.app_id })).then(load)
                  }}
                >
                  {t("Disconnect")}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
