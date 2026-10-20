import { useCallback, useEffect, useMemo, useState } from "react"
import { KeyRound, Search, UserPlus } from "lucide-react"

import { Badge } from "../../components/ui/badge"
import { Button } from "../../components/ui/button"
import { Card } from "../../components/ui/card"
import { Sheet } from "../../components/ui/sheet"
import { myProperties, type PropertyRow } from "../../lib/api"
import { APPS } from "../../lib/apps"
import { useT } from "../../lib/i18n"
import { serverError } from "../../lib/resource"
import { cn } from "../../lib/utils"
import {
  listStaff,
  resetCashierPin,
  saveStaff,
  setModuleEnabled,
  staffRoles,
  type RoleInfo,
  type SettingsModule,
  type StaffInput,
  type StaffRow,
} from "./api"
import { inputCls, Switch } from "./ModulePage"

const ADMIN_ROLES = ["Hotel Admin", "System Manager", "Administrator"]

const initials = (name: string) =>
  name.split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("") || "?"

function lastSeen(d: string | null): { key: string; n?: number; date?: string } {
  if (!d) return { key: "Never signed in" }
  const dt = new Date(d.replace(" ", "T"))
  const days = Math.floor((Date.now() - dt.getTime()) / 86_400_000)
  if (days <= 0) return { key: "Active today" }
  if (days === 1) return { key: "Active yesterday" }
  if (days < 30) return { key: "Active {n} days ago", n: days }
  return {
    key: "Last active {date}",
    date: dt.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }),
  }
}

// --- Staff -------------------------------------------------------------------

