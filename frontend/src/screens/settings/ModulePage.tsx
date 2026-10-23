import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowUpRight, Lock, RotateCcw } from "lucide-react"

import ImageField from "../../components/ImageField"
import { Card } from "../../components/ui/card"
import { useT, t as translate, useUILanguage } from "../../lib/i18n"
import { cur } from "../../lib/money"
import { serverError } from "../../lib/resource"
import { cn } from "../../lib/utils"
import { saveSettings, type SettingSpec, type SettingsModule } from "./api"


export const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 " +
  "disabled:cursor-not-allowed disabled:bg-zinc-50 disabled:text-zinc-500"

/** Money amounts carry the property currency instead of a unit. */
const MONEY_KEYS = new Set([
  "security_deposit_amount", "gst_slab_threshold", "cleaning_fee",
  "registration_fee", "max_cash_refund", "pet_charge",
])

export interface OptionSources {
  countries: string[]
  timezones: string[]
}

const same = (a: unknown, b: unknown) =>
  String(a ?? "") === String(b ?? "") ||
  (typeof b === "number" && a !== null && a !== "" && Number(a) === b)

export function Switch({
  on, onToggle, disabled, label, id,
}: {
  on: boolean
  onToggle: () => void
  disabled?: boolean
  label?: string
  id?: string
}) {
  useUILanguage()
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={translate(label)}
      disabled={disabled}
      onClick={onToggle}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600",
        "disabled:cursor-not-allowed disabled:opacity-60",
        on ? "bg-brand-600" : "bg-zinc-300",
      )}
    >
      <span
        className={cn(
          "inline-block size-5 rounded-full bg-white shadow transition-transform",
          on ? "translate-x-5.5 rtl:-translate-x-5.5" : "translate-x-0.5 rtl:-translate-x-0.5",
        )}
      />
    </button>
  )
}

