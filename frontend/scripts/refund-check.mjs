#!/usr/bin/env node
/** Checks for the refund screens' pure helpers (lib/refunds.ts): what a refund window asks for, the
 *  bill's badge, and the printed slip. Pure Node. */
import assert from "node:assert/strict"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { build } from "esbuild"

const lib = fileURLToPath(new URL("../src/lib/", import.meta.url))
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "refund-check-"))
await build({
  stdin: { contents: `export * from "./refunds"`, resolveDir: lib, loader: "ts" },
  bundle: true, format: "esm", platform: "node", outfile: path.join(dir, "refunds.mjs"), logLevel: "silent",
})
const { refundBadge, refundRequest, refundSlipHtml, newAttemptKey } =
  await import(pathToFileURL(path.join(dir, "refunds.mjs")).href)

assert.equal(refundBadge(72600, 0), null)
assert.equal(refundBadge(72600, 30250), "partly")
assert.equal(refundBadge(72600, 72600), "full")
assert.equal(refundBadge(100, 99.999), "full", "a rounding hair is not a part refund")
assert.equal(refundBadge(0, 50), "partly", "no record of what was paid: never claim it is all back")

// the whole bill: only the back-to-stock ticks go with it
assert.deepEqual(refundRequest("whole", {}, { a: true, b: false }, ""),
  { kind: "whole", lines: [{ row: "a", qty: 0, back_to_stock: 1 }] })
assert.deepEqual(refundRequest("whole", {}, {}, ""), { kind: "whole", lines: [] })
// items: the quantities above zero, with their ticks
assert.deepEqual(refundRequest("items", { a: "1", b: "", c: "0", d: "2" }, { d: true, b: true }, ""),
  { kind: "items", lines: [{ row: "a", qty: 1, back_to_stock: 0 }, { row: "d", qty: 2, back_to_stock: 1 }] })
assert.equal(refundRequest("items", { a: "0" }, {}, ""), null)
// an amount
assert.deepEqual(refundRequest("amount", { a: "1" }, { a: true }, "10000"), { kind: "amount", amount: 10000 })
assert.equal(refundRequest("amount", {}, {}, ""), null)
assert.equal(refundRequest("amount", {}, {}, "-5"), null)

assert.notEqual(newAttemptKey(), newAttemptKey())
assert.ok(newAttemptKey().length >= 16)

// the slip says what, how, why and who - and escapes what staff typed
const slip = refundSlipHtml({
  title: "Refund", outlet: "Cafe <b>", bill: "ORD-1", when: "26 Nov 16:00", total: "30.250",
  lines: [{ name: "Latte & milk", qty: 1, amount: "30.250" }],
  rows: [["Given back as", "Cash"], ["Reason", "Wrong order <script>"], ["Approved by", "Budi"]],
  sign: "Received by",
})
for (const text of ["Refund", "ORD-1", "30.250", "Latte &amp; milk", "Cafe &lt;b&gt;", "Wrong order &lt;script&gt;", "Received by"])
  assert.ok(slip.includes(text), text)
assert.ok(!slip.includes("<script>"))

fs.rmSync(dir, { recursive: true, force: true })
console.log("refund checks passed")
