/*  What the function actually made.

    Every banquet system prices the sell side. Almost none show the buy
    side, so a manager quotes on instinct and finds out at month end. This
    is the other half: what the food and the hired kit cost, what the input
    tax credit is worth, what's left, and where the quote and the night
    disagreed.

    The input-credit line is the one people get wrong. Bill food under the
    5% scheme and the hotel claims nothing back on what it bought; bill the
    same food as part of an 18% banquet supply and the credit is real. So
    the screen states which case you're in rather than quietly assuming. */

import { useCallback, useEffect, useState } from "react"
import {
  AlertTriangle,
  ChefHat,
  PackageCheck,
  Plus,
  TrendingUp,
} from "lucide-react"

import {
  banquet,
  type FunctionEconomics,
  type FunctionSheet,
  type KitchenIndent,
} from "../../lib/api"
import { listResource, serverError, type Row } from "../../lib/resource"
import { Button } from "../../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card"
import { Sheet } from "../../components/ui/sheet"
import { taxLabel } from "../../lib/money"
import { Empty, ErrorNote, Field, inputCls, inr, Select } from "./shared"
import { t as translate, useUILanguage } from "../../lib/i18n"

type Act = (work: () => Promise<unknown>) => Promise<void>

export default function Economics({
  fn,
  busy,
  act,
}: {
  fn: FunctionSheet
  busy: boolean
  act: Act
}) {
  useUILanguage()
  const [data, setData] = useState<FunctionEconomics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [indent, setIndent] = useState<KitchenIndent | null>(null)
  const [counting, setCounting] = useState(false)
  const [supp, setSupp] = useState(false)

  const load = useCallback(() => {
    banquet
      .economics(fn.name)
      .then(setData)
      .catch((e) => setError(serverError(e)))
  }, [fn])
  useEffect(load, [load])

  if (!data) return <Empty>{translate(error) ?? translate("Loading…")}</Empty>
  const m = data.margin
  const healthy = m.percent >= 35

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile label={translate("Revenue")} value={inr(data.revenue.taxable)} sub={translate("before tax")} />
        <Tile
          label={translate("Cost")}
          value={inr(data.cost.net)}
          sub={
            (data.cost.itc_eligible
              ? translate("after {v0} credit", { v0: String(inr(data.cost.input_tax)) })
              : translate("no credit claimable"))
          }
          tone="text-zinc-600"
        />
        <Tile
          label={translate("Gross margin")}
          value={inr(m.gross)}
          sub={translate("{v0} per head", { v0: String(inr(m.per_pax)) })}
          tone={healthy ? "text-emerald-700" : "text-amber-700"}
        />
        <Tile
          label={translate("Margin")}
          value={`${m.percent}%`}
          sub={(healthy ? translate("healthy") : translate("thin - check the discount"))}
          tone={healthy ? "text-emerald-700" : "text-amber-700"}
        />
      </div>

      {data.uncosted_lines.length > 0 && (
        <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <p>
            <span className="font-medium">
              {data.uncosted_lines.length}{translate(" line")}{data.uncosted_lines.length === 1 ? "" : translate("s")}{translate(" cost nothing yet")}</span>{" "}
           - {data.uncosted_lines.slice(0, 4).join(", ")}
            {data.uncosted_lines.length > 4 ? "…" : ""}{translate(". The margin above is optimistic until they carry a cost: choose the menu's dishes, or put a cost rate on the service in the catalogue.")}</p>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>
              <span className="inline-flex items-center gap-1.5">
                <TrendingUp className="size-4" />{translate("Where the money goes")}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Bar
              label={translate("Food")}
              value={data.cost.food}
              of={data.revenue.taxable}
              tone="bg-orange-400"
            />
            <Bar
              label={translate("Services & hire")}
              value={data.cost.service}
              of={data.revenue.taxable}
              tone="bg-sky-400"
            />
            <Bar
              label={translate("Margin")}
              value={Math.max(0, m.gross)}
              of={data.revenue.taxable}
              tone="bg-emerald-500"
            />
            <dl className="mt-3 space-y-1 border-t border-zinc-100 pt-3">
              <Line label={translate("Subtotal")} value={data.revenue.subtotal} />
              {data.revenue.discount > 0 && (
                <Line label={translate("Discount")} value={-data.revenue.discount} />
              )}
              {data.revenue.service_charge > 0 && (
                <Line
                  label={translate("Service charge")}
                  value={data.revenue.service_charge}
                />
              )}
              {data.revenue.supplementary > 0 && (
                <Line
                  label={translate("Ordered on the night")}
                  value={data.revenue.supplementary}
                  tone="text-amber-700"
                />
              )}
              <Line label={translate("Taxable")} value={data.revenue.taxable} bold />
              <Line
                label={translate("{v0} charged", { v0: String(taxLabel()) })}
                value={data.revenue.tax}
                tone="text-zinc-400"
              />
              <Line
                label={translate("{v0} paid on cost", { v0: String(taxLabel()) })}
                value={data.cost.input_tax}
                tone="text-zinc-400"
              />
            </dl>
            <p className="pt-1 text-xs text-zinc-400">
              {data.cost.itc_eligible
                ? translate("Billed at 12% or more, so the {v0} paid on the cost side is claimable as input credit - the margin above nets it off.", { v0: String(inr(data.cost.input_tax)) })
                : translate("Billed under the 5% food scheme, so the {v0} paid on purchases is NOT claimable. It stays in the cost.", { v0: String(inr(data.cost.input_tax)) })}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>
              <span className="inline-flex items-center gap-1.5">
                <ChefHat className="size-4" />{translate("The kitchen")}</span>
            </CardTitle>
            <Button
              variant="outline"
              onClick={() =>
                act(async () => setIndent(await banquet.indent(fn.name)))
              }
              disabled={busy}
            >{translate("Build the indent")}</Button>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-zinc-500">{translate("The chosen dishes, exploded through their recipes at")}{" "}
              {fn.billable_pax}{translate(" pax, checked against what's on the shelf - the sheet that has always been written by hand between the event order and the store room.")}</p>
            {fn.selections?.length ? (
              <p className="mt-2 text-xs text-emerald-700">
                {fn.selections.length}{translate(" dish")}{fn.selections.length === 1 ? "" : translate("es")}{translate(" chosen.")}</p>
            ) : (
              <p className="mt-2 text-xs text-amber-700">{translate("Nothing chosen yet - compose the menu first.")}</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{translate("Quoted vs served")}</CardTitle>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setSupp(true)}>
              <Plus className="size-4" />{translate("Ordered on the night")}</Button>
            <Button onClick={() => setCounting(true)}>
              <PackageCheck className="size-4" />{translate("Count the night")}</Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-400">
                  <th className="py-2 pr-3 font-medium">{translate("Item")}</th>
                  <th className="py-2 pr-3 text-right font-medium">{translate("Quoted")}</th>
                  <th className="py-2 pr-3 text-right font-medium">{translate("Served")}</th>
                  <th className="py-2 pr-3 text-right font-medium">{translate("Revenue")}</th>
                  <th className="py-2 pr-3 text-right font-medium">{translate("Cost")}</th>
                  <th className="py-2 text-right font-medium">{translate("Margin")}</th>
                </tr>
              </thead>
              <tbody>
                {data.lines.map((l) => (
                  <tr key={l.row} className="border-b border-zinc-100">
                    <td className="py-1.5 pr-3">
                      {l.item_name}
                      {l.is_supplementary && (
                        <span className="ml-1.5 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">{translate("on the night")}</span>
                      )}
                      {!l.chargeable && (
                        <span className="ml-1.5 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">{translate("free")}</span>
                      )}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums text-zinc-400">
                      {l.quoted_qty % 1 === 0
                        ? l.quoted_qty
                        : l.quoted_qty.toFixed(2)}{" "}
                      {l.uom}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">
                      {l.actual_qty === null ? (
                        <span className="text-zinc-300"> - </span>
                      ) : (
                        <>
                          {l.actual_qty}
                          {l.variance !== 0 && (
                            <span
                              className={
                                l.variance > 0
                                  ? "ml-1 text-emerald-600"
                                  : "ml-1 text-rose-600"
                              }
                            >
                              {l.variance > 0 ? "+" : ""}
                              {l.variance}
                            </span>
                          )}
                        </>
                      )}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">
                      {inr(l.net_amount)}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums text-zinc-500">
                      {l.cost_amount ? inr(l.cost_amount) : "-"}
                    </td>
                    <td
                      className={
                        "py-1.5 text-right tabular-nums " +
                        (l.margin < 0 ? "text-rose-700" : "")
                      }
                    >
                      {l.cost_amount ? inr(l.margin) : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {indent && (
        <IndentSheet
          indent={indent}
          property={fn.property}
          busy={busy}
          onClose={() => setIndent(null)}
          onIssue={(outlet) =>
            act(async () => {
              await banquet.issueIndent(fn.name, outlet)
              setIndent(null)
            })
          }
        />
      )}
      {counting && (
        <CountSheet
          data={data}
          pax={fn.billable_pax}
          busy={busy}
          onClose={() => setCounting(false)}
          onSave={(rows, pax) =>
            act(async () => {
              await banquet.recordConsumption(fn.name, rows, pax)
              setCounting(false)
              load()
            })
          }
        />
      )}
      {supp && (
        <SupplementarySheet
          busy={busy}
          onClose={() => setSupp(false)}
          onAdd={(params) =>
            act(async () => {
              await banquet.addSupplementary(fn.name, params)
              setSupp(false)
              load()
            })
          }
        />
      )}
    </div>
  )
}

/* ── pieces ───────────────────────────────────────────────────────────── */

function Tile({
  label,
  value,
  sub,
  tone = "",
}: {
  label: string
  value: string
  sub?: string
  tone?: string
}) {
  useUILanguage()
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
        {translate(label)}
      </p>
      <p className={"mt-1 text-xl font-semibold tabular-nums " + tone}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-zinc-400">{translate(sub)}</p>}
    </div>
  )
}

function Bar({
  label,
  value,
  of,
  tone,
}: {
  label: string
  value: number
  of: number
  tone: string
}) {
  useUILanguage()
  const pct = of ? Math.min(100, (value / of) * 100) : 0
  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="text-zinc-600">{translate(label)}</span>
        <span className="tabular-nums text-zinc-500">
          {inr(value)} <span className="text-zinc-400">({pct.toFixed(0)}%)</span>
        </span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-zinc-100">
        <div className={"h-full " + tone} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function Line({
  label,
  value,
  bold,
  tone = "",
}: {
  label: string
  value: number
  bold?: boolean
  tone?: string
}) {
  useUILanguage()
  return (
    <div
      className={
        "flex justify-between " +
        (bold ? "border-t border-zinc-200 pt-1 font-semibold " : "") +
        tone
      }
    >
      <dt className={bold ? "" : "text-zinc-500"}>{translate(label)}</dt>
      <dd className="tabular-nums">{inr(value)}</dd>
    </div>
  )
}

function IndentSheet({
  indent,
  property,
  busy,
  onClose,
  onIssue,
}: {
  indent: KitchenIndent
  property: string
  busy: boolean
  onClose: () => void
  onIssue: (outlet: string) => void
}) {
  useUILanguage()
  const [outlets, setOutlets] = useState<Row[]>([])
  const [outlet, setOutlet] = useState("")
  useEffect(() => {
    listResource("POS Outlet", {
      fields: ["name", "outlet_name"],
      filters: [["property", "=", property]],
    })
      .then((r) => {
        setOutlets(r)
        if (r.length) setOutlet(String(r[0].name))
      })
      .catch(() => {})
  }, [property])

  return (
    <Sheet
      title={translate("Kitchen indent")}
      description={translate("{v0} pax · {v1} · {v2}", { v0: String(indent.pax), v1: String(indent.venue), v2: String(indent.event_date) })}
      onClose={onClose}
      wide
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-sm text-zinc-500">
            {inr(indent.total_cost)}{translate(" of ingredients")}{indent.shortfall_lines > 0 && (
              <span className="text-amber-700">
                {" "}
                · {indent.shortfall_lines}{translate(" short on the shelf")}</span>
            )}
          </span>
          <div className="flex items-end gap-2">
            <Field label={translate("Issue from")}>
              <select
                className={inputCls + " !w-44"}
                value={outlet}
                onChange={(e) => setOutlet(e.target.value)}
              >
                {outlets.map((o) => (
                  <option key={o.name} value={o.name}>
                    {String(o.outlet_name ?? o.name)}
                  </option>
                ))}
              </select>
            </Field>
            <Button variant="outline" onClick={() => window.print()}>{translate("Print")}</Button>
            <Button disabled={busy || !outlet} onClick={() => onIssue(outlet)}>{translate("Issue the stock")}</Button>
          </div>
        </div>
      }
    >
      {indent.uncosted.length > 0 && (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">{translate("No recipe for ")}{indent.uncosted.join(", ")}{translate(" - those dishes aren't on this list and won't be pulled from stock.")}</div>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-400">
            <th className="py-2 pr-3 font-medium">{translate("Ingredient")}</th>
            <th className="py-2 pr-3 text-right font-medium">{translate("Need")}</th>
            <th className="py-2 pr-3 text-right font-medium">{translate("On hand")}</th>
            <th className="py-2 pr-3 text-right font-medium">{translate("Short")}</th>
            <th className="py-2 text-right font-medium">{translate("Cost")}</th>
          </tr>
        </thead>
        <tbody>
          {indent.ingredients.map((r) => (
            <tr key={r.ingredient} className="border-b border-zinc-100">
              <td className="py-1.5 pr-3">
                {r.ingredient_name}
                <p className="text-xs text-zinc-400">
                  {r.for_dishes.join(", ")}
                </p>
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums font-medium">
                {r.required} {r.uom}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums text-zinc-500">
                {r.on_hand}
              </td>
              <td
                className={
                  "py-1.5 pr-3 text-right tabular-nums " +
                  (r.short_by > 0 ? "font-medium text-rose-700" : "text-zinc-300")
                }
              >
                {r.short_by > 0 ? r.short_by : "-"}
              </td>
              <td className="py-1.5 text-right tabular-nums">{inr(r.cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {indent.by_kitchen.map((k) => (
          <div key={k.kitchen} className="rounded-lg border border-zinc-200 p-3">
            <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              {k.kitchen}
            </h4>
            <ul className="space-y-0.5 text-sm">
              {k.dishes.map((d, i) => (
                <li key={i} className="flex justify-between gap-2">
                  <span>
                    {d.dish}
                    {d.note && (
                      <span className="text-xs text-amber-700"> · {d.note}</span>
                    )}
                  </span>
                  <span className="shrink-0 tabular-nums text-zinc-400">
                    {d.portions}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Sheet>
  )
}

function CountSheet({
  data,
  pax,
  busy,
  onClose,
  onSave,
}: {
  data: FunctionEconomics
  pax: number
  busy: boolean
  onClose: () => void
  onSave: (rows: Record<string, number>, paxActual: number) => void
}) {
  useUILanguage()
  const [rows, setRows] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      data.lines.map((l) => [
        l.row,
        String(l.actual_qty ?? l.quoted_qty ?? ""),
      ]),
    ),
  )
  const [actual, setActual] = useState(String(data.pax || pax))

  return (
    <Sheet
      title={translate("Count the night")}
      description={translate("What was actually served. Until this is recorded the bill is a forecast.")}
      onClose={onClose}
      wide
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>{translate("Cancel")}</Button>
          <Button
            disabled={busy}
            onClick={() =>
              onSave(
                Object.fromEntries(
                  Object.entries(rows)
                    .filter(([, v]) => v !== "")
                    .map(([k, v]) => [k, Number(v)]),
                ),
                Number(actual) || 0,
              )
            }
          >{translate("Record it")}</Button>
        </div>
      }
    >
      <Field
        label={translate("Covers actually served")}
        hint={translate("Menus bill on the higher of this and the guarantee")}
        className="mb-4 max-w-48"
      >
        <input
          type="number"
          className={inputCls}
          value={actual}
          onChange={(e) => setActual(e.target.value)}
        />
      </Field>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-400">
            <th className="py-2 pr-3 font-medium">{translate("Item")}</th>
            <th className="py-2 pr-3 text-right font-medium">{translate("Quoted")}</th>
            <th className="py-2 text-right font-medium">{translate("Served")}</th>
          </tr>
        </thead>
        <tbody>
          {data.lines.map((l) => (
            <tr key={l.row} className="border-b border-zinc-100">
              <td className="py-1.5 pr-3">{l.item_name}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums text-zinc-400">
                {l.quoted_qty} {l.uom}
              </td>
              <td className="py-1.5 text-right">
                <input
                  type="number"
                  className={inputCls + " !w-24 !py-1 text-right"}
                  value={rows[l.row] ?? ""}
                  onChange={(e) =>
                    setRows((p) => ({ ...p, [l.row]: e.target.value }))
                  }
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Sheet>
  )
}

function SupplementarySheet({
  busy,
  onClose,
  onAdd,
}: {
  busy: boolean
  onClose: () => void
  onAdd: (params: Record<string, unknown>) => void
}) {
  useUILanguage()
  const [form, setForm] = useState({
    item_name: "",
    item_type: "Food & Beverage",
    qty: "1",
    uom: "Unit",
    rate: "",
    cost_rate: "",
    is_alcohol: false,
  })
  const set = (k: keyof typeof form, v: string | boolean) =>
    setForm((f) => ({ ...f, [k]: v }))

  return (
    <Sheet
      title={translate("Ordered on the night")}
      description={translate("Another round at the bar, twenty extra plates, a second cake - it bills on top of the agreed quote.")}
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>{translate("Cancel")}</Button>
          <Button
            disabled={busy || !form.item_name.trim() || !Number(form.rate)}
            onClick={() =>
              onAdd({
                item_name: form.item_name,
                item_type: form.item_type,
                qty: Number(form.qty) || 1,
                uom: form.uom,
                rate: Number(form.rate),
                cost_rate: Number(form.cost_rate) || 0,
                is_alcohol: form.is_alcohol ? 1 : 0,
              })
            }
          >{translate("Add it")}</Button>
        </div>
      }
    >
      <div className="space-y-3">
        <Field label={translate("What was it")}>
          <input
            className={inputCls}
            placeholder={translate("Extra bar round")}
            value={form.item_name}
            onChange={(e) => set("item_name", e.target.value)}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={translate("Kind")}>
            <Select
              value={form.item_type}
              onChange={(v) => set("item_type", v)}
              options={[
                "Food & Beverage",
                "Alcohol",
                "Audio Visual",
                "Decor",
                "Staffing",
                "Other",
              ]}
            />
          </Field>
          <Field label={translate("Per")}>
            <Select
              value={form.uom}
              onChange={(v) => set("uom", v)}
              options={["Unit", "Pax", "Hour", "Day", "Lot"]}
            />
          </Field>
          <Field label={translate("Quantity")}>
            <input
              type="number"
              className={inputCls}
              value={form.qty}
              onChange={(e) => set("qty", e.target.value)}
            />
          </Field>
          <Field label={translate("Rate")}>
            <input
              type="number"
              className={inputCls}
              value={form.rate}
              onChange={(e) => set("rate", e.target.value)}
            />
          </Field>
          <Field label={translate("What it cost us")} hint={translate("Keeps the margin honest")}>
            <input
              type="number"
              className={inputCls}
              value={form.cost_rate}
              onChange={(e) => set("cost_rate", e.target.value)}
            />
          </Field>
        </div>
        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            className="mt-0.5 size-4 accent-brand-600"
            checked={form.is_alcohol}
            onChange={(e) => set("is_alcohol", e.target.checked)}
          />
          <span>
            <span className="block text-sm font-medium text-zinc-700">{translate("Alcohol")}</span>
            <span className="block text-xs text-zinc-400">{translate("Never rides a company bill - it settles separately.")}</span>
          </span>
        </label>
      </div>
    </Sheet>
  )
}
