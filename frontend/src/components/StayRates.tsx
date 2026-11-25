import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "./ui/button"
import { call } from "../lib/api"
import { cur, fmtAmount, moneyDigits } from "../lib/money"
import { isOverride, maxPriceDigits, parsePrice, splitRoomTotal } from "../lib/nightPrices"
import { serverError } from "../lib/resource"
import { t as translate, useT } from "../lib/i18n"
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
}

/** "Rates for these dates" on a saved booking: the same box the desk uses on
 *  New booking, for a stay that already exists. Nights already on the bill
 *  are closed; every night the desk does not change keeps the price it was
 *  booked at. Shown only to someone who holds the "Set night prices" right. */
export default function StayRates({ reservation, onSaved }: { reservation: string; onSaved?: () => void }) {
  const { t } = useT()
  const [data, setData] = useState<StayRatesData | null>(null)
  const [typed, setTyped] = useState<Record<string, number>>({})
  // what is being typed, before it is a valid price (a night's text, or the room total)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [preview, setPreview] = useState<Preview | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputs = useRef<Record<string, HTMLInputElement | null>>({})

  const load = useCallback(async () => {
    try {
      setData(await call<StayRatesData>("kamra.api.stay_rates", { reservation }))
      setTyped({})
      setDrafts({})
      setPreview(null)
    } catch (e) {
      setError(serverError(e))
    }
  }, [reservation])
  useEffect(() => {
    void load()
  }, [load])

  if (!data) return error ? <p role="alert" className="text-sm text-rose-700">{translate(error)}</p> : null
  if (!data.can_set || !["Confirmed", "Checked In"].includes(data.status)) return null

  const digits = maxPriceDigits(moneyDigits())
  const plain = (n: number) => String(Number(n.toFixed(digits)))
  const off = !data.editable
  const open = data.nights.filter((n) => !n.posted)
  const priceOf = (n: Night) => typed[n.date] ?? n.price
  /** the nights whose price the desk changed, as the server takes them */
  const changes = open
    .filter((n) => isOverride(typed[n.date], n.price, digits))
    .map((n) => ({ date: n.date, price: typed[n.date] }))
  const roomTotal = data.nights.reduce((sum, n) => sum + priceOf(n), 0)
  const basis = data.levy_inclusive
    ? data.tax_inclusive
      ? t("Prices include tax and the levy.")
      : t("Prices include the levy, before tax.")
    : data.tax_inclusive
      ? t("Prices include tax.")
      : t("Prices are before tax.")

  const draft = (key: string, text: string | null) =>
    setDrafts((d) => {
      const { [key]: _gone, ...rest } = d
      return text === null ? rest : { ...rest, [key]: text }
    })
  const setNight = (n: Night, price: number | null) => {
    setPreview(null)
    setTyped((cur) => {
      const next = { ...cur }
      if (price === null || !isOverride(price, n.price, digits)) delete next[n.date]
      else next[n.date] = price
      return next
    })
  }
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
    if (!(want - kept > 0) || open.length === 0) return
    const parts = splitRoomTotal(want - kept, open.length, digits)
    setPreview(null)
    setTyped(
      Object.fromEntries(
        open.flatMap((n, i) => (isOverride(parts[i], n.price, digits) ? [[n.date, parts[i]]] : [])),
      ),
    )
  }
  function onNightKey(e: React.KeyboardEvent<HTMLInputElement>, i: number) {
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return
    const other = open[open.findIndex((n) => n.date === data!.nights[i].date) + (e.key === "ArrowUp" ? -1 : 1)]
    if (other) {
      e.preventDefault()
      inputs.current[other.date]?.focus()
      inputs.current[other.date]?.select()
    }
  }

  async function review() {
    setBusy(true)
    setError(null)
    try {
      setPreview(await call<Preview>("kamra.api.stay_prices_preview", { reservation, night_prices: changes }))
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }
  async function save() {
    setBusy(true)
    setError(null)
    try {
      await call("kamra.api.set_stay_prices", { reservation, night_prices: changes, confirm_price: 1 })
      await load()
      onSaved?.()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }
  const signed = (n: number) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${cur()}${fmtAmount(Math.abs(n))}`

  return (
    <div className="mt-3 space-y-3 rounded-xl border border-zinc-200 p-4" data-stay-rates>
      <h3 className="text-sm font-semibold text-zinc-800">{t("Rates for these dates")}</h3>

      {!off && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <label htmlFor="stay-room-total" className="text-zinc-600">
            {t("Room total")}
          </label>
          <span className="inline-flex items-center gap-1">
            <span className="text-zinc-500">{cur()}</span>
            <input
              id="stay-room-total"
              inputMode="decimal"
              disabled={busy || open.length === 0}
              className={cn(
                "w-28 rounded-md border px-2 py-1 text-right tabular-nums disabled:bg-zinc-50 disabled:text-zinc-500",
                drafts.total !== undefined && parsePrice(drafts.total, digits) === null
                  ? "border-rose-400"
                  : "border-zinc-300",
              )}
              value={drafts.total ?? plain(roomTotal)}
              aria-invalid={drafts.total !== undefined && parsePrice(drafts.total, digits) === null}
              onChange={(e) => typeTotal(e.target.value)}
              onBlur={() => draft("total", null)}
            />
          </span>
          <span className="text-xs text-zinc-400">{basis}</span>
        </div>
      )}

      <ul className="divide-y divide-zinc-100 text-sm">
        {data.nights.map((n, i) => {
          const edited = isOverride(typed[n.date], n.price, digits)
          const bad = drafts[n.date] !== undefined && drafts[n.date].trim() !== "" && parsePrice(drafts[n.date], digits) === null
          return (
            <li
              key={n.date}
              className={cn(
                "flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5",
                edited && "-mx-2 rounded-md bg-brand-50 px-2",
              )}
            >
              <span className="w-24 text-zinc-500">{n.date.slice(5)}</span>
              {off || n.posted ? (
                <span className="font-medium tabular-nums">
                  {cur()}
                  {fmtAmount(n.price)}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1">
                  <span className="text-zinc-500">{cur()}</span>
                  <input
                    ref={(el) => {
                      inputs.current[n.date] = el
                    }}
                    inputMode="decimal"
                    disabled={busy}
                    aria-label={t("Price for {d}", { d: n.date })}
                    aria-invalid={bad}
                    className={cn(
                      "w-28 rounded-md border px-2 py-1 text-right font-medium tabular-nums",
                      bad ? "border-rose-400" : edited ? "border-brand-600" : "border-zinc-300",
                    )}
                    value={drafts[n.date] ?? plain(priceOf(n))}
                    onChange={(e) => typeNight(n, e.target.value)}
                    onKeyDown={(e) => onNightKey(e, i)}
                    onBlur={() => draft(n.date, null)}
                  />
                </span>
              )}
              {n.posted ? (
                <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">{t("On the bill")}</span>
              ) : (
                !off &&
                n.rate !== priceOf(n) && (
                  <>
                    <span className="text-xs text-zinc-400 tabular-nums">
                      {t("BAR {r}", { r: `${cur()}${fmtAmount(n.rate)}` })}
                    </span>
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
            </li>
          )
        })}
      </ul>

      {data.why_not && <p className="text-xs text-zinc-500">{translate(data.why_not)}</p>}
      {!data.why_not && data.nights.some((n) => n.posted) && (
        <p className="text-xs text-zinc-500">{t("Nights already on the bill keep their price.")}</p>
      )}
      {!data.why_not && (
        <p className="text-xs text-zinc-400">
          {t("Nights you leave alone keep the price they were booked at.")}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-rose-700">
          {translate(error)}
        </p>
      )}

      {preview && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {t("The booking total changes from {from} to {to} ({diff}).", {
            from: `${cur()}${fmtAmount(preview.current_amount)}`,
            to: `${cur()}${fmtAmount(preview.new_amount)}`,
            diff: signed(preview.difference),
          })}
        </p>
      )}
      {changes.length > 0 && (
        <div className="flex gap-2">
          {preview ? (
            <Button disabled={busy} onClick={() => void save()}>
              {busy ? t("Saving…") : t("Save prices")}
            </Button>
          ) : (
            <Button disabled={busy} onClick={() => void review()}>
              {busy ? t("Checking…") : t("Review change")}
            </Button>
          )}
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => {
              setTyped({})
              setDrafts({})
              setPreview(null)
              setError(null)
            }}
          >
            {t("Cancel")}
          </Button>
        </div>
      )}
    </div>
  )
}
