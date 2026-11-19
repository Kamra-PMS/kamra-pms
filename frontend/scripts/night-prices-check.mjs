#!/usr/bin/env node
/** Pure regression checks for the nightly prices typed on New booking (#634). */
import assert from "node:assert/strict"
import fs from "node:fs"
import ts from "typescript"

const filename = new URL("../src/lib/nightPrices.ts", import.meta.url)
const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  },
}).outputText
const mod = {}
new Function("exports", code)(mod)
const { splitRoomTotal, parsePrice, typedNights, isOverride, maxPriceDigits } = mod

const sum = (xs, d) => Math.round(xs.reduce((a, b) => a + b, 0) * 10 ** d)

// a typed total of 230.00 over 2 nights adds up to exactly 230.00
assert.deepEqual(splitRoomTotal(230, 2, 2), [115, 115])
// an odd unit goes to the first nights, and the sum never drifts
assert.deepEqual(splitRoomTotal(100, 3, 2), [33.34, 33.33, 33.33])
assert.deepEqual(splitRoomTotal(0.1 + 0.2, 3, 2), [0.1, 0.1, 0.1])
for (const [total, n, d] of [[999.99, 7, 2], [1000, 3, 0], [1234567.89, 11, 2], [0.07, 4, 2], [19.99, 3, 2]]) {
  assert.equal(sum(splitRoomTotal(total, n, d), d), Math.round(total * 10 ** d), `${total} over ${n}`)
}
// a zero-decimal currency splits in whole units
assert.deepEqual(splitRoomTotal(1000, 3, 0), [334, 333, 333])
assert.deepEqual(splitRoomTotal(0, 2, 2), [])
assert.deepEqual(splitRoomTotal(100, 0, 2), [])

// a typed price: above zero, and no more decimals than the currency has
assert.equal(parsePrice("120", 2), 120)
assert.equal(parsePrice(" 120.50 ", 2), 120.5)
assert.equal(parsePrice("120.505", 2), null)
assert.equal(parsePrice("120.5", 0), null)
assert.equal(parsePrice("0", 2), null)
assert.equal(parsePrice("-5", 2), null)
assert.equal(parsePrice("1e3", 2), null)
assert.equal(parsePrice("", 2), null)
assert.equal(parsePrice("abc", 2), null)
assert.equal(maxPriceDigits(3), 2)
assert.equal(maxPriceDigits(0), 0)

// only typed nights inside the stay are sent: night 1 typed, night 2 at BAR
const dates = ["2030-02-01", "2030-02-02"]
assert.deepEqual(typedNights({ "2030-02-01": 120 }, dates), [{ date: "2030-02-01", price: 120 }])
assert.deepEqual(typedNights({}, dates), [])
// a night that left the stay on a date change is dropped
assert.deepEqual(typedNights({ "2030-02-01": 120, "2030-02-05": 99 }, dates), [{ date: "2030-02-01", price: 120 }])

assert.equal(isOverride(120, 100, 2), true)
assert.equal(isOverride(100, 100, 2), false)
assert.equal(isOverride(undefined, 100, 2), false)

console.log("night-prices-check: ok")
