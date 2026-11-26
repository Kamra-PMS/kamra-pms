#!/usr/bin/env node
/** Checks for the printed bill (lib/thermal.ts and lib/code128.ts): the Code 128 barcode, the HTML
 *  escaping on every ticket, the logo rule and the outlet's barcode switch. Pure Node: the real bill
 *  code is bundled with small stand-ins for the modules that need a browser or the network. */
import assert from "node:assert/strict"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { build } from "esbuild"

const lib = fileURLToPath(new URL("../src/lib/", import.meta.url))
const stubs = {
  i18n: `export const t = (s, v) => String(s).replace(/\\{(\\w+)\\}/g, (_, k) => (v && v[k] != null ? v[k] : ""))
         export const tn = (n, one, other, v) => t(n === 1 ? one : other, { n, ...v })
         export const uiDateLocale = () => "en"`,
  money: `export const cur = () => ""
          export const moneyLocale = () => "en"
          export const moneyDigits = () => 2
          export const fmtAmount = (n) => Number(n ?? 0).toFixed(2)`,
}
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "bill-check-"))
await build({
  entryPoints: { thermal: lib + "thermal.ts", code128: lib + "code128.ts" },
  bundle: true, format: "esm", platform: "node", outdir: dir, logLevel: "silent",
  plugins: [{
    name: "stand-ins",
    setup(b) {
      b.onResolve({ filter: /^\.\/(i18n|money)$/ }, (a) => ({ path: a.path.slice(2), namespace: "stub" }))
      b.onLoad({ filter: /.*/, namespace: "stub" }, (a) => ({ contents: stubs[a.path], loader: "js" }))
      b.onResolve({ filter: /\.woff2\?inline$/ }, (a) => ({ path: a.path, namespace: "font" }))
      b.onLoad({ filter: /.*/, namespace: "font" }, () => ({ contents: 'export default ""', loader: "js" }))
    },
  }],
})
const load = (name) => import(pathToFileURL(path.join(dir, name + ".js")).href)
const { billHtml, kotHtml, laundryDocketHtml, thermalDocument } = await load("thermal")
const { code128Widths, code128Svg } = await load("code128")

// ---- the barcode -------------------------------------------------------------------------
const sum = (xs) => xs.reduce((a, b) => a + b, 0)
assert.equal(code128Widths(""), null, "an empty text has no barcode")
for (const bad of ["é", "a\tb", "日本", "x\u0000"]) assert.equal(code128Widths(bad), null, `${JSON.stringify(bad)} is not Code 128B`)

for (const text of ["A", "ORD-2026-00042", " ~", "0123456789"]) {
  const w = code128Widths(text)
  assert.ok(Array.isArray(w), text)
  // start + one symbol per character + check symbol are 6 bars and spaces of 11 modules each, then the stop of 13
  const symbols = text.length + 2
  assert.equal(w.length, symbols * 6 + 7, `${text}: bar count`)
  assert.equal(sum(w), symbols * 11 + 13, `${text}: module count`)
  for (let i = 0; i < symbols; i++) assert.equal(sum(w.slice(i * 6, i * 6 + 6)), 11, `${text}: symbol ${i} is 11 modules`)
  assert.deepEqual(w.slice(0, 6), [2, 1, 1, 2, 1, 4], `${text}: starts with Start B`)
  assert.deepEqual(w.slice(-7), [2, 3, 3, 1, 1, 1, 2], `${text}: ends with the stop pattern`)
}
// known bar widths, checked once with a barcode reader against every printable character and bill numbers
assert.deepEqual(code128Widths("A"), [2, 1, 1, 2, 1, 4, 1, 1, 1, 3, 2, 3, 1, 3, 1, 1, 2, 3, 2, 3, 3, 1, 1, 1, 2])
assert.deepEqual(code128Widths("ORD-2026-00042"), [
  2, 1, 1, 2, 1, 4, 1, 3, 3, 1, 2, 1, 2, 3, 1, 1, 3, 1, 1, 1, 2, 3, 1, 3, 1, 2, 2, 1, 3, 2, 2, 2, 3, 2, 1, 1, 1, 2,
  3, 1, 2, 2, 2, 2, 3, 2, 1, 1, 2, 2, 3, 1, 1, 2, 1, 2, 2, 1, 3, 2, 1, 2, 3, 1, 2, 2, 1, 2, 3, 1, 2, 2, 1, 2, 3, 1,
  2, 2, 2, 2, 1, 2, 3, 1, 2, 2, 3, 2, 1, 1, 1, 1, 3, 1, 4, 1, 2, 3, 3, 1, 1, 1, 2,
])
assert.notDeepEqual(code128Widths("ORD-2026-00042"), code128Widths("ORD-2026-00043"), "different numbers, different bars")
const svg = code128Svg("ORD-2026-00042")
assert.ok(svg.startsWith("<svg") && svg.includes("mm"), "the barcode is an SVG sized in millimetres")
assert.ok(svg.includes('aria-label="ORD-2026-00042"'), "the SVG is labelled with the order number")
const hostile = code128Svg('a"><script>alert(1)</script>&')
assert.match(hostile, /^<svg [^<>]*><path d="[^"<>]*"\/><\/svg>$/, "a hostile text cannot add markup to the barcode SVG: it is one svg with one path")
assert.ok(hostile.includes('aria-label="ascriptalert(1)/script"'), "the label drops & < > and double quotes")
assert.equal(code128Svg("é"), "", "an unencodable text prints no barcode")

