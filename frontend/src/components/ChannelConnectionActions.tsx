import { useCallback, useEffect, useState } from "react"

import { call } from "../lib/api"
import { serverError, type Row } from "../lib/resource"
import { Button } from "./ui/button"
import { t, useUILanguage } from "../lib/i18n"
import { momentParts } from "../lib/localDates"

export type OutboxStatus = {
  outbox: boolean
  pending: number
  failed: number
  paused: Record<string, number>
  last_push: string
  last_push_status: string
  last_full_sync: string
}

type MappingRow = { room_type: string; external_room_id: string; external_rate_id: string; rate_plan?: string | null }
type Unmatched = { room_id: string; room_name?: string; rateplan_id?: string; rateplan_name?: string; reason?: string }
export type ImportPreview = {
  created: MappingRow[]
  updated: MappingRow[]
  unmatched: Unmatched[]
  warnings: { code: string; message: string }[]
}

type FullSync = { queued?: boolean; needs_confirm?: boolean; last_full_sync?: string }

const heading = "text-xs font-semibold uppercase tracking-wider text-zinc-500"

/** The connection panel: what the ARI outbox holds, the mapping import
 *  (preview first, then apply) and the full sync, which asks before a
 *  second one within 24 h (Channex admits one a day). */
export default function ChannelConnectionActions({ row, reload }: { row: Row; reload: () => void }) {
  const lang = useUILanguage()
  const connection = String(row.name)
  /** A server moment as the reader writes it ("17-11 a las 09:15"); the raw value if it is not a date. */
  const moment = (value: string) => {
    const parts = momentParts(value, lang)
    return parts ? t("{date} at {time}", parts) : value
  }
  const [status, setStatus] = useState<OutboxStatus | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [confirmSince, setConfirmSince] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    call<OutboxStatus>("kamra.channel_ari.outbox_status", { connection }).then(setStatus)
      .catch((e) => setError(serverError(e)))
  }, [connection])
  useEffect(refresh, [refresh])

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      return await fn()
    } catch (e) {
      setError(serverError(e))
      return undefined
    } finally {
      setBusy(false)
    }
  }

  async function importMappings(dry_run: number) {
    const out = await run(() => call<ImportPreview>("kamra.channel_manager.import_room_mappings", { connection, dry_run }))
    if (!out) return
    if (dry_run) {
      setPreview(out)
      return
    }
    setPreview(null)
    setNotice(t("Mapping imported: {created} created, {updated} updated.",
      { created: out.created.length, updated: out.updated.length }))
    reload()
  }

  async function fullSync(confirm: number) {
    const out = await run(() => call<FullSync>("kamra.channel_ari.request_full_sync", { connection, confirm }))
    if (!out) return
    if (out.needs_confirm) {
      setConfirmSince(out.last_full_sync || "")
      return
    }
    setConfirmSince(null)
    setNotice(t("Full sync queued. It goes out within a minute."))
    refresh()
  }

  if (status && !status.outbox) return null
  const paused = Object.entries(status?.paused ?? {})

  return (
    <div className="space-y-3 border-t border-zinc-200 pt-4">
      <div className={heading}>{t("Availability and rates sync")}</div>
      {status && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <dt className="text-zinc-500">{t("Changes waiting")}</dt>
          <dd>{status.pending}</dd>
          <dt className="text-zinc-500">{t("Failed changes")}</dt>
          <dd className={status.failed ? "text-rose-600" : ""}>{status.failed}</dd>
          <dt className="text-zinc-500">{t("Last push")}</dt>
          <dd>{status.last_push ? `${moment(status.last_push)} · ${status.last_push_status}` : t("Never")}</dd>
          <dt className="text-zinc-500">{t("Last full sync")}</dt>
          <dd>{status.last_full_sync ? moment(status.last_full_sync) : t("Never")}</dd>
        </dl>
      )}
      {paused.map(([kind, seconds]) => (
        <p key={kind} className="text-xs text-amber-700">
          {t("{kind} paused by the channel manager for {seconds} s.", { kind: kind === "availability" ? t("Availability") : t("Rates and restrictions"), seconds })}
        </p>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={busy} onClick={() => { void importMappings(1) }}>
          {t("Import mapping")}
        </Button>
        <Button variant="outline" disabled={busy} onClick={() => { void fullSync(0) }}>
          {t("Full sync")}
        </Button>
      </div>

      {confirmSince !== null && (
        <div role="alertdialog" className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
          <p>{t("The last full sync went out on {date} at {time}. The channel manager admits one a day: send another anyway?",
            momentParts(confirmSince, lang) ?? { date: confirmSince, time: "" })}</p>
          <div className="flex gap-2">
            <Button disabled={busy} onClick={() => { void fullSync(1) }}>{t("Send it")}</Button>
            <Button variant="ghost" disabled={busy} onClick={() => setConfirmSince(null)}>{t("Cancel")}</Button>
          </div>
        </div>
      )}

      {preview && (
        <div className="space-y-2 rounded-lg border border-zinc-200 p-3 text-sm">
          <div className={heading}>{t("Mapping preview")}</div>
          <p>{t("{created} to create, {updated} to update, {unmatched} unmatched.",
            { created: preview.created.length, updated: preview.updated.length, unmatched: preview.unmatched.length })}</p>
          {[...preview.created, ...preview.updated].length > 0 && (
            <ul className="space-y-0.5 text-xs text-zinc-600">
              {[...preview.created, ...preview.updated].map((m) => (
                <li key={`${m.external_room_id}|${m.external_rate_id}`}>
                  {m.room_type} · {m.rate_plan || t("Base price")} → {m.external_rate_id || m.external_room_id}
                </li>
              ))}
            </ul>
          )}
          {preview.unmatched.length > 0 && (
            <ul className="space-y-0.5 text-xs text-rose-700">
              {preview.unmatched.map((u) => (
                <li key={`${u.room_id}|${u.rateplan_id ?? ""}`}>
                  {u.room_name || u.room_id}{u.rateplan_name ? ` · ${u.rateplan_name}` : ""}: {u.reason}
                </li>
              ))}
            </ul>
          )}
          {preview.warnings.length > 0 && (
            <ul className="space-y-0.5 text-xs text-amber-700">
              {preview.warnings.map((w, i) => <li key={`${w.code}${i}`}>{w.message}</li>)}
            </ul>
          )}
          <div className="flex gap-2">
            <Button disabled={busy || preview.created.length + preview.updated.length === 0}
              onClick={() => { void importMappings(0) }}>{t("Apply")}</Button>
            <Button variant="ghost" disabled={busy} onClick={() => setPreview(null)}>{t("Cancel")}</Button>
          </div>
        </div>
      )}

      {notice && <p className="text-xs text-emerald-700">{notice}</p>}
      {error && <p className="text-xs text-rose-600">{t(error)}</p>}
    </div>
  )
}
