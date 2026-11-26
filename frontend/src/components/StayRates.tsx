import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Button } from "./ui/button"
import { call } from "../lib/api"
import { cur, fmtAmount, moneyDigits, moneyLocale } from "../lib/money"
import {
  isOverride,
  maxPriceDigits,
  nightInMessage,
  nightLabel,
  parsePrice,
  samePrice,
  splitRoomTotal,
} from "../lib/nightPrices"
import { serverError } from "../lib/resource"
import { t as translate, uiDateLocale, useT } from "../lib/i18n"
import { cn } from "../lib/utils"

interface Night {
  date: string
  /** what the guest pays for the night now, in the basis the rates screen shows */
  price: number
  /** the rate card's price for the date today */
  rate: number
  /** the night is on the bill: its price is closed */
  posted: boolean
  /** the desk typed this night's price */
  hand_set: boolean
}

interface StayRatesData {
  reservation: string
  status: string
  can_set: boolean
  editable: boolean
  why_not: string | null
  tax_inclusive: boolean
  levy_inclusive: boolean
  nights: Night[]
}

interface Preview {
  current_amount: number
  new_amount: number
  difference: number
  needs_confirmation: boolean
  /** what the guest has paid on the stay so far */
  paid: number
  /** what the guest will still owe after the change (in house: the folio at
   *  check-out, extras included); below zero in credit, null when unknown */
  new_balance: number | null
}

/** A night the desk is changing, as the server takes it. */
interface Change {
  date: string
  price: number
}