export function StaffPage() {
  const { t } = useT()
  const [rows, setRows] = useState<StaffRow[] | null>(null)
  const [roles, setRoles] = useState<RoleInfo[]>([])
  const [props, setProps] = useState<PropertyRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState("")
  const [roleFilter, setRoleFilter] = useState("")
  const [showInactive, setShowInactive] = useState(false)
  const [editing, setEditing] = useState<StaffRow | "new" | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(() => {
    listStaff().then(setRows).catch((e) => setError(serverError(e)))
  }, [])
  useEffect(() => {
    load()
    staffRoles().then(setRoles).catch(() => setRoles([]))
    myProperties().then(setProps).catch(() => setProps([]))
  }, [load])

  const roleLabel = useCallback(
    (r: string) => roles.find((x) => x.role === r)?.label ?? r,
    [roles],
  )

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return (rows ?? []).filter(
      (r) =>
        (showInactive || Boolean(Number(r.enabled))) &&
        (!roleFilter || r.roles.includes(roleFilter)) &&
        (!needle ||
          r.full_name.toLowerCase().includes(needle) ||
          r.email.toLowerCase().includes(needle)),
    )
  }, [rows, q, roleFilter, showInactive])

  const inactive = (rows ?? []).filter((r) => !Number(r.enabled)).length

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1">
          <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
          <input
            className={cn(inputCls, "ps-9")}
            placeholder={t("Search name or email")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label={t("Search staff")}
          />
        </div>
        <select
          className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          aria-label={t("Filter by role")}
        >
          <option value="">{t("All roles")}</option>
          {roles.map((r) => (
            <option key={r.role} value={r.role}>{t(r.label)}</option>
          ))}
        </select>
        <Button onClick={() => setEditing("new")}>
          <UserPlus className="size-4" aria-hidden />
          {t("Add staff")}
        </Button>
      </div>

      {notice && (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>
      )}
      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">{error}</p>}

      <Card className="overflow-hidden">
        {rows === null ? (
          <p className="py-10 text-center text-sm text-zinc-400">{t("Loading…")}</p>
        ) : shown.length === 0 ? (
          <p className="py-10 text-center text-sm text-zinc-400">{t("No one matches.")}</p>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {shown.map((r) => {
              const seen = lastSeen(r.last_active || r.last_login)
              return (
                <li
                  key={r.user}
                  className={cn(
                    "grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 px-4 py-3",
                    "md:grid-cols-[auto_minmax(0,14rem)_minmax(0,1fr)_9.5rem_auto]",
                    !Number(r.enabled) && "opacity-60",
                  )}
                >
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700 ring-1 ring-brand-100">
                    {initials(r.full_name || r.email)}
                  </span>
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 truncate text-sm font-medium text-zinc-900">
                      {r.full_name || r.email}
                      {r.is_self && <Badge tone="zinc">{t("You")}</Badge>}
                      {!Number(r.enabled) && <Badge tone="zinc">{t("Deactivated")}</Badge>}
                    </p>
                    <p className="truncate text-xs text-zinc-500">{r.email}</p>
                  </div>
                  <div className="col-span-2 col-start-2 row-start-2 flex min-w-0 flex-wrap gap-1 md:col-span-1 md:col-start-auto md:row-start-auto">
                    {r.roles.length ? (
                      r.roles.map((role) => (
                        <Badge key={role} tone={ADMIN_ROLES.includes(role) ? "brand" : "zinc"}>
                          {t(roleLabel(role))}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-xs text-zinc-400">{t("No role")}</span>
                    )}
                  </div>
                  <div className="hidden text-xs text-zinc-500 md:block">
                    <p>
                      {r.properties === null
                        ? t("All properties")
                        : r.properties.length === 1
                          ? t("1 property")
                          : t("{n} properties", { n: r.properties.length })}
                    </p>
                    <p className="text-zinc-400">{t(seen.key, { n: seen.n ?? 0, date: seen.date ?? "" })}</p>
                  </div>
                  <div className="flex items-center justify-end gap-1">
                    {r.pin === "reset" && <Badge tone="amber">{t("PIN reset")}</Badge>}
                    {r.pin === "set" && !r.is_self && r.editable && (
                      <button
                        type="button"
                        title={t("Reset cashier PIN")}
                        aria-label={t("Reset cashier PIN")}
                        onClick={async () => {
                          const name = r.full_name || r.email
                          if (!confirm(t("Reset {name}'s cashier PIN? They set a new one on their next money action.", { name }))) return
                          try {
                            await resetCashierPin(r.user)
                            setNotice(t("PIN reset for {name}.", { name }))
                            load()
                          } catch (e) {
                            setError(serverError(e))
                          }
                        }}
                        className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
                      >
                        <KeyRound className="size-4" aria-hidden />
                      </button>
                    )}
                    <Button
                      variant="outline"
                      disabled={!r.editable}
                      onClick={() => setEditing(r)}
                      title={
                        r.editable
                          ? undefined
                          : r.is_self
                            ? t("You can't change your own access")
                            : t("Only IT can change this person")
                      }
                    >
                      {t("Manage")}
                    </Button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
      {inactive > 0 && (
        <button
          type="button"
          className="text-xs text-zinc-500 hover:text-zinc-800"
          onClick={() => setShowInactive((v) => !v)}
        >
          {showInactive ? t("Hide deactivated staff") : t("Show {n} deactivated", { n: inactive })}
        </button>
      )}

      {editing && (
        <StaffSheet
          row={editing === "new" ? null : editing}
          roles={roles}
          properties={props}
          onClose={() => setEditing(null)}
          onSaved={(name) => {
            setEditing(null)
            setNotice(t("Saved access for {name}.", { name }))
            load()
          }}
        />
      )}
    </div>
  )
}

function StaffSheet({
  row, roles, properties, onClose, onSaved,
}: {
  row: StaffRow | null
  roles: RoleInfo[]
  properties: PropertyRow[]
  onClose: () => void
  onSaved: (name: string) => void
}) {
  const { t } = useT()
  const [f, setF] = useState<StaffInput>({
    email: row?.email ?? "",
    full_name: row?.full_name ?? "",
    roles: row?.roles ?? [],
    properties: row ? row.properties : null,
    enabled: row ? Boolean(Number(row.enabled)) : true,
    send_welcome: false,
  })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const all = f.properties === null

  const toggleRole = (r: string) =>
    setF((s) => ({ ...s, roles: s.roles.includes(r) ? s.roles.filter((x) => x !== r) : [...s.roles, r] }))
  const toggleProp = (p: string) =>
    setF((s) => {
      const cur = s.properties ?? []
      return { ...s, properties: cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p] }
    })

  const invalid =
    !f.email.trim() || !f.full_name.trim() || f.roles.length === 0 ||
    (f.properties !== null && f.properties.length === 0)

  async function submit() {
    setBusy(true)
    setErr(null)
    try {
      await saveStaff(f)
      onSaved(f.full_name || f.email)
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet
      title={row ? t("Manage access") : t("Add staff")}
      description={row ? row.email : t("They sign in with this email.")}
      onClose={onClose}
      footer={
        <div className="flex w-full items-center gap-2">
          {err && <p className="flex-1 text-sm text-rose-600">{err}</p>}
          <Button variant="ghost" className="ms-auto" onClick={onClose}>{t("Cancel")}</Button>
          <Button disabled={busy || invalid} onClick={submit}>
            {busy ? t("Saving…") : row ? t("Save") : t("Add staff")}
          </Button>
        </div>
      }
    >
      <div className="space-y-6">
        <div className="space-y-3">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-zinc-700">{t("Full name")}</span>
            <input className={inputCls} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-zinc-700">{t("Email")}</span>
            <input
              className={inputCls}
              type="email"
              value={f.email}
              disabled={!!row}
              onChange={(e) => setF({ ...f, email: e.target.value })}
            />
          </label>
        </div>

        <fieldset>
          <legend className="mb-2 text-sm font-semibold text-zinc-900">{t("Roles")}</legend>
          <div className="space-y-2">
            {roles.map((r) => {
              const on = f.roles.includes(r.role)
              return (
                <label
                  key={r.role}
                  className={cn(
                    "flex gap-3 rounded-lg border px-3 py-2.5",
                    on ? "border-brand-300 bg-brand-50/50" : "border-zinc-200",
                    r.assignable ? "cursor-pointer" : "cursor-not-allowed opacity-60",
                  )}
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 size-4 accent-brand-600"
                    checked={on}
                    disabled={!r.assignable}
                    onChange={() => toggleRole(r.role)}
                  />
                  <span>
                    <span className="block text-sm font-medium text-zinc-800">{t(r.label)}</span>
                    <span className="block text-xs text-zinc-500">{t(r.description)}</span>
                  </span>
                </label>
              )
            })}
          </div>
        </fieldset>

        <fieldset>
          <legend className="mb-2 text-sm font-semibold text-zinc-900">{t("Property access")}</legend>
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm text-zinc-700">
              <input
                type="radio"
                className="accent-brand-600"
                checked={all}
                onChange={() => setF({ ...f, properties: null })}
              />
              {t("All properties, including ones added later")}
            </label>
            <label className="flex items-center gap-2 text-sm text-zinc-700">
              <input
                type="radio"
                className="accent-brand-600"
                checked={!all}
                onChange={() =>
                  setF({ ...f, properties: row?.properties ?? properties.slice(0, 1).map((p) => p.name) })
                }
              />
              {t("Only these properties")}
            </label>
            {!all && (
              <div className="ms-6 space-y-1.5">
                {properties.map((p) => (
                  <label key={p.name} className="flex items-center gap-2 text-sm text-zinc-700">
                    <input
                      type="checkbox"
                      className="size-4 accent-brand-600"
                      checked={(f.properties ?? []).includes(p.name)}
                      onChange={() => toggleProp(p.name)}
                    />
                    {p.property_name}
                    {p.city && <span className="text-xs text-zinc-400">· {p.city}</span>}
                  </label>
                ))}
              </div>
            )}
          </div>
        </fieldset>

        {row ? (
          <label className="flex items-start gap-3 rounded-lg border border-zinc-200 px-3 py-2.5">
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-brand-600"
              checked={f.enabled}
              onChange={(e) => setF({ ...f, enabled: e.target.checked })}
            />
            <span>
              <span className="block text-sm font-medium text-zinc-800">{t("Active")}</span>
              <span className="block text-xs text-zinc-500">{t("Deactivated staff can't sign in. Their history stays.")}</span>
            </span>
          </label>
        ) : (
          <label className="flex items-start gap-3 rounded-lg border border-zinc-200 px-3 py-2.5">
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-brand-600"
              checked={f.send_welcome}
              onChange={(e) => setF({ ...f, send_welcome: e.target.checked })}
            />
            <span>
              <span className="block text-sm font-medium text-zinc-800">{t("Email them a link to set a password")}</span>
              <span className="block text-xs text-zinc-500">{t("Leave off to share access yourself.")}</span>
            </span>
          </label>
        )}
      </div>
    </Sheet>
  )
}

// --- Modules on/off ----------------------------------------------------------

export function ModulesPage({
  modules, canToggle, onChanged,
}: {
  modules: SettingsModule[]
  canToggle: boolean
  onChanged: () => void
}) {
  const { t } = useT()
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const blurb = (id: string, fallback: string) => APPS.find((a) => a.id === id)?.description ?? fallback

  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-sm text-zinc-600">
        {t("Switch off what this property doesn't run. Its apps leave the launcher, search and the AI agent's tools for everyone. Data is kept and comes back when you switch it on.")}
      </p>
      {err && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">{err}</p>}
      <Card className="divide-y divide-zinc-100">
        {[
          { id: "front-desk", title: "Front Desk" },
          { id: "admin", title: "Admin" },
        ].map((m) => (
          <div key={m.id} className="flex items-center gap-4 px-5 py-4">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-zinc-800">{t(m.title)}</p>
              <p className="text-xs text-zinc-500">{t(blurb(m.id, ""))}</p>
            </div>
            <Badge tone="zinc">{t("Always on")}</Badge>
          </div>
        ))}
        {modules.filter((m) => m.toggle).map((m) => (
          <div key={m.id} className="flex items-center gap-4 px-5 py-4">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-zinc-800">{t(m.title)}</p>
              <p className="text-xs text-zinc-500">{t(blurb(m.id, m.description))}</p>
            </div>
            <Switch
              on={m.enabled}
              label={t(m.title)}
              disabled={!canToggle || busy === m.id}
              onToggle={async () => {
                if (m.enabled && !confirm(t("Switch off {name} for this property?", { name: t(m.title) }))) return
                setBusy(m.id)
                setErr(null)
                try {
                  await setModuleEnabled(m.id, !m.enabled)
                  window.dispatchEvent(new Event("kamra:modules-changed"))
                  onChanged()
                } catch (e) {
                  setErr(serverError(e))
                } finally {
                  setBusy(null)
                }
              }}
            />
          </div>
        ))}
      </Card>
      {!canToggle && <p className="text-xs text-zinc-400">{t("Only Hotel Admin can switch modules.")}</p>}
    </div>
  )
}