// ---- the bill -----------------------------------------------------------------------------
const EVIL = `<img src=x onerror=alert(1)>"'&`
const bill = (over = {}) => ({
  order: "ORD-2026-00042", kot_no: 17, property_name: "Hotel", outlet_name: "Warung", order_type: "Dine In",
  table_no: "T1", room_no: null, customer_name: null, customer_phone: null, delivery_address: null,
  captain: null, served_by: "Rina", cashier: null, logo: null, receipt_design: "Columns",
  items: [{ item_name: "Nasi Goreng", qty: 1, rate: 35000, amount: 35000 }],
  subtotal: 35000, discount_amount: 0, taxable: 35000, gst_rate: 10, cgst: 1750, sgst: 1750,
  tax_parts: [{ label: "TAX", rate: 10, amount: 3500 }], grand_total: 38500,
  paid: 0, payment_mode: null, nc: 0, nc_authorized_by: null, nc_note: null, ...over,
})

// every free-text field is escaped on the bill, in both layouts
for (const receipt_design of ["Columns", "Stacked"]) {
  const html = billHtml(bill({
    receipt_design, order: EVIL, property_name: EVIL, outlet_name: EVIL, table_no: EVIL, room_no: null,
    customer_name: EVIL, customer_phone: EVIL, delivery_address: EVIL, served_by: EVIL, cashier: EVIL,
    items: [{ item_name: EVIL, qty: 1, rate: 1, amount: 1, modifiers: [EVIL] }], tax_parts: [{ label: EVIL, rate: 10, amount: 1 }],
    paid: 1, payment_mode: EVIL, nc: 1, nc_authorized_by: EVIL, nc_note: EVIL,
  }))
  assert.ok(!/<img/i.test(html), `${receipt_design}: nothing the user typed becomes a tag`)
  assert.ok(html.includes("&lt;img src=x onerror=alert(1)&gt;"), `${receipt_design}: it prints as text instead`)
}
// the Saudi QR and ICV are escaped too
const saudi = billHtml(bill({ paid: 1, payment_mode: "Card",
  statutory: { title: "Simplified Tax Invoice", title_ar: "x", qr_image: 'data:image/png;base64,AAA" onerror="alert(1)', icv: "1<b>x" } }))
