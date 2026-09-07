import { useCallback, useEffect, useState } from "react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { useCashierAuth } from "../lib/cashierAuth"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { moneyLocale } from "../lib/money"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), {
    maximumFractionDigits: 2,
  })

export default function CurrencyDesk() {
  const { withPin } = useCashierAuth()
  const [rates, setRates] = useState<
    {
      currency: string
      buy_rate: number
      sell_rate: number
      service_tax_pct: number
      max_exchange?: number
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
    <div className="mx-auto max-w-4xl space-y-4 p-4 sm:p-6">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
          Cashier
        </p>
        <h1 className="text-2xl font-semibold">Currency Desk</h1>
      </div>
      {err ? <p className="text-sm text-rose-600">{err}</p> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Calculator</CardTitle>
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
                <option value="Buy">Buy (guest sells FX)</option>
                <option value="Sell">Sell (guest buys FX)</option>
              </select>
              <input
                className="w-28 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                value={fxAmount}
                onChange={(e) => setFxAmount(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => void doCalc()}>
                Calculate
              </Button>
              <Button onClick={() => void post()}>Post exchange</Button>
            </div>
            {calc ? (
              <p className="text-sm text-zinc-600">
                Rate {String(calc.exchange_rate)} → local{" "}
                <span className="font-semibold tabular-nums">
                  {inr(calc.local_amount)}
                </span>
                {Number(calc.service_tax) > 0
                  ? ` + tax ${inr(calc.service_tax)}`
                  : ""}{" "}
                = {inr(calc.total)}
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Set rate</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <input
              className="w-20 rounded-lg border px-2 py-1.5 text-sm"
              value={newRate.currency}
              onChange={(e) =>
                setNewRate((r) => ({ ...r, currency: e.target.value }))
              }
              placeholder="CCY"
            />
            <input
              className="w-24 rounded-lg border px-2 py-1.5 text-sm"
              value={newRate.buy}
              onChange={(e) => setNewRate((r) => ({ ...r, buy: e.target.value }))}
              placeholder="Buy"
            />
            <input
              className="w-24 rounded-lg border px-2 py-1.5 text-sm"
              value={newRate.sell}
              onChange={(e) =>
                setNewRate((r) => ({ ...r, sell: e.target.value }))
              }
              placeholder="Sell"
            />
            <Button variant="outline" onClick={() => void saveRate()}>
              Save
            </Button>
          </CardContent>
        </Card>
      </div>

      <div className="overflow-x-auto rounded-xl border bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-xs uppercase text-zinc-400">
            <tr>
              <th className="px-3 py-2">Currency</th>
              <th className="px-3 py-2">Buy</th>
              <th className="px-3 py-2">Sell</th>
              <th className="px-3 py-2">Tax %</th>
            </tr>
          </thead>
          <tbody>
            {rates.map((r) => (
              <tr key={r.currency} className="border-t">
                <td className="px-3 py-2 font-medium">{r.currency}</td>
                <td className="px-3 py-2 tabular-nums">{r.buy_rate}</td>
                <td className="px-3 py-2 tabular-nums">{r.sell_rate}</td>
                <td className="px-3 py-2">{r.service_tax_pct}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold">Today&apos;s exchanges</h2>
        <div className="overflow-x-auto rounded-xl border bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b text-xs uppercase text-zinc-400">
              <tr>
                <th className="px-3 py-2">Dir</th>
                <th className="px-3 py-2">FX</th>
                <th className="px-3 py-2">Rate</th>
                <th className="px-3 py-2">Local</th>
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
