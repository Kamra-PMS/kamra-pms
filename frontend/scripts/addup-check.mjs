#!/usr/bin/env node
/** Pure checks for the figures printed on a POS bill (lib/addUp.ts): the printed
 *  lines add up to the printed subtotal, and a Rounding amount covers what is left. */
import assert from "node:assert/strict"
import fs from "node:fs"
import ts from "typescript"

const filename = new URL("../src/lib/addUp.ts", import.meta.url)
const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const mod = {}
new Function("exports", code)(mod)
const { addUp, toUnits } = mod

const units = (n, d) => Math.round(n * 10 ** d)
const sum = (xs) => xs.reduce((a, b) => a + b, 0)
/** the whole bill in units: lines, subtotal, discount, levy, tax, rounding, total */
const asUnits = (f) => ({
  lines: f.lines.map((n) => units(n, f.digits)), subtotal: units(f.subtotal, f.digits),
  discount: units(f.discount, f.digits), levy: units(f.levy, f.digits),
  taxes: f.taxes.map((n) => units(n, f.digits)), total: units(f.total, f.digits),
  rounding: units(f.rounding, f.digits),
})
/** every figure printed adds up: lines -> subtotal, and subtotal - discount + levy + tax + rounding -> total */
function assertAddsUp(f, label = "") {
  const u = asUnits(f)
  assert.equal(sum(u.lines), u.subtotal, `${label}: the lines add up to the subtotal`)
  assert.equal(u.subtotal - u.discount + u.levy + sum(u.taxes) + u.rounding, u.total, `${label}: the pieces add up to the total`)
}

// toUnits rounds the way Intl prints: half away from zero, on the decimal as written
assert.equal(toUnits(1.005, 2), 101)
assert.equal(toUnits(2.675, 2), 268)
assert.equal(toUnits(-2.675, 2), -268)
assert.equal(toUnits(0.5, 0), 1)
assert.equal(toUnits(-0.5, 0), -1)
assert.equal(toUnits(31818.181818, 0), 31818)
assert.equal(toUnits(-0.0001, 2), 0)
assert.ok(Object.is(toUnits(-0.0001, 2), 0), "never -0")
assert.equal(toUnits(1.2345, 3), 1235)

// 1. a menu stored without its tax at 6 decimals (a 35.000 dish is 31818.181818), 10% tax, 4 items:
//    the whole-number lines miss the subtotal by a unit, so the bill prints "Rounding -1"
const real = addUp({
  digits: 0,
  lines: [31818.181818, 58181.818182, 36363.636364, 7272.727273],
  taxes: [13363.64], // 10% of 133636.36, as the server rounds it
  total: 147000,
})
assert.deepEqual(real.lines, [31818, 58182, 36364, 7273])
assert.equal(real.subtotal, 133637)
assert.deepEqual(real.taxes, [13364])
assert.equal(real.total, 147000)
assert.equal(real.rounding, -1)
assertAddsUp(real, "the four-item bill")

// 2. whole-number prices: nothing to round, no Rounding line
const whole = addUp({ digits: 0, lines: [35000, 24000], levy: 5900, taxes: [3245], total: 68145 })
assert.equal(whole.rounding, 0)
assert.equal(whole.subtotal, 59000)
assertAddsUp(whole, "whole prices")

// 3. a two-decimal currency: 4.50 x 3 + 12.50, 10% tax
const usd = addUp({ digits: 2, lines: [13.5, 12.5], taxes: [2.6], total: 28.6 })
assert.deepEqual(usd.lines, [13.5, 12.5])
assert.equal(usd.subtotal, 26)
assert.equal(usd.rounding, 0)
assertAddsUp(usd, "USD")

// 4. six-decimal prices printed with two: the lines still add to the subtotal by construction
const six = addUp({ digits: 2, lines: [31818.181818, 58181.818182, 36363.636364, 7272.727273], taxes: [13363.64], total: 147000 })
assert.deepEqual(six.lines, [31818.18, 58181.82, 36363.64, 7272.73])
assert.equal(six.subtotal, 133636.37)
assertAddsUp(six, "six decimals at two digits")

// 5. three decimals (KWD) and none (JPY)
const kwd = addUp({ digits: 3, lines: [1.2345, 2.0004], taxes: [0.162], total: 3.397 })
assert.deepEqual(kwd.lines, [1.235, 2])
assertAddsUp(kwd, "KWD")
const jpy = addUp({ digits: 0, lines: [1280, 650.4, 650.4], taxes: [258], total: 2839 })
assert.equal(jpy.subtotal, 2580)
assertAddsUp(jpy, "JPY")

// 6. a discount comes off the subtotal; a levy goes on after it
const discounted = addUp({ digits: 0, lines: [35000, 24000], discount: 9000, levy: 5000, taxes: [2750], total: 57750 })
assert.equal(discounted.subtotal, 59000)
assert.equal(discounted.discount, 9000)
assert.equal(discounted.rounding, 0)
assertAddsUp(discounted, "discount and levy")
// a negative amount rounds like a positive one
assert.deepEqual(addUp({ digits: 0, lines: [-2.5, 2.5], total: 0 }).lines, [-3, 3])

// no figures at all
assertAddsUp(addUp({ digits: 2, lines: [], total: 0 }), "empty bill")

// 7. generated bills from a six-decimal menu: every figure adds up, the total is exactly what was
//    charged, and a unit is what the formatter prints
let seed = 20261124
const rand = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296)
const menu = [35000, 12000, 22000, 18000, 45000, 9000, 27500, 61000, 15500, 8000].map((p) => p / 1.1)
let withRounding = 0
for (const digits of [0, 2, 3]) {
  for (let i = 0; i < 400; i++) {
    const n = 1 + Math.floor(rand() * 6)
    const lines = Array.from({ length: n }, () => menu[Math.floor(rand() * menu.length)] * (1 + Math.floor(rand() * 4)))
    const exact = sum(lines)
    const discount = rand() < 0.3 ? Math.round(exact * 0.1) : 0
    const levy = rand() < 0.5 ? Math.round((exact - discount) * 10) / 100 : 0
    const tax = Math.round(((exact - discount) + levy) * 10) / 100
    const total = Math.round(((exact - discount) + levy + tax) * 10 ** digits) / 10 ** digits
    const f = addUp({ digits, lines, discount, levy, taxes: [tax], total })
    assertAddsUp(f, `bill ${digits}/${i}`)
    assert.equal(units(f.total, digits), toUnits(total, digits), "the total is what was charged")
    assert.ok(Math.abs(units(f.rounding, digits)) <= (n + 3) / 2, `bill ${digits}/${i}: rounding stays within what rounding can cause`)
    if (f.rounding !== 0) withRounding++
    // each printed figure is the unit Intl prints
    const printed = (x) => Number(x.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }).replace(/[^\d-]/g, ""))
    f.lines.forEach((x, k) => assert.equal(units(x, digits), printed(lines[k]), "a line equals what the formatter prints"))
  }
}
assert.ok(withRounding > 0, "the generated bills exercise the Rounding line")

console.log("addup-check: ok")
