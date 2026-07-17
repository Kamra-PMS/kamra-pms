import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  BedDouble,
  CalendarDays,
  CreditCard,
  Fingerprint,
  FileText,
  LogIn,
  LogOut,
  ShieldCheck,
  Star,
  TriangleAlert,
  User,
} from "lucide-react"

import {
  amendStay,
  checkIn,
  checkOut,
  idDocumentImage,
  promoteWaitlist,
  reservationDetail,
  verifyPrecheckin,
  type ReservationDetail as Detail,
} from "../lib/api"
import { IdDocumentField } from "../components/IdDocumentField"
import { serverError, updateResource, type Row } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import CancelPanel from "../components/CancelPanel"
import LinkedRecords from "../components/LinkedRecords"

const inr = (n: number) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })

const STATUS_TONE: Record<string, string> = {
  Waitlist: "bg-amber-100 text-amber-800",
  Confirmed: "bg-sky-100 text-sky-800",
  "Checked In": "bg-emerald-100 text-emerald-800",
  "Checked Out": "bg-zinc-200 text-zinc-700",
  Cancelled: "bg-rose-100 text-rose-800",
  "No Show": "bg-amber-100 text-amber-800",
}

function Card(props: {
  icon: React.ReactNode
  title: string
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-zinc-700">
          <span className="text-zinc-400">{props.icon}</span>
          {props.title}
        </div>
        {props.action}
      </div>
      {props.children}
    </div>
  )
}

function Field(props: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-zinc-400">{props.label}</dt>
      <dd className="mt-0.5 text-sm text-zinc-800">{props.value || "-"}</dd>
    </div>
  )
}

/* The guest's ID for this stay: the photo, and whether a human has checked it
   against the person. The image is fetched through a role-gated endpoint, not
   linked by its /private/files/ URL - Frappe authorises that URL through the
   Reservation's doctype permissions, which this site's Custom DocPerm rows
   deny to Front Desk. Linking it would show the GM a photo and the desk a
   broken image. */
function IdentityCard({ d, reload }: { d: Detail; reload: () => void }) {
  const [img, setImg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    setImg(null)
    if (!d.id_document) return
    idDocumentImage(d.name).then((r) => setImg(r.data)).catch(() => setImg(null))
  }, [d.id_document, d.name])

  const verify = async () => {
    setBusy(true)
    setErr(null)
    try {
      await verifyPrecheckin(d.name)
      reload()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const open = d.status === "Confirmed" || d.status === "Checked In"

  return (
    <Card
      icon={<Fingerprint className="size-4" />}
      title="Identity"
      action={
        d.warnings.id_unverified ? (
          <Button variant="outline" disabled={busy} onClick={verify}>
            <ShieldCheck className="size-4" /> Verify identity
          </Button>
        ) : d.precheckin_verified_by ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
            <ShieldCheck className="size-3.5" />
            Verified by {d.precheckin_verified_by.split("@")[0]}
          </span>
        ) : undefined
      }
    >
      <dl className="mb-3 grid grid-cols-2 gap-3">
        <Field label="Pre-check-in" value={d.precheckin_status} />
        <Field label="ID captured by" value={d.id_document_source} />
      </dl>

      {img ? (
        <img src={img} alt="Guest ID document"
          className="max-h-56 w-auto rounded-lg border border-zinc-200" />
      ) : d.id_document ? (
        <p className="text-sm text-zinc-400">Loading the document…</p>
      ) : d.id_document_discarded ? (
        <p className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-500">
          ID document discarded at checkout, per this property's retention policy.
        </p>
      ) : open ? (
        <div className="space-y-2">
          {/* A warning, never a gate. The guest is standing here with a
              physical card; check-in works with or without this. */}
          <div className="flex items-start gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800">
            <TriangleAlert className="mt-px size-3.5 shrink-0" />
            No ID document on file — capture it at the counter.
          </div>
          <IdDocumentField
            method="kamra.api.upload_id_document"
            params={{ reservation: d.name }}
            uploaded={false}
            onUploaded={reload}
            label="Photograph the guest's ID"
          />
        </div>
      ) : null}

      {err && (
        <p className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {err}
        </p>
      )}
    </Card>
  )
}

