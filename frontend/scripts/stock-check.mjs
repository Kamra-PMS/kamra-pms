#!/usr/bin/env node
/** Checks for the kitchen stock screens' pure helpers: unit costs (lib/stockCost.ts), what a Receive row
 *  adds up to and sends, which fields a form saves (lib/formPayload.ts), and what a recipe costs
 *  (lib/recipeCost.ts), an entry's date (lib/stockDates.ts) and the till's out-of-stock notice
 *  (lib/stockNotice.ts). Pure Node: bundled with small
 *  stand-ins for React, the API client and the language module. */
import assert from "node:assert/strict"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { build } from "esbuild"

const lib = fileURLToPath(new URL("../src/lib/", import.meta.url))
const stubs = {
  react: `export const useEffect = () => {}; export const useState = (v) => [v, () => {}]`,
  api: `export const call = async () => ({}); export const getCurrentProperty = () => ""`,
  dir: `export const adoptGuestLanguage = () => {}; export const applyEnabledLanguages = () => {}`,
}
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "stock-check-"))
// one bundle, so the helpers share the same money.ts (it holds the property's locale)
await build({
  stdin: {
    contents: `export * from "./money"; export * from "./stockCost"; export * from "./formPayload"; export * from "./recipeCost"; export * from "./stockDates"; export * from "./stockNotice"`,
    resolveDir: lib, loader: "ts",
  },
  bundle: true, format: "esm", platform: "node", outfile: path.join(dir, "stock.mjs"), logLevel: "silent",
  plugins: [{
    name: "stand-ins",
    setup(b) {
      b.onResolve({ filter: /^(react|\.\/api|\.\/dir)$/ }, (a) => ({ path: a.path.replace("./", ""), namespace: "stub" }))
      b.onLoad({ filter: /.*/, namespace: "stub" }, (a) => ({ contents: stubs[a.path], loader: "js" }))
    },
  }],
})
// money.ts remembers the locale in localStorage when there is one; there is none here
Object.defineProperty(globalThis, "localStorage", { value: undefined, configurable: true })
const { adoptUiLocale, fmtUnitCost, formPayload, defaultEntry, receiveLine, receiveRow, recipeTotals, fmtCost, postedAt, enteredLater, stockNotice } = await import(pathToFileURL(path.join(dir, "stock.mjs")).href)

// a cost per unit keeps up to 4 decimals, whatever the currency
adoptUiLocale({ currency: "INR", locale: "en-IN", currency_symbol: "₹" })
assert.equal(fmtUnitCost(18.571429), "18.5714")
assert.equal(fmtUnitCost(2500), "2,500.00")
assert.equal(fmtUnitCost(99999.999999), "1,00,000.00")
adoptUiLocale({ currency: "JPY", locale: "en-US", currency_symbol: "¥" })
assert.equal(fmtUnitCost(2500), "2,500")
assert.equal(fmtUnitCost(18.571429), "18.5714")

// a form saves only its own fields; an untouched cost is left for deliveries to set
const fields = [{ field: "ingredient_name", type: "data" },
  { field: "cost_per_unit", type: "currency", onlyIfChanged: true },
  { field: "secret", type: "password" }, { field: "fixed", type: "readonly" }]
const loaded = { ingredient_name: "Milk", cost_per_unit: 20, fixed: 1 }
assert.deepEqual(formPayload(fields, { ...loaded, secret: "" }, loaded), { ingredient_name: "Milk" })
assert.deepEqual(formPayload(fields, { ...loaded, cost_per_unit: "20" }, loaded), { ingredient_name: "Milk" })
assert.deepEqual(formPayload(fields, { ...loaded, cost_per_unit: 25 }, loaded),
  { ingredient_name: "Milk", cost_per_unit: 25 })
assert.deepEqual(formPayload(fields, { ...loaded, cost_per_unit: null }, loaded),
  { ingredient_name: "Milk", cost_per_unit: null }, "clearing the cost is a change")
assert.deepEqual(formPayload(fields, { ingredient_name: "Oat", cost_per_unit: 30 }, null),
  { ingredient_name: "Oat", cost_per_unit: 30 })

// a Receive row: what goes into stock, what it costs, and what is sent
const cups = { ingredient: "ING-1", uom: "pc", buy_uom: "box", buy_size: 24, cost_per_unit: 2000 }
assert.deepEqual(defaultEntry(cups), { qty: "", unit: "buy", size: "24", price: "" })
assert.equal(defaultEntry({ ingredient: "ING-2", uom: "L" }).unit, "stock")
const box = { qty: "2", unit: "buy", size: "24", price: "60000" }
assert.deepEqual(receiveLine(cups, box), { stockQty: 48, perUnit: 2500, total: 120000 })
// the total is what makes "60.000" (sixty) visible before saving
assert.deepEqual(receiveLine(cups, { ...box, price: "60.000" }), { stockQty: 48, perUnit: 2.5, total: 120 })
assert.deepEqual(receiveLine(cups, { ...box, price: "" }), { stockQty: 48, perUnit: null, total: null })
assert.deepEqual(receiveLine(cups, { ...box, price: "0" }), { stockQty: 48, perUnit: 0, total: 0 })
assert.deepEqual(receiveLine(cups, { qty: "10", unit: "stock", size: "24", price: "2500" }),
  { stockQty: 10, perUnit: 2500, total: 25000 })
