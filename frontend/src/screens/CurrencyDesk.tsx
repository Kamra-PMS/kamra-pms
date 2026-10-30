import { useCallback, useEffect, useState } from "react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { useCashierAuth } from "../lib/cashierAuth"
import { useAuth } from "../lib/auth"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { moneyLocale } from "../lib/money"
import { useT, t as translate } from "../lib/i18n"


const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), {
    maximumFractionDigits: 2,
  })

const FETCH_ROLES = ["Finance", "Hotel Admin", "System Manager", "Administrator"]

export default function CurrencyDesk() {
  const { lang, t } = useT()
  const { roles } = useAuth()
  const canFetch = roles.some((r) => FETCH_ROLES.includes(r))
  const [fetching, setFetching] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const { withPin } = useCashierAuth()
  const [rates, setRates] = useState<
    {
      currency: string
      buy_rate: number
      sell_rate: number
      service_tax_pct: number
      max_exchange?: number
      rate_date?: string
      source?: string
      set_by?: string
      market_rate?: number
    }[]
  >([])
  const [history, setHistory] = useState<Record<string, unknown>[]>([])
  const [currency, setCurrency] = useState("USD")
  const [fxAmount, setFxAmount] = useState("100")
  const [direction, setDirection] = useState<"Buy" | "Sell">("Buy")
  const [calc, setCalc] = useState<Record<string, number | string> | null>(null)
  const [newRate, setNewRate] = useState({
    currency: "USD",
    buy: "83",
    sell: "84",
    tax: "0",
  })
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const r = await call<{ rates: typeof rates }>(
        "kamra.ledger.list_exchange_rates",
        { property: getCurrentProperty() },
      )
      setRates(r.rates)
      const h = await call<{ transactions: Record<string, unknown>[] }>(
        "kamra.ledger.exchange_history",
        { property: getCurrentProperty() },
      )
      setHistory(h.transactions)
    } catch (e) {
      setErr(serverError(e))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const doCalc = async () => {
    try {
      const out = await call<Record<string, number | string>>(
        "kamra.ledger.currency_calculator",
        {
          property: getCurrentProperty(),
          currency,
          fx_amount: Number(fxAmount),
          direction,
        },
      )
      setCalc(out)
    } catch (e) {
      setErr(serverError(e))
    }
  }

  const post = async () => {
    try {
      await withPin(async (pin) => {
        await call("kamra.ledger.post_exchange", {
          property: getCurrentProperty(),
          currency,
          fx_amount: Number(fxAmount),
          direction,
          pin,
        })
      })
      await load()
    } catch (e) {
      setErr(serverError(e))
    }
  }

  const fetchRates = async () => {
    setFetching(true)
    setErr(null)
    setNote(null)
    try {
      const out = await call<{
        updated: string[]
        kept_manual: string[]
        not_offered: string[]
      }>("kamra.ledger.fetch_exchange_rates", { property: getCurrentProperty() })
      const parts = [t("Updated: {v0}", { v0: out.updated.join(", ") || "-" })]
      if (out.kept_manual.length)
        parts.push(t("Kept typed-in rates: {v0}", { v0: out.kept_manual.join(", ") }))
      if (out.not_offered.length)
        parts.push(t("Not offered online: {v0}", { v0: out.not_offered.join(", ") }))
      setNote(parts.join(". "))
      await load()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setFetching(false)
    }
  }

  const saveRate = async () => {
    try {
      await call("kamra.ledger.upsert_exchange_rate", {
        property: getCurrentProperty(),
        currency: newRate.currency,
        buy_rate: Number(newRate.buy),
        sell_rate: Number(newRate.sell),
        service_tax_pct: Number(newRate.tax),
      })
      await load()
    } catch (e) {
      setErr(serverError(e))
    }
  }

  return (
    <div className="w-full space-y-4">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{translate("Cashier")}</p>
        <h1 className="text-2xl font-semibold">{translate("Currency Desk")}</h1>
      </div>
      {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : null}
      {note ? <p className="text-sm text-emerald-700">{note}</p> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{translate("Calculator")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <select
                className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
              >
                {(rates.length ? rates.map((r) => r.currency) : ["USD", "EUR", "GBP"]).map(
                  (c) => (
                    <option key={c}>{c}</option>
                  ),
                )}
              </select>
              <select
                className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                value={direction}
                onChange={(e) => setDirection(e.target.value as "Buy" | "Sell")}
              >
                <option value="Buy">{translate("Buy (guest sells FX)")}</option>
                <option value="Sell">{translate("Sell (guest buys FX)")}</option>
              </select>
              <input
                className="w-28 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                value={fxAmount}
                onChange={(e) => setFxAmount(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => void doCalc()}>{translate("Calculate")}</Button>
              <Button onClick={() => void post()}>{translate("Post exchange")}</Button>
            </div>
            {calc ? (
              <p className="text-sm text-zinc-600">
                {(lang !== "en") ? t("Exchange rate") : translate("Rate")} {String(calc.exchange_rate)}{translate(" → local")}{" "}
                <span className="font-semibold tabular-nums">
                  {inr(calc.local_amount)}
                </span>
                {Number(calc.service_tax) > 0
                  ? translate(" + tax {v0}", { v0: String(inr(calc.service_tax)) })
                  : ""}{" "}
                = {inr(calc.total)}
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("Set rate")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <input
              className="w-20 rounded-lg border px-2 py-1.5 text-sm"
              value={newRate.currency}
              onChange={(e) =>
                setNewRate((r) => ({ ...r, currency: e.target.value }))
              }
              placeholder={translate("CCY")}
            />
            <input
              className="w-24 rounded-lg border px-2 py-1.5 text-sm"
              value={newRate.buy}
              onChange={(e) => setNewRate((r) => ({ ...r, buy: e.target.value }))}
              placeholder={translate("Buy")}
            />
            <input
              className="w-24 rounded-lg border px-2 py-1.5 text-sm"
              value={newRate.sell}
              onChange={(e) =>
                setNewRate((r) => ({ ...r, sell: e.target.value }))
              }
              placeholder={translate("Sell")}
            />
            <Button variant="outline" onClick={() => void saveRate()}>{translate("Save")}</Button>
            {canFetch ? (
              <Button variant="outline" disabled={fetching} onClick={() => void fetchRates()}>
                {fetching ? t("Fetching...") : t("Fetch today's rates")}
              </Button>
            ) : null}
            <p className="w-full text-xs text-zinc-500">
              {t("Rates are hotel currency per 1 unit of the foreign currency, for today's business date. A guest paying a bill in foreign money is converted at today's Buy rate.")}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="overflow-x-auto rounded-xl border bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-xs uppercase text-zinc-400">
            <tr>
              <th className="px-3 py-2">{translate("Currency")}</th>
              <th className="px-3 py-2">{translate("Buy")}</th>
              <th className="px-3 py-2">{translate("Sell")}</th>
              <th className="px-3 py-2">{translate("Tax %")}</th>
              <th className="px-3 py-2">{t("Set on")}</th>
              <th className="px-3 py-2">{t("Source")}</th>
            </tr>
          </thead>
          <tbody>
            {rates.map((r) => (
              <tr key={r.currency} className="border-t">
                <td className="px-3 py-2 font-medium">{r.currency}</td>
                <td className="px-3 py-2 tabular-nums">{r.buy_rate}</td>
                <td className="px-3 py-2 tabular-nums">{r.sell_rate}</td>
                <td className="px-3 py-2">{r.service_tax_pct}</td>
                <td className="px-3 py-2 tabular-nums">{r.rate_date}</td>
                <td className="px-3 py-2 text-xs text-zinc-500">
                  {r.source === "Online"
                    ? t("Online, market {v0}", { v0: String(r.market_rate ?? "") })
                    : t("Manual")}
                  {r.set_by ? ` · ${r.set_by}` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rates.some((r) => r.source === "Online") ? (
          <p className="border-t px-3 py-2 text-xs text-zinc-400">
            <a href="https://www.exchangerate-api.com" target="_blank" rel="noreferrer">
              Rates By Exchange Rate API
            </a>
          </p>
        ) : null}
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold">{translate("Today's exchanges")}</h2>
        <div className="overflow-x-auto rounded-xl border bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b text-xs uppercase text-zinc-400">
              <tr>
                <th className="px-3 py-2">{translate("Dir")}</th>
                <th className="px-3 py-2">{translate("FX")}</th>
                <th className="px-3 py-2">{(lang !== "en") ? t("Exchange rate") : translate("Rate")}</th>
                <th className="px-3 py-2">{translate("Local")}</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={String(h.name)} className="border-t">
                  <td className="px-3 py-2">{String(h.direction)}</td>
                  <td className="px-3 py-2">
                    {String(h.fx_amount)} {String(h.currency)}
                  </td>
                  <td className="px-3 py-2">{String(h.exchange_rate)}</td>
                  <td className="px-3 py-2 tabular-nums">
                    {inr(h.local_amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
