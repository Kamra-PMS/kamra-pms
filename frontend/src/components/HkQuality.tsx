/*  Housekeeping Board panels (#560), each behind its Housekeeping setting:
    - room status cases: rooms the front office and housekeeping disagree on,
      opened as a case with an owner and closed with a reason
      (kamra.housekeeping.room_discrepancies / open_ / close_room_discrepancy)
    - inspection pass rate and checkout-clean turn time by attendant and
      room type (kamra.housekeeping.hk_quality) */

import { useCallback, useEffect, useState } from "react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { useT, t as translate } from "../lib/i18n"
import { Button } from "./ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"

const inputCls = "rounded-lg border border-zinc-300 bg-white px-2 py-1 text-sm"

type Detected = { room: string; room_id: string; issue: string; front_office: string; room_board: string; housekeeping_status: string; guest_name?: string | null }
type Case = { name: string; room: string; room_number: string; issue: string; case_owner: string; opened_on: string; note?: string | null }

export function RoomStatusCases({ staff }: { staff: { user: string; full_name: string }[] }) {
  const { t } = useT()
  const [data, setData] = useState<{ enabled: boolean; detected: Detected[]; cases: Case[] } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [owner, setOwner] = useState("")
  const [closing, setClosing] = useState<string | null>(null)
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    call<{ enabled: boolean; detected: Detected[]; cases: Case[] }>("kamra.housekeeping.room_discrepancies", {
      property: getCurrentProperty(),
    }).then(setData).catch((e) => setErr(serverError(e)))
  }, [])
  useEffect(load, [load])

  const act = async (method: string, params: Record<string, unknown>) => {
    setBusy(true)
    setErr(null)
    try {
      await call(method, params)
      setClosing(null)
      setReason("")
      load()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  if (!data?.enabled || (!data.detected.length && !data.cases.length)) return null
  const name = (u: string) => staff.find((s) => s.user === u)?.full_name || u

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("Room status cases")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {err ? <p className="text-rose-600">{translate(err)}</p> : null}
        {data.detected.length ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-zinc-500">{t("Owner for new cases")}</span>
            <select className={inputCls} value={owner} onChange={(e) => setOwner(e.target.value)} aria-label={t("Owner")}>
              <option value="">{t("Me")}</option>
              {staff.map((s) => <option key={s.user} value={s.user}>{s.full_name}</option>)}
            </select>
          </div>
        ) : null}
        <ul className="divide-y divide-zinc-100">
          {data.detected.map((d) => (
            <li key={d.room_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>
                <b>{d.room}</b> · {translate(d.issue)}
                <span className="text-zinc-400"> · {t("Front office: {a} · Board: {b}, {c}", { a: translate(d.front_office), b: translate(d.room_board), c: translate(d.housekeeping_status) })}</span>
              </span>
              <Button variant="outline" disabled={busy}
                onClick={() => void act("kamra.housekeeping.open_room_discrepancy", {
                  property: getCurrentProperty(), room: d.room_id, owner: owner || undefined,
                })}>
                {t("Open case")}
              </Button>
            </li>
          ))}
          {data.cases.map((c) => (
            <li key={c.name} className="py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <span className="mr-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">{t("Open case")}</span>
                  <b>{c.room_number}</b> · {translate(c.issue)}
                  <span className="text-zinc-400"> · {t("Owner: {who}", { who: name(c.case_owner) })}</span>
                </span>
                {closing !== c.name ? (
                  <Button variant="outline" disabled={busy} onClick={() => { setClosing(c.name); setReason("") }}>
                    {t("Close case")}
                  </Button>
                ) : null}
              </div>
              {closing === c.name ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  <input autoFocus className={`${inputCls} min-w-56 flex-1`} value={reason} maxLength={500}
                    onChange={(e) => setReason(e.target.value)} placeholder={t("What was found (required)")} />
                  <Button disabled={busy || !reason.trim()}
                    onClick={() => void act("kamra.housekeeping.close_room_discrepancy", { case: c.name, reason: reason.trim() })}>
                    {t("Close case")}
                  </Button>
                  <Button variant="ghost" onClick={() => setClosing(null)}>{t("Cancel")}</Button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

type QRow = { key: string | null; label: string; inspected: number; passed: number; pass_rate: number | null; cleans: number; avg_turn_minutes: number | null }

export function InspectionQuality() {
  const { t } = useT()
  const [data, setData] = useState<{ enabled: boolean; attendant?: QRow[]; room_type?: QRow[] } | null>(null)
  const [by, setBy] = useState<"attendant" | "room_type">("attendant")

  useEffect(() => {
    call<{ enabled: boolean; attendant?: QRow[]; room_type?: QRow[] }>("kamra.housekeeping.hk_quality", {
      property: getCurrentProperty(),
    }).then(setData).catch(() => setData(null))
  }, [])

  const rows = data?.[by] ?? []
  if (!data?.enabled || (!data.attendant?.length && !data.room_type?.length)) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("Inspection pass rate and turn time, last 30 days")}</CardTitle>
        <select className={inputCls} value={by} onChange={(e) => setBy(e.target.value as "attendant" | "room_type")}
          aria-label={t("Group by")}>
          <option value="attendant">{t("By attendant")}</option>
          <option value="room_type">{t("By room type")}</option>
        </select>
      </CardHeader>
      <CardContent>
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-zinc-400">
            <tr>
              <th className="py-1.5 pr-3">{by === "attendant" ? t("Attendant") : t("Room type")}</th>
              <th className="py-1.5 pr-3 text-right">{t("Inspected")}</th>
              <th className="py-1.5 pr-3 text-right">{t("Pass rate")}</th>
              <th className="py-1.5 pr-3 text-right">{t("Checkout cleans")}</th>
              <th className="py-1.5 text-right">{t("Average turn")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key ?? "-"} className="border-t border-zinc-100">
                <td className="py-1.5 pr-3">{r.label || t("Unassigned")}</td>
                <td className="py-1.5 pr-3 text-right tabular-nums">{r.inspected}</td>
                <td className="py-1.5 pr-3 text-right tabular-nums">{r.pass_rate == null ? "-" : `${r.pass_rate}%`}</td>
                <td className="py-1.5 pr-3 text-right tabular-nums">{r.cleans}</td>
                <td className="py-1.5 text-right tabular-nums">
                  {r.avg_turn_minutes == null ? "-" : t("{n} min", { n: Math.round(r.avg_turn_minutes) })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
