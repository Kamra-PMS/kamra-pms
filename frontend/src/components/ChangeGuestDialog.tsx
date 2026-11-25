/*  A different person turns up for a booking made under someone else's name
    or number (change_booking_guest). The booking and its own bill move to the
    new guest, before check-in; the old guest's profile and other stays are
    not touched. Used from the reservation page and from the guest step of
    check-in. */

import { useEffect, useState } from "react"
import { X } from "lucide-react"
import { call, guestSearch, type GuestHit } from "../lib/api"
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
  onClose: () => void
  onDone: () => void
}) {
  const { t } = useT()
  const [mode, setMode] = useState<Mode>("new")
  const [name, setName] = useState("")
  const [phone, setPhone] = useState("")
  const [q, setQ] = useState("")
  const [hits, setHits] = useState<GuestHit[]>([])
  const [picked, setPicked] = useState<GuestHit | null>(null)
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

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

  const ready = mode === "new" ? name.trim().length > 0 : !!picked && !picked.blacklisted

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      await call("kamra.api.change_booking_guest", {
        reservation: props.reservation,
        ...(mode === "new" ? { guest_name: name.trim(), phone: phone.trim() || undefined } : { guest: picked!.name }),
        reason: reason.trim() || undefined,
      })
      props.onDone()
    } catch (e) {
      setError(serverError(e))
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
        setError(null)
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
      <div className="absolute inset-0 bg-black/40" onClick={props.onClose} aria-hidden />
      <div className="relative w-full max-w-md rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl">
        <header className="flex items-start justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900">{t("Change guest")}</h2>
            <p className="text-sm text-zinc-500">{t("Booked under {name}", { name: props.guestName })}</p>
          </div>
          <Button variant="ghost" onClick={props.onClose} aria-label={t("Close")}>
            <X className="size-5" />
          </Button>
        </header>

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
                <input className={inputCls} value={name} autoFocus onChange={(e) => setName(e.target.value)} />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs text-zinc-500">{t("Phone")}</span>
                <input className={inputCls} inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
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
                  <button type="button" className="text-xs text-brand-700 underline" onClick={() => setPicked(null)}>
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
                          onClick={() => setPicked(h)}
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
              {picked?.blacklisted ? (
                <p className="rounded-lg bg-rose-50 px-3 py-2 text-rose-700">
                  {t("This guest is blacklisted. A Hotel Admin has to remove the flag on the profile first.")}
                </p>
              ) : null}
            </div>
          )}

          <input
            className={inputCls}
            placeholder={t("Reason (optional)")}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-rose-700">{error}</p>}
        </div>

        <footer className="flex justify-end gap-2 border-t border-zinc-100 px-5 py-3">
          <Button variant="outline" disabled={busy} onClick={props.onClose}>
            {t("Back")}
          </Button>
          <Button disabled={busy || !ready} onClick={() => void submit()}>
            {busy ? t("Saving…") : t("Change guest")}
          </Button>
        </footer>
      </div>
    </div>
  )
}