assert.equal(receiveLine(cups, { ...box, qty: "" }), null)
assert.equal(receiveLine(cups, { ...box, size: "0" }), null)
assert.deepEqual(receiveRow(cups, box), { ingredient: "ING-1", uom: "pc", qty: 2, in_buying_unit: 1,
  buy_uom: "box", buy_size: 24, cost_per_unit: 60000 })
assert.equal(receiveRow(cups, { ...box, price: "0" }).cost_per_unit, 0)
assert.ok(!("cost_per_unit" in receiveRow(cups, { ...box, price: "" })))
assert.deepEqual(receiveRow(cups, { qty: "10", unit: "stock", size: "", price: "2500" }),
  { ingredient: "ING-1", uom: "pc", qty: 10, cost_per_unit: 2500 })

// a recipe's cost per portion and margin: the same rule as kamra/inventory.py
const ings = [
  { name: "M", ingredient_name: "Milk", cost_per_unit: 20 },
  { name: "B", ingredient_name: "Beans", cost_per_unit: 220 },
  { name: "C", ingredient_name: "Cup", cost_per_unit: 2400 },
  { name: "W", ingredient_name: "Water", cost_per_unit: 0 },
  { name: "S", ingredient_name: "Syrup", cost_per_unit: 6000 },
]
const costed = recipeTotals(
  [{ ingredient: "M", qty: "150" }, { ingredient: "B", qty: 18 }, { ingredient: "C", qty: 1 }], ings, 25000)
assert.deepEqual([costed.lines, costed.cost, costed.margin, costed.pct.toFixed(1), costed.missing],
  [[3000, 3960, 2400], 9360, 15640, "62.6", []])
assert.deepEqual(recipeTotals([{ ingredient: "M", qty: 150 }, { ingredient: "W", qty: 5 }, { ingredient: "W", qty: 5 }], ings, 25000),
  { lines: [3000, null, null], cost: null, margin: null, pct: null, missing: ["Water"] })
const dear = recipeTotals([{ ingredient: "S", qty: 2 }], ings, 10000)
assert.deepEqual([dear.cost, dear.margin, dear.pct.toFixed(1)], [12000, -2000, "-20.0"])
const free = recipeTotals([{ ingredient: "M", qty: 150 }], ings, 0)
assert.deepEqual([free.cost, free.margin, free.pct], [3000, -3000, null])
assert.equal(recipeTotals([{ ingredient: "M", qty: 100 }, { ingredient: "M", qty: 50 }], ings, 5000).cost, 3000)
// lines still being typed don't count, and don't blank the total
const typing = recipeTotals([{ ingredient: "", qty: "" }, { ingredient: "M", qty: "" }, { ingredient: "M", qty: 100 }], ings, 5000)
assert.deepEqual([typing.lines, typing.cost], [[null, null, 2000], 2000])
assert.deepEqual(recipeTotals([{ ingredient: "", qty: "" }], ings, 5000),
  { lines: [null], cost: null, margin: null, pct: null, missing: [] })
// money to the currency's decimals, and 2 where the figure needs them
adoptUiLocale({ currency: "INR", locale: "en-IN", currency_symbol: "₹" })
assert.equal(fmtCost(334.285722), "334.29")
assert.equal(fmtCost(9360), "9,360.00")
adoptUiLocale({ currency: "JPY", locale: "en-US", currency_symbol: "¥" })
assert.equal(fmtCost(9360), "9,360")
assert.equal(fmtCost(334.285722), "334.29")

// an entry's date: blank means now; one typed well after it happened says so
assert.equal(postedAt(""), undefined)
assert.equal(postedAt("  "), undefined)
assert.equal(postedAt("2026-11-02T18:00"), "2026-11-02 18:00:00")
assert.equal(postedAt("2026-11-02T18:00:30"), "2026-11-02 18:00:30")
assert.equal(enteredLater({ posted_at: "2026-11-02 18:00:00.000000", creation: "2026-11-02 18:00:00.500000" }), false)
assert.equal(enteredLater({ posted_at: "2026-11-02 18:00:00", creation: "2026-11-05 09:12:00.123456" }), true)
assert.equal(enteredLater({ posted_at: null, creation: "2026-11-05 09:12:00" }), false)

// the till warns about an item with its own stock and nothing left; it never stops the sale
assert.equal(stockNotice({ item_name: "Tea" }), null, "an item without own stock")
assert.equal(stockNotice({ item_name: "Water", stock_left: 3 }), null)
assert.equal(stockNotice({ item_name: "Water", stock_left: 0.0005 }), null)
assert.deepEqual(stockNotice({ item_name: "Water", stock_left: 0 }), { name: "Water", qty: "0" })
assert.deepEqual(stockNotice({ item_name: "Water", stock_left: -2.5 }), { name: "Water", qty: "-2.5" })

fs.rmSync(dir, { recursive: true, force: true })
console.log("stock checks passed")