function Control({
  spec, value, disabled, onChange, sources,
}: {
  spec: SettingSpec
  value: unknown
  disabled: boolean
  onChange: (v: unknown) => void
  sources: OptionSources
}) {
  const { t } = useT()
  const id = `setting-${spec.key}`
  if (spec.type === "check")
    return (
      <Switch
        id={id}
        on={Boolean(Number(value ?? 0))}
        disabled={disabled}
        onToggle={() => onChange(Number(value ?? 0) ? 0 : 1)}
      />
    )
  if (spec.type === "image")
    return <ImageField hint="" value={String(value ?? "")} onChange={(v) => onChange(v)} />
  if (spec.type === "select") {
    let options = spec.options ?? []
    if (spec.options_source) options = sources[spec.options_source]
    const v = String(value ?? "")
    if (v && !options.includes(v)) options = [v, ...options]
    return (
      <select
        id={id}
        className={inputCls}
        value={v}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      >
        {!v && <option value="">-</option>}
        {options.map((o) => (
          <option key={o} value={o}>
            {o ? t(o) : "-"}
          </option>
        ))}
      </select>
    )
  }
  if (spec.type === "textarea")
    return (
      <textarea
        id={id}
        className={`${inputCls} min-h-24`}
        value={String(value ?? "")}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    )
  if (spec.type === "number") {
    const unit = MONEY_KEYS.has(spec.key) ? cur() : spec.unit
    return (
      <div className="flex items-center gap-2">
        <input
          id={id}
          type="number"
          inputMode="decimal"
          className={cn(inputCls, "max-w-36 tabular-nums")}
          value={value === null || value === undefined ? "" : String(value)}
          min={spec.min}
          max={spec.max}
          step="any"
          disabled={disabled}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        />
        {unit && <span className="text-sm text-zinc-500">{t(unit)}</span>}
      </div>
    )
  }
  return (
    <input
      id={id}
      type={spec.type === "time" ? "time" : spec.type === "email" ? "email" : "text"}
      className={cn(inputCls, spec.type === "time" && "max-w-36")}
      value={String(value ?? "")}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

function SettingRow({
  spec, value, saved, disabled, highlight, onChange, sources, taxIdLabel,
}: {
  spec: SettingSpec
  value: unknown
  saved: unknown
  disabled: boolean
  highlight: boolean
  onChange: (v: unknown) => void
  sources: OptionSources
  taxIdLabel?: string
}) {
  const { t } = useT()
  const dirty = !same(value, saved)
  const hasDefault = spec.default !== null && spec.default !== undefined && spec.default !== ""
  const offDefault = hasDefault && !same(value, spec.default)
  const label = spec.key === "gstin" && taxIdLabel ? taxIdLabel : spec.label
  const fmtDefault = (d: unknown) =>
    spec.type === "check"
      ? Number(d) ? t("On") : t("Off")
      : `${String(d)}${spec.unit && spec.type === "number" ? ` ${t(spec.unit)}` : ""}`
  return (
    <div
      id={`row-${spec.key}`}
      className={cn(
        "grid scroll-mt-24 gap-x-8 gap-y-2 px-5 py-4 transition-colors md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]",
        highlight && "bg-brand-50/70",
      )}
    >
      <div className="min-w-0">
        <label htmlFor={`setting-${spec.key}`} className="flex items-center gap-2 text-sm font-medium text-zinc-800">
          {t(label)}
          {dirty && (
            <span className="size-1.5 rounded-full bg-amber-500" title={t("Unsaved")} />
          )}
        </label>
        {spec.hint && <p className="mt-0.5 text-xs leading-relaxed text-zinc-500">{t(spec.hint)}</p>}
      </div>
      <div className="min-w-0">
        <Control spec={spec} value={value} disabled={disabled} onChange={onChange} sources={sources} />
        {offDefault && !disabled && (
          <button
            type="button"
            onClick={() => onChange(spec.default)}
            className="mt-1.5 inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-brand-700"
          >
            <RotateCcw className="size-3" aria-hidden />
            {t("Reset to default ({value})", { value: fmtDefault(spec.default) })}
          </button>
        )}
      </div>
    </div>
  )
}

export function ModulePage({
  module, sources, focusKey, taxIdLabel, onSaved, onDirtyChange, children,
}: {
  module: SettingsModule
  sources: OptionSources
  focusKey?: string | null
  taxIdLabel?: string
  onSaved: (values: Record<string, unknown>) => void
  onDirtyChange: (dirty: boolean) => void
  /** extra cards a module owns (rate cards, hurdle tiers) */
  children?: React.ReactNode
}) {
  const { t } = useT()
  const [draft, setDraft] = useState<Record<string, unknown>>({})
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const readOnly = !module.can_edit

  // another page drops the draft (save clears it itself)
  useEffect(() => {
    setDraft({})
    setMsg(null)
  }, [module.id])

  const changed = useMemo(
    () => Object.keys(draft).filter((k) => !same(draft[k], module.values[k])),
    [draft, module.values],
  )
  useEffect(() => onDirtyChange(changed.length > 0), [changed.length, onDirtyChange])

  useEffect(() => {
    if (!focusKey) return
    document.getElementById(`row-${focusKey}`)?.scrollIntoView({ block: "center", behavior: "smooth" })
  }, [focusKey, module.id])

  async function save() {
    setBusy(true)
    setMsg(null)
    try {
      const res = await saveSettings(
        module.id,
        Object.fromEntries(changed.map((k) => [k, draft[k]])),
      )
      onSaved(res.values)
      setDraft({})
      setMsg({ ok: true, text: t("Saved") })
    } catch (e) {
      setMsg({ ok: false, text: serverError(e) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6 pb-24">
      {readOnly && (
        <p className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-600">
          <Lock className="size-4 text-zinc-400" aria-hidden />
          {t("View only. {roles} can change these.", { roles: module.editors.map((r) => t(r)).join(", ") })}
        </p>
      )}

      {module.sections.map((sec) => (
        <section key={sec.id} aria-labelledby={`sec-${module.id}-${sec.id}`}>
          <div className="mb-2 px-1">
            <h3 id={`sec-${module.id}-${sec.id}`} className="text-sm font-semibold text-zinc-900">
              {t(sec.title)}
            </h3>
            {sec.description && <p className="text-xs text-zinc-500">{t(sec.description)}</p>}
          </div>
          <Card className="divide-y divide-zinc-100 overflow-hidden">
            {sec.settings.map((s) => (
              <SettingRow
                key={s.key}
                spec={s}
                value={s.key in draft ? draft[s.key] : module.values[s.key]}
                saved={module.values[s.key]}
                disabled={readOnly || busy}
                highlight={focusKey === s.key}
                sources={sources}
                taxIdLabel={taxIdLabel}
                onChange={(v) => {
                  setMsg(null)
                  setDraft((d) => ({ ...d, [s.key]: v }))
                }}
              />
            ))}
          </Card>
        </section>
      ))}

      {children}

      {module.related.length > 0 && (
        <section>
          <h3 className="mb-2 px-1 text-sm font-semibold text-zinc-900">{t("Managed on their own screens")}</h3>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {module.related.map((r) => (
              <Link
                key={r.to}
                to={r.to}
                className="group flex items-center justify-between rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm font-medium text-zinc-700 shadow-sm hover:border-brand-300 hover:text-brand-700"
              >
                {t(r.label)}
                <ArrowUpRight className="size-4 text-zinc-400 group-hover:text-brand-600" aria-hidden />
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* contextual save bar - only while there is something to save or report */}
      {(changed.length > 0 || msg) && !readOnly && (
        <div className="sticky bottom-4 z-30">
          <div
            role="status"
            className="flex flex-wrap items-center gap-3 rounded-xl border border-zinc-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur"
          >
            {changed.length > 0 && (
              <span className="text-sm text-zinc-700">
                {changed.length === 1
                  ? t("1 unsaved change")
                  : t("{n} unsaved changes", { n: changed.length })}
              </span>
            )}
            {msg && (
              <span className={cn("text-sm", msg.ok ? "text-emerald-700" : "text-rose-600")}>{translate(msg.text)}</span>
            )}
            <div className="ms-auto flex gap-2">
              {changed.length > 0 ? (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      setDraft({})
                      setMsg(null)
                    }}
                    disabled={busy}
                    className="rounded-lg px-3 py-1.5 text-sm font-medium text-zinc-600 hover:bg-zinc-100"
                  >
                    {t("Discard")}
                  </button>
                  <button
                    type="button"
                    onClick={save}
                    disabled={busy}
                    className="rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
                  >
                    {busy ? t("Saving…") : t("Save changes")}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => setMsg(null)}
                  className="rounded-lg px-3 py-1.5 text-sm text-zinc-500 hover:bg-zinc-100"
                >
                  {t("Dismiss")}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