const money = (n: number) => `${cur()}${fmtAmount(n)}`
const signed = (n: number) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${cur()}${fmtAmount(Math.abs(n))}`

/** The nightly prices of a saved booking, behind a "Change nightly prices"
 *  button: the same box the desk uses on New booking, for a stay that already
 *  exists. Typing shows one live total (the server prices it, so the figure is
 *  what the save will bill) and the Save button carries that total. Nights
 *  already on the bill are closed; every night the desk does not change keeps
 *  the price it was booked at. Shown only to a Revenue Manager or Hotel Admin. */
export default function StayRates({ reservation, onSaved }: { reservation: string; onSaved?: () => void }) {
  const { t } = useT()
  const [data, setData] = useState<StayRatesData | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [typed, setTyped] = useState<Record<string, number>>({})
  // what is being typed, before it is a valid price (a night's text, the room total or the same price)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  // the server's price for the nights in `changes`, tagged with the changes it was priced for
  const [preview, setPreview] = useState<(Preview & { key: string }) | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [recheck, setRecheck] = useState(0)
  const [busy, setBusy] = useState(false)
  const inputs = useRef<Record<string, HTMLInputElement | null>>({})

  const load = useCallback(async () => {
    try {
      setData(await call<StayRatesData>("kamra.api.stay_rates", { reservation }))
      setTyped({})
      setDrafts({})
      setPreview(null)
    } catch (e) {
      setLoadError(serverError(e))
    }
  }, [reservation])
  useEffect(() => {
    void load()
  }, [load])

  const digits = maxPriceDigits(moneyDigits())
  const openNights = useMemo(() => (data?.nights ?? []).filter((n) => !n.posted), [data])
  /** the nights whose price the desk changed */
  const changes = useMemo<Change[]>(
    () =>
      openNights
        .filter((n) => isOverride(typed[n.date], n.price, digits))
        .map((n) => ({ date: n.date, price: typed[n.date] })),
    [openNights, typed, digits],
  )
  const changesKey = JSON.stringify(changes)

  // one live total while the desk types: priced by the same code the save runs
  useEffect(() => {
    setPreviewError(null)
    if (!expanded || changes.length === 0) {
      setPreview(null)
      return
    }
    let live = true
    const timer = setTimeout(() => {
      call<Preview>("kamra.api.stay_prices_preview", { reservation, night_prices: changes })
        .then((p) => live && setPreview({ ...p, key: changesKey }))
        .catch((e) => {
          if (!live) return
          setPreview(null)
          setPreviewError(serverError(e))
        })
    }, 350)
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [expanded, changes, changesKey, reservation, recheck])
  // a save that was refused is explained until the desk changes something
  useEffect(() => setSaveError(null), [changes])
  // the button that opened the box is gone: put the cursor on the first night
  const firstOpen = openNights[0]?.date
  useEffect(() => {
    if (expanded && firstOpen) inputs.current[firstOpen]?.focus()
  }, [expanded, firstOpen])

  if (!data) return loadError ? <p role="alert" className="text-sm text-rose-700">{translate(loadError)}</p> : null
  if (!data.can_set || !["Confirmed", "Checked In"].includes(data.status)) return null
  // locked (another rule sets this booking's price): just say why
  if (!data.editable) {
    return data.why_not ? <p className="mt-3 text-xs text-zinc-500">{translate(data.why_not)}</p> : null
  }
  if (!expanded) {
    return (
      <div className="mt-3">
        <Button variant="outline" onClick={() => setExpanded(true)} data-stay-rates-open>
          {t("Change nightly prices")}
        </Button>
      </div>
    )
  }

  const plain = (n: number) => String(Number(n.toFixed(digits)))
  const priceOf = (n: Night) => typed[n.date] ?? n.price
  const roomTotal = data.nights.reduce((sum, n) => sum + priceOf(n), 0)
  const samePriceNow = openNights.length > 0 && openNights.every((n) => priceOf(n) === priceOf(openNights[0]))
  const basis = data.levy_inclusive
    ? data.tax_inclusive
      ? t("Prices include tax and the levy.")
      : t("Prices include the levy, before tax.")
    : data.tax_inclusive
      ? t("Prices include tax.")
      : t("Prices are before tax.")
  const fresh = preview !== null && preview.key === changesKey
  const problem = saveError ?? previewError
  const problemNight = problem ? nightInMessage(problem, data.nights.map((n) => n.date)) : null
  const dateLocale = uiDateLocale(moneyLocale())

  const draft = (key: string, text: string | null) =>
    setDrafts((d) => {
      const { [key]: _gone, ...rest } = d
      return text === null ? rest : { ...rest, [key]: text }
    })
  const setNight = (n: Night, price: number | null) =>
    setTyped((prev) => {
      const next = { ...prev }
      if (price === null || !isOverride(price, n.price, digits)) delete next[n.date]
      else next[n.date] = price
      return next
    })
  function typeNight(n: Night, text: string) {
    draft(n.date, text)
    if (text.trim() === "") return setNight(n, null)
    const price = parsePrice(text, digits)
    if (price !== null) setNight(n, price)
  }
  function typeTotal(text: string) {
    draft("total", text)
    const want = parsePrice(text, digits)
    if (want === null) return
    // the nights on the bill keep their price: the rest share what is left
    const kept = data!.nights.filter((n) => n.posted).reduce((sum, n) => sum + n.price, 0)
    if (!(want - kept > 0) || openNights.length === 0) return
    const parts = splitRoomTotal(want - kept, openNights.length, digits)
    setTyped(
      Object.fromEntries(
        openNights.flatMap((n, i) => (isOverride(parts[i], n.price, digits) ? [[n.date, parts[i]]] : [])),
      ),
    )
  }
  function typeSame(text: string) {
    draft("same", text)
    const price = parsePrice(text, digits)
    if (price !== null) setTyped(samePrice(price, openNights, digits))
  }
  function onNightKey(e: React.KeyboardEvent<HTMLInputElement>, date: string) {
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return
    const other = openNights[openNights.findIndex((n) => n.date === date) + (e.key === "ArrowUp" ? -1 : 1)]
    if (other) {
      e.preventDefault()
      inputs.current[other.date]?.focus()
      inputs.current[other.date]?.select()
    }
  }
  function close() {
    setTyped({})
    setDrafts({})
    setPreview(null)
    setSaveError(null)
    setExpanded(false)
  }

  async function save() {
    // the total the desk was shown goes with the save: the server refuses it if
    // the booking changed in between and this is no longer the new total
    if (!preview || preview.key !== changesKey) return
    setBusy(true)
    setSaveError(null)
    try {
      await call("kamra.api.set_stay_prices", {
        reservation,
        night_prices: changes,
        expected_total: preview.new_amount,
      })
      await load()
      setExpanded(false)
      onSaved?.()
    } catch (e) {
      setSaveError(serverError(e))
      setRecheck((n) => n + 1) // price it again: the desk looks at the new total before saving
    } finally {
      setBusy(false)
    }
  }

  const bulkInput = (id: string, key: string, value: string, disabled: boolean, onChange: (v: string) => void) => (
    <input
      id={id}
      inputMode="decimal"
      disabled={disabled}
      className={cn(
        "w-28 rounded-md border px-2 py-1 text-right tabular-nums disabled:bg-zinc-50 disabled:text-zinc-500",
        drafts[key] !== undefined && parsePrice(drafts[key], digits) === null ? "border-rose-400" : "border-zinc-300",
      )}
      value={value}
      aria-invalid={drafts[key] !== undefined && parsePrice(drafts[key], digits) === null}
      onChange={(e) => onChange(e.target.value)}
      onBlur={() => draft(key, null)}
    />
  )

  return (
    <div className="mt-3 space-y-3 rounded-xl border border-zinc-200 p-4" data-stay-rates>
      <h3 className="text-sm font-semibold text-zinc-800">{t("Rates for these dates")}</h3>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <span className="inline-flex items-center gap-2">
          <label htmlFor="stay-room-total" className="text-zinc-600">
            {t("Room total")}
          </label>
          <span className="inline-flex items-center gap-1">
            <span className="text-zinc-500">{cur()}</span>
            {bulkInput("stay-room-total", "total", drafts.total ?? plain(roomTotal), busy || openNights.length === 0, typeTotal)}
          </span>
        </span>
        <span className="inline-flex items-center gap-2">
          <label htmlFor="stay-same-price" className="text-zinc-600">
            {t("Same price every night")}
          </label>
          <span className="inline-flex items-center gap-1">
            <span className="text-zinc-500">{cur()}</span>
            {bulkInput(
              "stay-same-price",
              "same",
              drafts.same ?? (samePriceNow ? plain(priceOf(openNights[0])) : ""),
              busy || openNights.length === 0,
              typeSame,
            )}
          </span>
        </span>
      </div>
      <p className="text-xs text-zinc-400">{basis}</p>

      <ul className="divide-y divide-zinc-100 text-sm">
        {data.nights.map((n) => {
          const edited = isOverride(typed[n.date], n.price, digits)
          const bad =
            drafts[n.date] !== undefined && drafts[n.date].trim() !== "" && parsePrice(drafts[n.date], digits) === null
          const label = nightLabel(n.date, dateLocale)
          return (
            <li
              key={n.date}
              className={cn(
                "flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5",
                edited && "-mx-2 rounded-md bg-brand-50 px-2",
              )}
            >
              <span className="w-28 shrink-0 text-zinc-500">{label}</span>
              {n.posted ? (
                <span className="font-medium tabular-nums">{money(n.price)}</span>
              ) : (
                <span className="inline-flex items-center gap-1">
                  <span className="text-zinc-500">{cur()}</span>
                  <input
                    ref={(el) => {
                      inputs.current[n.date] = el
                    }}
                    inputMode="decimal"
                    disabled={busy}
                    aria-label={t("Price for {d}", { d: label })}
                    aria-invalid={bad || problemNight === n.date}
                    className={cn(
                      "w-28 rounded-md border px-2 py-1 text-right font-medium tabular-nums",
                      bad || problemNight === n.date ? "border-rose-400" : edited ? "border-brand-600" : "border-zinc-300",
                    )}
                    value={drafts[n.date] ?? plain(priceOf(n))}
                    onChange={(e) => typeNight(n, e.target.value)}
                    onKeyDown={(e) => onNightKey(e, n.date)}
                    onBlur={() => draft(n.date, null)}
                  />
                </span>
              )}
              {n.posted ? (
                <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">{t("On the bill")}</span>
              ) : (
                n.rate !== priceOf(n) && (
                  <>
                    <span className="text-xs text-zinc-400 tabular-nums">{t("BAR {r}", { r: money(n.rate) })}</span>
                    <button
                      type="button"
                      className="text-xs text-brand-700 underline"
                      onClick={() => {
                        draft(n.date, null)
                        setNight(n, n.rate)
                      }}
                    >
                      {t("Back to BAR")}
                    </button>
                  </>
                )
              )}
              {n.hand_set && !edited && !n.posted && (
                <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-800">{t("Set by hand")}</span>
              )}
              {problem && problemNight === n.date && (
                <p role="alert" className="w-full text-xs text-rose-700">
                  {translate(problem)}
                </p>
              )}
            </li>
          )
        })}
      </ul>

      {data.nights.some((n) => n.posted) && (
        <p className="text-xs text-zinc-500">{t("Nights already on the bill keep their price.")}</p>
      )}
      <p className="text-xs text-zinc-400">{t("Nights you leave alone keep the price they were booked at.")}</p>
      {problem && !problemNight && (
        <p role="alert" className="text-sm text-rose-700">
          {translate(problem)}
        </p>
      )}

      {changes.length > 0 && !previewError && (
        <div className="space-y-0.5 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900" aria-live="polite">
          {fresh && preview ? (
            <>
              <p className="font-medium">
                {t("New total {to}, was {from}, {diff}", {
                  to: money(preview.new_amount),
                  from: money(preview.current_amount),
                  diff: signed(preview.difference),
                })}
              </p>
              {preview.paid > 0 &&
                (preview.new_balance === null ? (
                  <p>{t("Paid so far {paid}.", { paid: money(preview.paid) })}</p>
                ) : preview.new_balance >= 0 ? (
                  <p>
                    {t("Paid so far {paid}. Still to pay after this change: {balance}.", {
                      paid: money(preview.paid),
                      balance: money(preview.new_balance),
                    })}
                  </p>
                ) : (
                  <p>
                    {t("Paid so far {paid}. The guest is {credit} in credit after this change.", {
                      paid: money(preview.paid),
                      credit: money(-preview.new_balance),
                    })}
                  </p>
                ))}
            </>
          ) : (
            <p>{t("Checking the new total…")}</p>
          )}
        </div>
      )}

      <div className="flex gap-2">
        {changes.length > 0 && (
          <Button disabled={busy || !fresh} onClick={() => void save()}>
            {busy ? t("Saving…") : fresh && preview ? t("Save new total {amount}", { amount: money(preview.new_amount) }) : t("Save")}
          </Button>
        )}
        <Button variant="outline" disabled={busy} onClick={close}>
          {t("Cancel")}
        </Button>
      </div>
    </div>
  )
}
