import { useCallback, useEffect, useState } from "react"
import { useNavigate, useOutletContext } from "react-router-dom"
import { BedDouble, CalendarDays, Receipt, ShieldCheck } from "lucide-react"

import { call, reservationDetail, type ReservationDetail } from "../lib/api"
import { cur, moneyLocale } from "../lib/money"
import { useT, t as translate, uiDateLocale } from "../lib/i18n"
import { serverError } from "../lib/resource"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"
import CheckInDialog from "./CheckInDialog"
import CheckOutDialog from "./CheckOutDialog"
import type { ShellContext } from "../AppShell"

/** What a Kamra Agent turn hands the chat (kamra.assistant._turn_cards). */
export type AgentCard =
  | { type: "stay"; reservation: string }
  | {
      type: "quote"
      room_type?: string
      check_in_date?: string
      check_out_date?: string
      adults?: number
      children?: number
      nights?: number
      total?: number
      deposit?: number
    }

const money = (n: number) =>
  `${cur()}${Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })}`

const day = (d?: string | null) =>
  d
    ? new Date(d + "T00:00:00").toLocaleDateString(uiDateLocale(undefined), {
        day: "numeric",
        month: "short",
      })
    : ""

const STATUS_TONE: Record<string, "green" | "sky" | "zinc" | "amber" | "rose"> = {
  Confirmed: "sky",
  "Checked In": "green",
  "Checked Out": "zinc",
  Cancelled: "rose",
  "No Show": "rose",
  Held: "amber",
  "Pending Payment": "amber",
}

/** A stay the agent touched, with the desk's own actions on it. Every button
 *  opens the same sheet or endpoint the rest of Kamra uses, as this user. */
function StayCard({ reservation }: { reservation: string }) {
  const { t } = useT()
  const navigate = useNavigate()
  const [stay, setStay] = useState<ReservationDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sheet, setSheet] = useState<"in" | "out" | null>(null)
  const [waiving, setWaiving] = useState(false)
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    reservationDetail(reservation)
      .then((d) => {
        setStay(d)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
  }, [reservation])
  useEffect(load, [load])

  if (error)
    return (
      <div className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-500">
        {reservation} · {translate(error)}
      </div>
    )
  if (!stay)
    return <div className="h-24 animate-pulse rounded-xl border border-zinc-100 bg-zinc-50" />

  const due = Number(stay.money?.due || 0)
  const dep = stay.security_deposit
  const depositOpen = !!dep && dep.status === "Required" && dep.can_waive

  async function waive() {
    if (!reason.trim()) return
    setBusy(true)
    try {
      await call("kamra.api.waive_security_deposit", { reservation, reason: reason.trim() })
      setWaiving(false)
      setReason("")
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-zinc-900">{stay.guest?.full_name}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500">
            <span className="inline-flex items-center gap-1">
              <BedDouble className="size-3.5" aria-hidden />
              {stay.room_number ? t("Room {n}", { n: stay.room_number }) : stay.room_type_name || t("No room yet")}
            </span>
            <span className="inline-flex items-center gap-1">
              <CalendarDays className="size-3.5" aria-hidden />
              {day(stay.check_in_date)} - {day(stay.check_out_date)}
            </span>
            <span className="font-mono text-[11px] text-zinc-400">{stay.name}</span>
          </div>
        </div>
        <Badge tone={STATUS_TONE[stay.status] ?? "zinc"}>{t(stay.status)}</Badge>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        <span className={due > 0 ? "font-medium text-amber-700" : "text-zinc-500"}>
          {due > 0 ? t("{amount} due", { amount: money(due) }) : t("Nothing due")}
        </span>
        {dep && dep.status !== "None" && (
          <span className="inline-flex items-center gap-1 text-zinc-500">
            <ShieldCheck className="size-3.5" aria-hidden />
            {t("Security deposit: {status}", { status: t(dep.status) })}
          </span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {stay.actions?.can_check_in && (
          <Button className="px-2.5 py-1 text-xs" onClick={() => setSheet("in")}>{t("Check in")}</Button>
        )}
        {stay.actions?.can_check_out && (
          <Button className="px-2.5 py-1 text-xs" onClick={() => setSheet("out")}>{t("Check out")}</Button>
        )}
        {stay.folio_name && due > 0 && (
          <Button
            variant="outline"
            className="px-2.5 py-1 text-xs"
            onClick={() => navigate(`/billing/${encodeURIComponent(stay.folio_name!)}`)}
          >
            {t("Collect {amount}", { amount: money(due) })}
          </Button>
        )}
        {stay.folio_name && (
          <Button
            variant="outline"
            className="px-2.5 py-1 text-xs"
            onClick={() => navigate(`/billing/${encodeURIComponent(stay.folio_name!)}`)}
          >
            <Receipt className="size-3.5" aria-hidden />
            {t("Open folio")}
          </Button>
        )}
        {depositOpen && !waiving && (
          <Button variant="outline" className="px-2.5 py-1 text-xs" onClick={() => setWaiving(true)}>
            {t("Waive deposit")}
          </Button>
        )}
        <Button
          variant="ghost"
          className="px-2.5 py-1 text-xs"
          onClick={() => navigate(`/grc/${encodeURIComponent(stay.name)}`)}
        >
          {t("Open stay")}
        </Button>
      </div>

      {waiving && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            autoFocus
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t("Reason (goes on the record)")}
            className="min-w-0 flex-1 rounded-lg border border-zinc-200 px-2.5 py-1 text-xs outline-none focus:border-brand-400"
          />
          <Button className="px-2.5 py-1 text-xs" disabled={busy || !reason.trim()} onClick={waive}>
            {t("Waive")}
          </Button>
          <Button variant="ghost" className="px-2.5 py-1 text-xs" onClick={() => setWaiving(false)}>
            {t("Cancel")}
          </Button>
        </div>
      )}

      {sheet === "in" && (
        <CheckInDialog
          reservation={stay.name}
          onClose={() => setSheet(null)}
          onDone={() => {
            setSheet(null)
            load()
          }}
        />
      )}
      {sheet === "out" && (
        <CheckOutDialog
          reservation={stay.name}
          onClose={() => setSheet(null)}
          onDone={() => {
            setSheet(null)
            load()
          }}
        />
      )}
    </div>
  )
}

