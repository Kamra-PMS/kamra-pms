import { useCallback, useEffect, useState } from "react"

import { Button } from "../../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card"
import { call } from "../../lib/api"
import { useT } from "../../lib/i18n"
import { serverError } from "../../lib/resource"
import { Switch } from "./ModulePage"

/** Settings → Usage reporting (#657): the anonymous daily heartbeat (on by
 *  default, one click off, shows exactly what it sends) and the separate,
 *  opt-in property registration. Backend: kamra.telemetry (admins only). */

export interface Registration {
  property_name: string
  city: string
  country: string
  room_count: number
  contact_email: string
  list_publicly: boolean
}

interface Status {
  enabled: boolean
  disabled_by_config: boolean
  endpoint: string
  payload: Record<string, unknown>
  registration: Registration | null
}

const M = "kamra.telemetry."
const EMPTY: Registration = {
  property_name: "", city: "", country: "", room_count: 0, contact_email: "", list_publicly: false,
}

export function UsageReportingPage() {
  const { t } = useT()
  const [status, setStatus] = useState<Status | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(() => {
    call<Status>(`${M}telemetry_status`).then(setStatus, (e) => setError(serverError(e)))
  }, [])
  useEffect(load, [load])

  if (error) return <p className="text-sm text-rose-700">{error}</p>
  if (!status) return <p className="text-sm text-zinc-500">{t("Loading…")}</p>

  async function toggle() {
    try {
      setStatus(await call<Status>(`${M}set_telemetry`, { enabled: status!.enabled ? 0 : 1 }))
    } catch (e) {
      setError(serverError(e))
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("Anonymous usage heartbeat")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex items-start justify-between gap-4">
            <p className="text-zinc-600">
              {t("Once a day Kamra tells kamrapms.com that this install exists, so we can count how many hotels run Kamra. No guest data, hotel name, domain, revenue or emails are sent, and nothing is ever blocked if it fails.")}
            </p>
            <Switch
              on={status.enabled}
              onToggle={toggle}
              disabled={status.disabled_by_config}
              label="Anonymous usage heartbeat"
            />
          </div>
          {status.disabled_by_config && (
            <p className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-zinc-600">
              {t("Turned off by the server's configuration (KAMRA_TELEMETRY, DO_NOT_TRACK or kamra_telemetry in site config).")}
            </p>
          )}
          <details>
            <summary className="cursor-pointer font-medium text-brand-700">{t("See exactly what we send")}</summary>
            <p className="mt-2 text-xs text-zinc-500">{status.endpoint}</p>
            <pre className="mt-1 overflow-x-auto rounded-lg bg-zinc-900 p-3 font-mono text-xs text-zinc-100">
              {JSON.stringify(status.payload, null, 2)}
            </pre>
          </details>
        </CardContent>
      </Card>
      <RegistrationCard registration={status.registration} onChanged={load} />
    </div>
  )
}

/** The opt-in registration form. Used here and, with `initial`, by the setup wizard. */
export function RegistrationForm({
  initial, onSaved, onRemoved, registered,
}: {
  initial: Registration
  onSaved?: (sent: boolean) => void
  onRemoved?: (sent: boolean) => void
  registered?: boolean
}) {
  const { t } = useT()
  const [reg, setReg] = useState<Registration>(initial)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const set = <K extends keyof Registration>(k: K, v: Registration[K]) => setReg((r) => ({ ...r, [k]: v }))

  async function run(method: string, params: Record<string, unknown>, done?: (sent: boolean) => void) {
    setBusy(true)
    setNote(null)
    try {
      const out = await call<{ sent: boolean }>(`${M}${method}`, params)
      if (!out.sent) setNote(t("Saved here, but kamrapms.com could not be reached. Try again later."))
      done?.(out.sent)
    } catch (e) {
      setNote(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const field = (k: "property_name" | "city" | "country" | "contact_email", label: string, type = "text") => (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-medium text-zinc-500">{t(label)}</span>
      <input
        type={type}
        value={reg[k]}
        onChange={(e) => set(k, e.target.value)}
        className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm"
      />
    </label>
  )

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {field("property_name", "Property name")}
        {field("contact_email", "Contact email", "email")}
        {field("city", "City")}
        {field("country", "Country")}
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Rooms")}</span>
          <input
            type="number"
            min={0}
            value={reg.room_count || ""}
            onChange={(e) => set("room_count", Number(e.target.value) || 0)}
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm"
          />
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={reg.list_publicly} onChange={(e) => set("list_publicly", e.target.checked)} />
        {t("List us on kamrapms.com as a Kamra property")}
      </label>
      {note && <p className="text-sm text-amber-700">{note}</p>}
      <div className="flex gap-2">
        <Button
          disabled={busy || !reg.property_name.trim() || !reg.contact_email.trim()}
          onClick={() => run("save_registration", { ...reg, list_publicly: reg.list_publicly ? 1 : 0 }, onSaved)}
        >
          {registered ? t("Update registration") : t("Register this property")}
        </Button>
        {registered && (
          <Button variant="outline" disabled={busy} onClick={() => run("remove_registration", {}, onRemoved)}>
            {t("Remove registration")}
          </Button>
        )}
      </div>
    </div>
  )
}

function RegistrationCard({ registration, onChanged }: { registration: Registration | null; onChanged: () => void }) {
  const { t } = useT()
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("Register your property (optional)")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-zinc-600">
          {t("Separate from the heartbeat, and only if you want to: tell us who you are. We name your hotel on kamrapms.com only when you tick the box. You can change or remove this any time.")}
        </p>
        <RegistrationForm
          key={registration ? "registered" : "new"}
          initial={registration ?? EMPTY}
          registered={!!registration}
          onSaved={onChanged}
          onRemoved={onChanged}
        />
      </CardContent>
    </Card>
  )
}

/** The setup wizard's disclosure: the heartbeat is on, here is what it
 *  sends, one click turns it off; and the optional registration, filled
 *  from what the wizard already knows. Shown after the property is created
 *  (guided Import step and Finish setup). Renders nothing for non-admins. */
export function UsageSetupCard({ prefill }: { prefill: Partial<Registration> }) {
  const { t } = useT()
  const [status, setStatus] = useState<Status | null>(null)
  const [done, setDone] = useState(false)
  useEffect(() => {
    call<Status>(`${M}telemetry_status`).then(setStatus, () => setStatus(null))
  }, [])
  if (!status) return null

  async function toggle() {
    try {
      setStatus(await call<Status>(`${M}set_telemetry`, { enabled: status!.enabled ? 0 : 1 }))
    } catch {
      // the switch stays as it was; Settings → Usage reporting has it too
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-semibold text-zinc-800">{t("Anonymous usage heartbeat")}</p>
          <p className="mt-1 text-zinc-600">
            {t("Once a day Kamra tells kamrapms.com that this install exists, so we can count how many hotels run Kamra. No guest data, hotel name, domain, revenue or emails are sent, and nothing is ever blocked if it fails.")}
          </p>
        </div>
        <Switch on={status.enabled} onToggle={toggle} disabled={status.disabled_by_config} label="Anonymous usage heartbeat" />
      </div>
      <details>
        <summary className="cursor-pointer font-medium text-brand-700">{t("See exactly what we send")}</summary>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-zinc-900 p-3 font-mono text-xs text-zinc-100">
          {JSON.stringify(status.payload, null, 2)}
        </pre>
      </details>
      {!status.registration && !done && (
        <details>
          <summary className="cursor-pointer font-medium text-brand-700">{t("Register your property (optional)")}</summary>
          <p className="mt-2 text-zinc-600">
            {t("Separate from the heartbeat, and only if you want to: tell us who you are. We name your hotel on kamrapms.com only when you tick the box. You can change or remove this any time.")}
          </p>
          <div className="mt-2">
            <RegistrationForm initial={{ ...EMPTY, ...prefill }} onSaved={() => setDone(true)} />
          </div>
        </details>
      )}
      {done && <p className="text-emerald-700">{t("Thank you. You can change this in Settings → Usage reporting.")}</p>}
    </div>
  )
}
