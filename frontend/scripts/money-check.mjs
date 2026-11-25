#!/usr/bin/env node
/** Checks for fmtAmount (lib/money.ts) and tripMoney (lib/tripMoney.ts): an amount in another currency
 *  than the property's own (a stay at another property on a trip) is printed with that currency's
 *  decimals, and a trip's figures take their currency from the right stay. Pure Node: both are bundled with small stand-ins for React, the API client and the language module. */
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
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "money-check-"))
await build({
  entryPoints: { money: lib + "money.ts", tripMoney: lib + "tripMoney.ts" }, bundle: true, format: "esm", platform: "node", outdir: dir, logLevel: "silent",
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
const { fmtAmount, fmtMoney, adoptUiLocale } = await import(pathToFileURL(path.join(dir, "money.js")).href)
const { tripMoney } = await import(pathToFileURL(path.join(dir, "tripMoney.js")).href)

// a property that keeps its books in rupees
adoptUiLocale({ currency: "INR", locale: "en-IN", currency_symbol: "₹" })
assert.equal(fmtAmount(5000), "5,000.00", "the property's own currency: 2 decimals")
assert.equal(fmtAmount(5000, undefined), "5,000.00")
assert.equal(fmtAmount(5000, null), "5,000.00", "no code means the property's currency")
assert.equal(fmtAmount(5000, ""), "5,000.00")
assert.equal(fmtAmount(5000, "INR"), "5,000.00")
// a stay at another property, billed in another currency: that currency's decimals
assert.equal(fmtAmount(5000, "IDR"), "5,000", "rupiah has none")
assert.equal(fmtAmount(1234567.5, "JPY"), "12,34,568", "yen has none (grouping is still the viewer's)")
assert.equal(fmtAmount(1234.5, "KWD"), "1,234.500", "dinar has three")
assert.equal(fmtAmount(1234.5, "USD"), "1,234.50")
assert.equal(fmtAmount(1234.5, "ZZZ"), "1,234.50", "an unknown code falls back to two")
assert.equal(fmtAmount(1234.5, "not a code"), "1,234.50", "so does one that is not a code at all")
assert.equal(fmtAmount(undefined, "IDR"), "0")
assert.equal(fmtMoney(5000), "₹5,000.00", "fmtMoney still uses the property's currency")

// a trip's header and confirmation: the symbol and code come from the stays the figures add up
const idr = (status) => ({ status, currency: "IDR", currency_symbol: "Rp" })
const usd = (status) => ({ status, currency: "USD", currency_symbol: "$" })
const header = (legs, n = 5000) => { const { live } = tripMoney(legs); return `${live.sym}${fmtAmount(n, live.code)}` }
assert.equal(header([idr("Confirmed"), idr("Confirmed")]), "Rp5,000", "an all-rupiah trip seen from a rupee desk: no cents")
assert.equal(header([usd("Cancelled"), idr("Confirmed")]), "Rp5,000", "a cancelled first stay in dollars does not label the live total")
assert.equal(header([usd("Cancelled"), idr("Checked In"), idr("Held")]), "Rp5,000", "Checked In and Held are live")
assert.equal(header([usd("No Show"), idr("Pending Payment")]), "Rp5,000", "a no-show is not live")
assert.equal(tripMoney([usd("Cancelled"), idr("Confirmed")]).held.code, "USD", "the advance held on cancelled stays takes the cancelled stay's currency")
assert.equal(tripMoney([usd("Cancelled"), idr("Confirmed")]).held.sym, "$")
assert.equal(tripMoney([idr("Confirmed")]).held.code, "IDR", "with none cancelled it falls back to the first stay")
assert.deepEqual(tripMoney([usd("Cancelled")]).live, { sym: "$", code: "USD" }, "with no live stay it falls back to the first stay")
assert.deepEqual(tripMoney([]).live, { sym: "", code: undefined }, "no stays, no symbol")
assert.deepEqual(tripMoney([{ status: "Confirmed" }]).live, { sym: "", code: undefined }, "a stay without a currency prints with the property's own")

// a property that keeps its books in rupiah, with a stay in dollars on the same trip
adoptUiLocale({ currency: "IDR", locale: "id-ID", currency_symbol: "Rp" })
assert.equal(fmtAmount(35000), "35.000")
assert.equal(fmtAmount(35000, "IDR"), "35.000")
assert.equal(fmtAmount(5.5, "USD"), "5,50", "dollars keep their cents next to a rupiah property")

fs.rmSync(dir, { recursive: true, force: true })
console.log("money-check: ok")
