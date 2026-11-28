/*  A different person turns up for a booking made under someone else's name
    or number (change_booking_guest). The booking and its own bill move to the
    new guest, before check-in; the old guest's profile and other stays are
    not touched. Used from the reservation page and from the guest step of
    check-in. The desk sees who the booking moves from and to before it is
    saved, and a short confirmation after. */

import { useEffect, useState } from "react"
import { CheckCircle2, X } from "lucide-react"
import { call, guestAlert, guestSearch, type GuestAlert, type GuestHit } from "../lib/api"
import { serverError } from "../lib/resource"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Button } from "./ui/button"

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

type Mode = "new" | "existing"

export default function ChangeGuestDialog(props: {
  reservation: string
  /** who the booking names now */
  guestName: string
  guestPhone?: string | null
  /** the guest named now has completed online check-in */
  onlineCheckIn?: boolean
  onClose: () => void
  onDone: () => void
}) {
  const { t, tn } = useT()
  const [mode, setMode] = useState<Mode>("new")
  const [name, setName] = useState("")
  const [phone, setPhone] = useState("")
  const [q, setQ] = useState("")
  const [hits, setHits] = useState<GuestHit[]>([])
  const [picked, setPicked] = useState<GuestHit | null>(null)
  const [reason, setReason] = useState("")
  const [alert, setAlert] = useState<GuestAlert | null>(null)
  const [blReason, setBlReason] = useState("")
  const [confirming, setConfirming] = useState(false)
  const [done, setDone] = useState<{ name: string; removed: number } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /** any edit takes the summary away: what is shown must be what is saved */
  const edit = () => {
    setConfirming(false)
    setError(null)
  }

  // typeahead for an existing profile, once two letters are typed
  useEffect(() => {
    if (mode !== "existing" || picked || q.trim().length < 2) {
      setHits([])
      return
    }
    let live = true
    const h = setTimeout(() => {
      guestSearch(q.trim())
        .then((r) => live && setHits(r))
        .catch(() => live && setHits([]))
    }, 250)
    return () => {
      live = false
      clearTimeout(h)
    }
  }, [q, mode, picked])

  // is the guest this would attach to blacklisted, and may this user override it?
  useEffect(() => {
    setAlert(null)
    const guest = mode === "existing" ? picked?.name : undefined
    if (mode === "existing" ? !guest : phone.replace(/\D/g, "").length < 6) return
    let live = true
    const h = setTimeout(() => {
      guestAlert({ guest, phone: guest ? undefined : phone.trim() })
        .then((a) => live && setAlert(a))
        .catch(() => live && setAlert(null))
    }, 300)
    return () => {
      live = false
      clearTimeout(h)
    }
  }, [mode, picked, phone])

  const blacklisted = alert ? !!alert.blacklisted : mode === "existing" && !!picked?.blacklisted
  const overridden = blacklisted && !!alert?.can_override && blReason.trim().length > 0
  const ready =
    (mode === "new" ? name.trim().length > 0 && phone.trim().length > 0 : !!picked) &&
    (!blacklisted || overridden)

  const to = mode === "new" ? { name: name.trim(), phone: phone.trim() } : { name: picked?.full_name ?? "", phone: picked?.phone ?? "" }
  const who = (n: string, p?: string | null) => (p ? `${n} (${p})` : n)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const out = await call<{ guest_name: string; removed_occupants: number }>("kamra.api.change_booking_guest", {
        reservation: props.reservation,
        ...(mode === "new" ? { guest_name: name.trim(), phone: phone.trim() } : { guest: picked!.name }),
        reason: reason.trim() || undefined,
        blacklist_override_reason: blacklisted ? blReason.trim() : undefined,
      })
      setDone({ name: out.guest_name, removed: out.removed_occupants })
    } catch (e) {
      setError(serverError(e))
      setConfirming(false)
    } finally {
      setBusy(false)
    }
  }

  const tab = (m: Mode, label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={mode === m}
      onClick={() => {
        setMode(m)
        edit()
      }}
      className={cn(
        "flex-1 rounded-lg border px-3 py-1.5 text-sm font-medium",
        mode === m ? "border-brand-600 bg-brand-50 text-brand-800" : "border-zinc-200 text-zinc-600 hover:bg-zinc-50",
      )}
    >
      {label}
    </button>
  )

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={t("Change guest")}>
      <div className="absolute inset-0 bg-black/40" onClick={done ? props.onDone : props.onClose} aria-hidden />
      <div className="relative w-full max-w-md rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl">
        <header className="flex items-start justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900">{t("Change guest")}</h2>
            <p className="text-sm text-zinc-500">{t("Booked under {name}", { name: props.guestName })}</p>
          </div>
          <Button variant="ghost" onClick={done ? props.onDone : props.onClose} aria-label={t("Close")}>
            <X className="size-5" />
          </Button>
        </header>

        {done ? (
          <>
            <div className="px-5 py-4 text-sm">
              <p role="status" className="flex items-start gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-emerald-800">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>
                  {t("Guest changed. {name} is now on the booking, and its bill and deposit moved with it.", { name: done.name })}
                  {done.removed > 0 &&
                    ` ${tn(done.removed, "{n} person listed in online check-in was removed.", "{n} people listed in online check-in were removed.")}`}
                </span>
              </p>
            </div>
            <footer className="flex justify-end gap-2 border-t border-zinc-100 px-5 py-3">
              <Button onClick={props.onDone}>{t("Done")}</Button>
            </footer>
          </>
        ) : (
          <>
            <div className="space-y-3 px-5 py-4 text-sm">
              <p className="text-zinc-600">
                {t("Use this when a different person arrives for the booking. The booking and its bill move to them. The old guest's profile and other stays are not touched.")}
              </p>

              <div role="tablist" className="flex gap-2">
                {tab("new", t("New person"))}
                {tab("existing", t("Existing guest"))}
              </div>

              {mode === "new" ? (
                <div className="space-y-2">
                  <label className="block">
                    <span className="mb-1 block text-xs text-zinc-500">{t("Full name")}</span>
                    <input className={inputCls} value={name} autoFocus required onChange={(e) => { setName(e.target.value); edit() }} />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs text-zinc-500">
                      {t("Phone")} <span aria-hidden className="text-rose-600">*</span>
                    </span>
                    <input className={inputCls} inputMode="tel" value={phone} required aria-required onChange={(e) => { setPhone(e.target.value); edit() }} />
                  </label>
                  <p className="text-xs text-zinc-400">
                    {t("A guest with this name and phone already on file is used; otherwise a new profile is made.")}
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {picked ? (
                    <div className="flex items-center justify-between gap-2 rounded-lg border border-zinc-200 px-3 py-2">
                      <span>
                        <span className="font-medium">{picked.full_name}</span>
                        {picked.phone && <span className="ms-2 text-zinc-500">{picked.phone}</span>}
                      </span>
                      <button type="button" className="text-xs text-brand-700 underline" onClick={() => { setPicked(null); edit() }}>
                        {t("Change")}
                      </button>
                    </div>
                  ) : (
                    <>
                      <input
                        className={inputCls}
                        autoFocus
                        placeholder={t("Search by name or phone")}
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                      />
                      {q.trim().length >= 2 && hits.length === 0 && (
                        <p className="text-xs text-zinc-400">{t("No guests found.")}</p>
                      )}
                      <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200 empty:hidden">
                        {hits.map((h) => (
                          <li key={h.name}>
                            <button
                              type="button"
                              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-start hover:bg-zinc-50"
                              onClick={() => { setPicked(h); edit() }}
                            >
                              <span>
                                <span className="font-medium">{h.full_name}</span>
                                {h.phone && <span className="ms-2 text-zinc-500">{h.phone}</span>}
                              </span>
                              <span className="text-xs text-zinc-400">
                                {h.blacklisted ? t("Blacklisted") : t("{n} stays", { n: h.stays })}
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              )}

              {blacklisted && (
                <div role="alert" className="space-y-2 rounded-xl border-2 border-rose-300 bg-rose-50 px-3 py-2 text-rose-800">
                  <p className="font-medium">
                    {alert?.full_name
                      ? t("{name} is blacklisted", { name: alert.full_name })
                      : t("This guest is blacklisted")}
                  </p>
                  {alert?.blacklist_reason && <p>{alert.blacklist_reason}</p>}
                  {alert?.can_override ? (
                    <input
                      className={inputCls}
                      value={blReason}
                      onChange={(e) => { setBlReason(e.target.value); edit() }}
                      placeholder={t("Reason for overriding the blacklist")}
                    />
                  ) : (
                    <p>{t("Only a Hotel Admin can book a blacklisted guest.")}</p>
                  )}
                </div>
              )}

              <input
                className={inputCls}
                placeholder={t("Reason (optional)")}
                value={reason}
                onChange={(e) => { setReason(e.target.value); edit() }}
              />

              {confirming && ready && (
                <p role="status" className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">
                  {t("Move this booking from {from} to {to}? The booking, its bill and its deposit move to them. {from} keeps their profile and other stays.", {
                    from: who(props.guestName, props.guestPhone),
                    to: who(to.name, to.phone),
                  })}
                  {props.onlineCheckIn &&
                    ` ${t("People they listed in online check-in that the desk has not confirmed are removed.")}`}
                </p>
              )}
              {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-rose-700">{error}</p>}
            </div>

            <footer className="flex justify-end gap-2 border-t border-zinc-100 px-5 py-3">
              <Button variant="outline" disabled={busy} onClick={props.onClose}>
                {t("Cancel")}
              </Button>
              {confirming ? (
                <Button disabled={busy || !ready} onClick={() => void submit()}>
                  {busy ? t("Saving…") : t("Confirm change")}
                </Button>
              ) : (
                <Button disabled={busy || !ready} onClick={() => setConfirming(true)}>
                  {t("Change guest")}
                </Button>
              )}
            </footer>
          </>
        )}
      </div>
    </div>
  )
}
