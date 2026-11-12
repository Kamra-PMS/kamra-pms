/*  Guest offers: perks for repeat and high-value guests. Opened from a
    guest's profile (?guest=) or a reservation (?reservation=). Anyone at
    the desk (or an AI agent) proposes; a Hotel Admin or Finance approves
    or declines here. The server (kamra.guest_offers) checks the property's
    limits again on approval and refuses an agent, whatever this screen
    shows. Redeeming posts through the allowance, room move or add-on. */

import { useCallback, useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { cur, fmtAmount } from "../lib/money"
import { useT, t as translate } from "../lib/i18n"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"

const KINDS = ["Early check-in", "Late check-out", "Upgrade", "Complimentary service", "Discount"] as const
const TABS = ["Proposed", "Approved", "Delivered", "Redeemed", "Declined", "Expired"] as const
type Status = (typeof TABS)[number]
const TONE: Record<Status, "amber" | "green" | "sky" | "brand" | "rose" | "zinc"> = {
  Proposed: "amber", Approved: "green", Delivered: "sky", Redeemed: "brand", Declined: "rose", Expired: "zinc",
}

interface Offer {
  name: string
  code: string
  guest: string
  guest_name: string | null
  reservation: string | null
  kind: (typeof KINDS)[number]
  value: number
  experience: string | null
  room_type: string | null
  valid_to: string
  reason: string | null
  status: Status
  proposed_by: string
  channel: string | null
  approved_by: string | null
  decision_note: string | null
  redeemed_reservation: string | null
}
interface Listing {
  offers: Offer[]
  can_approve: boolean
  limits: { kinds: string[]; max_value: number; max_month: number }
  month_total: number
}
interface Options {
  room_types: { name: string; room_type_name: string }[]
  experiences: { name: string; experience_name: string; price: number }[]
}

const inputCls =
  "rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
const money = (n: number) => `${cur()}${fmtAmount(n || 0)}`
// "Upgrade" alone is also the software upgrade; the offer kind has its own sense
const kindLabel = (k: string) => (k === "Upgrade" ? "offer|Upgrade" : k)

export default function GuestOffers() {
  const { t } = useT()
  const property = getCurrentProperty()
  const [params] = useSearchParams()
  const guestParam = params.get("guest")
  const reservation = params.get("reservation")
  const [tab, setTab] = useState<Status | "">("")
  const [data, setData] = useState<Listing | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [declining, setDeclining] = useState<string | null>(null)
  const [note, setNote] = useState("")
  const [resGuest, setResGuest] = useState<string | null>(null)
  const guest = guestParam || resGuest

  const load = useCallback(() => {
    call<Listing>("kamra.guest_offers.list_offers", {
      property, status: tab || undefined, guest: guestParam || undefined,
      reservation: reservation || undefined,
    })
      .then(setData)
      .catch((e) => setError(serverError(e)))
  }, [property, tab, guestParam, reservation])
  useEffect(load, [load])

  useEffect(() => {
    if (!reservation || guestParam) return
    call<{ guest?: { name: string } }>("kamra.api.reservation_detail", { reservation })
      .then((d) => setResGuest(d.guest?.name ?? null))
      .catch(() => setResGuest(null))
  }, [reservation, guestParam])

  async function act(method: string, args: Record<string, unknown>) {
    setBusy(true)
    setError(null)
    try {
      await call(method, args)
      setDeclining(null); setNote("")
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const lim = data?.limits
  return (
    <div className="w-full max-w-3xl space-y-4">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{t("Guests")}</p>
        <h1 className="text-2xl font-semibold">{t("Guest offers")}</h1>
        <p className="text-sm text-zinc-500">
          {t("Perks for repeat and high-value guests. An offer is used only after a manager approves it.")}
        </p>
        {(guestParam || reservation) && (
          <p className="mt-1 text-sm">
            {guestParam && (
              <Link to={`/guests/${encodeURIComponent(guestParam)}`} className="text-brand-700 hover:underline">
                {t("Back to the guest")}
              </Link>
            )}
            {reservation && (
              <span className="text-zinc-500">{t("For stay {v0}", { v0: reservation })}</span>
            )}
          </p>
        )}
        {lim && (
          <p className="mt-1 text-xs text-zinc-500">
            {lim.max_value ? t("Most per offer: {v0}", { v0: money(lim.max_value) }) : t("No limit per offer")}
            {" · "}
            {lim.max_month
              ? t("This month: {v0} of {v1}", { v0: money(data.month_total), v1: money(lim.max_month) })
              : t("This month: {v0}", { v0: money(data.month_total) })}
          </p>
        )}
      </div>

      {guest && lim && (
        <ProposeForm property={property} guest={guest} reservation={reservation}
          kinds={lim.kinds} onDone={load} />
      )}

      <div className="flex flex-wrap gap-2">
        {(["", ...TABS] as const).map((k) => (
          <button key={k || "all"} type="button" onClick={() => setTab(k)}
            className={`rounded-full border px-3 py-1 text-xs ${tab === k
              ? "border-brand-600 bg-brand-50 text-brand-800"
              : "border-zinc-200 text-zinc-600 hover:bg-zinc-50"}`}>
            {k ? t(k) : t("All")}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-rose-600">{translate(error)}</p>}
      {data && !data.offers.length && (
        <p className="py-6 text-center text-sm text-zinc-400">{t("Nothing here.")}</p>
      )}
      <div className="space-y-2">
        {data?.offers.map((o) => (
          <div key={o.name} className="rounded-lg border border-zinc-200 bg-white p-3 text-sm">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="font-medium">{t(kindLabel(o.kind))}</span>
              <span className="tabular-nums">{money(o.value)}</span>
              <Badge tone={TONE[o.status]}>{t(o.status)}</Badge>
              <span className="font-mono text-xs text-zinc-500">{o.code}</span>
              {!guestParam && (
                <Link to={`/guests/${encodeURIComponent(o.guest)}`} className="ml-auto text-xs text-brand-700 hover:underline">
                  {o.guest_name || o.guest}
                </Link>
              )}
            </div>
            <p className="mt-0.5 text-xs text-zinc-500">
              {[o.room_type && t("to {v0}", { v0: o.room_type.split("-").pop() ?? "" }),
                o.experience && o.experience.split("-").pop(),
                o.reservation && t("stay {v0}", { v0: o.reservation }),
                t("valid to {v0}", { v0: o.valid_to }),
                t("proposed by {v0}", { v0: o.proposed_by }) + (o.channel && o.channel !== "Desk" ? ` (${o.channel})` : ""),
                o.approved_by && t("decided by {v0}", { v0: o.approved_by }),
              ].filter(Boolean).join(" · ")}
            </p>
            {o.reason && <p className="mt-0.5 text-xs text-zinc-600">{o.reason}</p>}
            {o.decision_note && <p className="mt-0.5 text-xs text-zinc-600">{o.decision_note}</p>}
            <div className="mt-2 flex flex-wrap gap-2">
              {o.status === "Proposed" && data.can_approve && (
                <>
                  <Button variant="outline" disabled={busy}
                    onClick={() => void act("kamra.guest_offers.decide_offer", { offer: o.name, approve: 1 })}>
                    {t("Approve")}
                  </Button>
                  <Button variant="ghost" disabled={busy} onClick={() => setDeclining(o.name)}>
                    {t("Decline")}
                  </Button>
                </>
              )}
              {o.status === "Approved" && (
                <Button variant="ghost" disabled={busy}
                  onClick={() => void act("kamra.guest_offers.mark_offer_delivered", { code: o.code })}>
                  {t("Told the guest")}
                </Button>
              )}
              {reservation && (o.status === "Approved" || o.status === "Delivered") && (
                <Button variant="outline" disabled={busy}
                  onClick={() => void act("kamra.guest_offers.redeem_offer", { code: o.code, reservation })}>
                  {t("Use on this stay")}
                </Button>
              )}
            </div>
            {declining === o.name && (
              <div className="mt-2 flex flex-wrap gap-2">
                <input autoFocus className={`${inputCls} min-w-48 flex-1`} value={note}
                  onChange={(e) => setNote(e.target.value)} placeholder={t("Why (optional)")} />
                <Button variant="outline" disabled={busy}
                  onClick={() => void act("kamra.guest_offers.decide_offer", { offer: o.name, approve: 0, note: note.trim() })}>
                  {t("Decline")}
                </Button>
                <Button variant="ghost" onClick={() => setDeclining(null)}>{t("Cancel")}</Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function ProposeForm({ property, guest, reservation, kinds, onDone }: {
  property: string
  guest: string
  reservation: string | null
  kinds: string[]
  onDone: () => void
}) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState(kinds[0] ?? "")
  const [value, setValue] = useState("")
  const [validTo, setValidTo] = useState("")
  const [roomType, setRoomType] = useState("")
  const [experience, setExperience] = useState("")
  const [opts, setOpts] = useState<Options | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (open && !opts)
      call<Options>("kamra.api.booking_options", { property }).then(setOpts).catch(() => setOpts(null))
  }, [open, opts, property])

  if (!open)
    return <Button variant="outline" onClick={() => setOpen(true)}>{t("Propose an offer")}</Button>

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      await call("kamra.guest_offers.propose_offer", {
        property, guest, kind, value: Number(value), valid_to: validTo,
        reservation: reservation || undefined,
        room_type: kind === "Upgrade" ? roomType : undefined,
        experience: kind === "Complimentary service" ? experience : undefined,
      })
      setOpen(false); setValue(""); setValidTo("")
      onDone()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-2 rounded-lg border border-zinc-200 bg-zinc-50 p-3">
      <div className="flex flex-wrap gap-2">
        <select className={inputCls} value={kind} onChange={(e) => setKind(e.target.value)} aria-label={t("Kind")}>
          {kinds.map((k) => <option key={k} value={k}>{t(kindLabel(k))}</option>)}
        </select>
        {kind === "Upgrade" && (
          <select className={inputCls} value={roomType} onChange={(e) => setRoomType(e.target.value)} aria-label={t("Upgrade to")}>
            <option value="">{t("Upgrade to…")}</option>
            {opts?.room_types.map((r) => <option key={r.name} value={r.name}>{r.room_type_name}</option>)}
          </select>
        )}
        {kind === "Complimentary service" && (
          <select className={inputCls} value={experience}
            onChange={(e) => {
              setExperience(e.target.value)
              const x = opts?.experiences.find((p) => p.name === e.target.value)
              if (x && !value) setValue(String(x.price))
            }} aria-label={t("Experience")}>
            <option value="">{t("Experience…")}</option>
            {opts?.experiences.map((x) => <option key={x.name} value={x.name}>{x.experience_name}</option>)}
          </select>
        )}
        <input className={`${inputCls} w-28`} type="number" min={0} step="0.01" value={value}
          onChange={(e) => setValue(e.target.value)} placeholder={t("Worth")} aria-label={t("Worth")} />
        <input className={inputCls} type="date" value={validTo} onChange={(e) => setValidTo(e.target.value)}
          aria-label={t("Valid to")} />
      </div>
      <div className="flex gap-2">
        <Button disabled={busy || !value || !validTo} onClick={() => void submit()}>{t("Propose")}</Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>{t("Cancel")}</Button>
      </div>
      {error && <p className="text-sm text-rose-600">{translate(error)}</p>}
    </div>
  )
}