export default function ReservationDetail({
  row,
  reload,
  onClose,
}: {
  row: Row
  reload: () => void
  onClose: () => void
}) {
  const name = String(row.name)
  const [d, setD] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(() => {
    reservationDetail(name)
      .then(setD)
      .catch((e) => setError(serverError(e)))
  }, [name])

  useEffect(() => refresh(), [refresh])

  // stay-date amend
  const [ci, setCi] = useState("")
  const [co, setCo] = useState("")
  useEffect(() => {
    if (d) {
      setCi(d.check_in_date)
      setCo(d.check_out_date)
    }
  }, [d])

  // editable special requests
  const [req, setReq] = useState<string>("")
  const [reqDirty, setReqDirty] = useState(false)
  useEffect(() => {
    if (d) {
      setReq(d.special_requests ?? "")
      setReqDirty(false)
    }
  }, [d])

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
      refresh()
      reload()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  if (!d)
    return (
      <p className="py-10 text-center text-sm text-zinc-400">
        {error ?? "Loading…"}
      </p>
    )

  const datesChanged = ci !== d.check_in_date || co !== d.check_out_date
  const money = d.money

  return (
    <div className="space-y-4">
      <LinkedRecords doctype="Reservation" name={String(row.name)} />
      {/* status + provenance */}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={
            "rounded-full px-2.5 py-1 text-xs font-semibold " +
            (STATUS_TONE[d.status] ?? "bg-zinc-100 text-zinc-700")
          }
        >
          {d.status}
        </span>
        {d.booking_type && d.booking_type !== "Individual" && (
          <Badge>{d.booking_type}</Badge>
        )}
        {d.source && <Badge>{d.source}</Badge>}
        {d.channel && <Badge>{d.channel}</Badge>}
        {d.guest?.vip === 1 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
            <Star className="size-3" /> VIP
          </span>
        )}
        {d.guest?.blacklisted === 1 && <Badge tone="rose">Blacklisted</Badge>}
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      {/* money - the question everyone asks first */}
      <Card
        icon={<CreditCard className="size-4" />}
        title="Billing"
        action={
          d.folio_name ? (
            <Link
              to={`/billing/${encodeURIComponent(d.folio_name)}`}
              onClick={onClose}
              className="text-xs font-medium text-brand-700 hover:underline"
            >
              Open folio →
            </Link>
          ) : undefined
        }
      >
        <div className="grid grid-cols-3 gap-3">
          <div>
            <div className="text-xs text-zinc-400">Total</div>
            <div className="text-lg font-semibold text-zinc-900">
              {inr(money.total)}
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-400">Paid</div>
            <div className="text-lg font-semibold text-emerald-700">
              {inr(money.paid)}
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-400">Balance due</div>
            <div
              className={
                "text-lg font-semibold " +
                (money.due > 0 ? "text-rose-600" : "text-zinc-400")
              }
            >
              {inr(money.due)}
            </div>
          </div>
        </div>
        <p className="mt-2 text-xs text-zinc-400">
          {money.has_folio
            ? "Live from the guest folio."
            : d.advance_paid > 0
              ? `Booking advance of ${inr(d.advance_paid)} received. The folio opens at check-in.`
              : "No folio yet - it opens at check-in."}
        </p>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        {/* stay + dates (editable) */}
        <Card icon={<CalendarDays className="size-4" />} title="Stay">
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs text-zinc-400">Check-in</span>
              <input
                type="date"
                value={ci}
                disabled={!d.actions.can_amend}
                onChange={(e) => setCi(e.target.value)}
                className="mt-0.5 w-full rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm disabled:bg-zinc-50 disabled:text-zinc-400"
              />
            </label>
            <label className="block">
              <span className="text-xs text-zinc-400">Check-out</span>
              <input
                type="date"
                value={co}
                disabled={!d.actions.can_amend}
                onChange={(e) => setCo(e.target.value)}
                className="mt-0.5 w-full rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm disabled:bg-zinc-50 disabled:text-zinc-400"
              />
            </label>
          </div>
          {datesChanged && d.actions.can_amend && (
            <Button
              className="mt-3"
              disabled={busy}
              onClick={() => act(() => amendStay(name, ci, co))}
            >
              {busy ? "Updating…" : "Update dates & re-price"}
            </Button>
          )}
          <dl className="mt-3 grid grid-cols-2 gap-3">
            <Field label="Nights" value={d.nights} />
            <Field
              label="Guests"
              value={`${d.adults} adult${d.adults === 1 ? "" : "s"}${
                d.children ? ` · ${d.children} child` : ""
              }`}
            />
            {d.eta && <Field label="ETA" value={d.eta} />}
            {d.precheckin_status && d.precheckin_status !== "Not Started" && (
              <Field label="Pre-check-in" value={d.precheckin_status} />
            )}
          </dl>
        </Card>

        <IdentityCard d={d} reload={refresh} />

        {/* room */}
        <Card icon={<BedDouble className="size-4" />} title="Room">
          <dl className="grid grid-cols-2 gap-3">
            <Field label="Room type" value={d.room_type_name ?? d.room_type} />
            <Field label="Room" value={d.room ?? "Unassigned"} />
            {d.meal_plan && <Field label="Meal plan" value={d.meal_plan} />}
            {d.rate_plan && <Field label="Rate plan" value={d.rate_plan} />}
          </dl>
          {!d.room && d.status === "Confirmed" && (
            <p className="mt-2 text-xs text-amber-600">
              No room assigned yet - assign from the Tape Chart before check-in.
            </p>
          )}
        </Card>

        {/* guest - connected to the journey */}
        <Card
          icon={<User className="size-4" />}
          title="Guest"
          action={
            d.guest ? (
              <Link
                to={`/guests/${encodeURIComponent(d.guest.name)}`}
                onClick={onClose}
                className="text-xs font-medium text-brand-700 hover:underline"
              >
                Guest journey →
              </Link>
            ) : undefined
          }
        >
          {d.guest ? (
            <dl className="grid grid-cols-2 gap-3">
              <Field label="Name" value={d.guest.full_name} />
              <Field label="Phone" value={d.guest.phone} />
              {d.guest.email && <Field label="Email" value={d.guest.email} />}
              <Field
                label="History"
                value={
                  d.guest.stays > 0
                    ? `${d.guest.stays} stay${d.guest.stays === 1 ? "" : "s"}${
                        d.guest.last_stay ? ` · last ${d.guest.last_stay}` : ""
                      }`
                    : "First stay"
                }
              />
            </dl>
          ) : (
            <p className="text-sm text-zinc-400">No linked guest profile.</p>
          )}
        </Card>

        {/* booker / company, when someone booked on the guest's behalf */}
        {(d.booker || d.company || d.travel_agent) && (
          <Card icon={<User className="size-4" />} title="Booked by">
            <dl className="grid grid-cols-2 gap-3">
              {d.booker && (
                <>
                  <Field label="Booker" value={d.booker.name} />
                  <Field label="Phone" value={d.booker.phone} />
                  {d.booker.relation && (
                    <Field label="Relation" value={d.booker.relation} />
                  )}
                  {d.booker.contact_preference && (
                    <Field
                      label="Send updates to"
                      value={d.booker.contact_preference}
                    />
                  )}
                </>
              )}
              {d.company && <Field label="Company" value={d.company} />}
              {d.travel_agent && (
                <Field label="Travel agent" value={d.travel_agent} />
              )}
            </dl>
          </Card>
        )}
      </div>

      {/* special requests - editable */}
      <Card icon={<FileText className="size-4" />} title="Special requests">
        <textarea
          value={req}
          onChange={(e) => {
            setReq(e.target.value)
            setReqDirty(true)
          }}
          placeholder="Late check-in, high floor, allergies…"
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
          rows={2}
        />
        {reqDirty && (
          <Button
            variant="outline"
            className="mt-2"
            disabled={busy}
            onClick={() =>
              act(() =>
                updateResource("Reservation", name, {
                  special_requests: req,
                }),
              )
            }
          >
            Save note
          </Button>
        )}
      </Card>

      {/* cancellation record, if any */}
      {d.cancellation && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          <p className="font-semibold">
            Cancelled - {d.cancellation.number}
          </p>
          <p className="mt-0.5">
            {d.cancellation.reason}
            {d.cancellation.fee > 0
              ? ` · fee ${inr(d.cancellation.fee)}`
              : " · no fee"}
            {d.cancellation.cancelled_on
              ? ` · ${d.cancellation.cancelled_on}`
              : ""}
          </p>
          <Link
            to={`/cancelled/${encodeURIComponent(name)}`}
            onClick={onClose}
            className="mt-1 inline-block font-medium text-rose-900 underline"
          >
            Cancellation letter
          </Link>
        </div>
      )}

      {/* primary actions */}
      <div className="flex flex-wrap items-center gap-2 border-t border-zinc-200 pt-4">
        {d.status === "Waitlist" && (
          <Button
            disabled={busy}
            onClick={() =>
              act(async () => {
                await promoteWaitlist(name)
              })
            }
          >
            <LogIn className="size-4" /> Promote to a room
          </Button>
        )}
        {/* Adjacent to the button, never wired into it: can_check_in stays
            `status === "Confirmed" && room`. A stale or missing upload must
            not turn a real guest away at the counter. */}
        {d.actions.can_check_in && d.warnings.id_document_missing && (
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-800">
            <TriangleAlert className="size-3.5" /> No ID document on file
          </span>
        )}
        {d.actions.can_check_in && (
          <Button disabled={busy} onClick={() => act(() => checkIn(name))}>
            <LogIn className="size-4" /> Check in
          </Button>
        )}
        {d.actions.can_check_out && (
          <Button disabled={busy} onClick={() => act(() => checkOut(name))}>
            <LogOut className="size-4" /> Check out
          </Button>
        )}
        <Link
          to={`/grc/${encodeURIComponent(name)}`}
          onClick={onClose}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-1.5 text-sm font-medium text-zinc-600 hover:border-brand-600 hover:text-brand-700"
        >
          <FileText className="size-4" /> Registration card
        </Link>
      </div>

      {/* cancel flow (self-guards to Confirmed) */}
      {d.actions.can_cancel && (
        <CancelPanel
          row={row}
          reload={() => {
            refresh()
            reload()
          }}
        />
      )}
    </div>
  )
}