assert.ok(!saudi.includes('" onerror="alert(1)'), "the QR source cannot break out of its attribute")
assert.ok(saudi.includes("&quot; onerror=&quot;alert(1)"), "the QR source is escaped")
assert.ok(saudi.includes("ICV 1&lt;b&gt;x"), "the ICV is escaped")
// the kitchen ticket and the laundry docket
const kot = kotHtml({ outlet: EVIL, kot_no: 1, label: EVIL, order_type: EVIL, order: EVIL, customer: EVIL, address: EVIL,
  station: EVIL, fallback_from: EVIL, nc: true, nc_by: EVIL, items: [{ item_name: EVIL, qty: 1, instructions: EVIL, modifiers: [EVIL] }] })
assert.ok(!/<img/i.test(kot), "the kitchen ticket escapes everything")
// the choices ticked for a dish print under it, one per line, on the kitchen ticket and on the bill in both layouts
const kotMods = kotHtml({ outlet: "Warung", kot_no: 2, label: "Table 1", order: "ORD-1", items: [
  { item_name: "Es Kopi Susu", qty: 2, modifiers: ["Less ice", "Oat milk"], instructions: "no straw" },
  { item_name: "Nasi Goreng", qty: 1 }] })
assert.ok(kotMods.includes('<div class="mod">+ Less ice</div><div class="mod">+ Oat milk</div><div class="ins">'), "the kitchen ticket lists the choices, then the note")
assert.equal((kotMods.match(/class="mod"/g) ?? []).length, 2, "a dish without choices prints none")
for (const receipt_design of ["Columns", "Stacked"]) {
  const html = billHtml(bill({ receipt_design, items: [{ item_name: "Es Kopi Susu", qty: 1, rate: 32000, amount: 32000, modifiers: ["Less ice", "Oat milk"] }] }))
  assert.ok(html.includes('<div class="mod">+ Oat milk</div>'), `${receipt_design}: the bill lists the choices under the dish`)
  assert.ok(html.includes("32,000.00") || html.includes("32000.00"), `${receipt_design}: the rate is the one that includes them`)
}
const laundry = laundryDocketHtml({ property_name: EVIL, order: EVIL, room_no: EVIL, guest_name: EVIL, order_type: EVIL,
  express: true, ready_by: EVIL, items: [{ item_name: EVIL, service_type: EVIL, qty: 1 }], total: 100 })
assert.ok(!/<img/i.test(laundry), "the laundry docket escapes everything")

// ---- the logo: an uploaded file or an https link only ---------------------------------------
for (const ok of ["/files/logo.png", "/private/files/logo.png", "https://example.com/logo.png", "/files/my%20logo.png"]) {
  const html = billHtml(bill({ logo: ok }))
  assert.ok(html.includes(`<div class="logo"><img src="${ok}"`), `${ok} is printed as the logo`)
}
for (const bad of ["", "http://example.com/logo.png", "javascript:alert(1)", "data:image/svg+xml;base64,PHN2Zz4=",
  "//example.com/logo.png", "/files/../etc/passwd", '/files/x.png" onerror="y', "/files/a b.png", "ftp://example.com/x.png",
  "/files/%2e%2e/etc/passwd", "/files/%2E%2E/x.png", "/files/%zz.png"]) {
  const html = billHtml(bill({ logo: bad }))
  assert.ok(!html.includes('class="logo"') && !/<img/i.test(html), `${JSON.stringify(bad)} is not printed as a logo`)
  assert.ok(html.includes('class="c brand">Warung<'), "the outlet name prints instead")
}
// a large logo cannot print at full size even before it has loaded
const css = thermalDocument("t", "")
assert.ok(/\.logo img\s*{[^}]*max-height: 16mm/.test(css) && /\.logo img\s*{[^}]*max-width: 60mm/.test(css)
  && /\.logo img\s*{[^}]*object-fit: contain/.test(css), "the logo is capped at 16 x 60 mm")

// ---- the barcode switch ---------------------------------------------------------------------
for (const on of [undefined, null, 1, true]) assert.ok(billHtml(bill({ barcode: on })).includes('class="bc"'), `barcode ${on} prints it`)
for (const off of [0, false]) assert.ok(!billHtml(bill({ barcode: off })).includes('class="bc"'), `barcode ${off} leaves it off`)

fs.rmSync(dir, { recursive: true, force: true })
console.log("bill-check: ok")