/** A quote the agent priced; Book opens the normal booking dialog with it. */
function QuoteCard({ card }: { card: Extract<AgentCard, { type: "quote" }> }) {
  const { t } = useT()
  const shell = useOutletContext<ShellContext | undefined>()
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-zinc-900">{card.room_type}</div>
          <div className="mt-0.5 text-xs text-zinc-500">
            {day(card.check_in_date)} - {day(card.check_out_date)}
            {card.nights ? ` · ${t("{n} nights", { n: card.nights })}` : ""}
            {card.adults ? ` · ${t("{n} adults", { n: card.adults })}` : ""}
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm font-semibold tabular-nums text-zinc-900">{money(card.total ?? 0)}</div>
          {!!card.deposit && (
            <div className="text-[11px] text-zinc-500">
              {t("+ {amount} refundable deposit", { amount: money(card.deposit) })}
            </div>
          )}
        </div>
      </div>
      {shell?.canBook && (
        <div className="mt-3">
          <Button
            className="px-2.5 py-1 text-xs"
            onClick={() =>
              shell.openBooking({
                room_type: card.room_type,
                date: card.check_in_date,
                stays: card.nights,
                adults: card.adults,
                children: card.children,
              })
            }
          >
            {t("Book")}
          </Button>
        </div>
      )}
    </div>
  )
}

export default function AgentCards({ cards }: { cards: AgentCard[] }) {
  if (!cards.length) return null
  return (
    <div className="grid gap-2">
      {cards.map((c, i) =>
        c.type === "stay" ? (
          <StayCard key={c.reservation} reservation={c.reservation} />
        ) : (
          <QuoteCard key={`q${i}`} card={c} />
        ),
      )}
    </div>
  )
}
