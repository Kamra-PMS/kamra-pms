#!/usr/bin/env node
/** Pure regression checks for the booking dialog's default room type (#549). */
import assert from "node:assert/strict"
import fs from "node:fs"
import ts from "typescript"

const filename = new URL("../src/lib/bookingDefaults.ts", import.meta.url)
const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  },
}).outputText
const mod = {}
new Function("exports", code)(mod)
const { pickDefaultRoomType } = mod

const cheapEmpty = { name: "cheap" }
const midAvail = { name: "mid" }
const dearAvail = { name: "dear" }
const types = [cheapEmpty, midAvail, dearAvail]

assert.equal(pickDefaultRoomType([], {}), "", "empty catalog")
assert.equal(
  pickDefaultRoomType(types, { cheap: 0, mid: 2, dear: 1 }),
  "mid",
  "skip empty cheapest; take first with rooms",
)
assert.equal(
  pickDefaultRoomType(types, { cheap: 0, mid: 0, dear: 0 }),
  "cheap",
  "fall back to cheapest when none have rooms",
)
assert.equal(
  pickDefaultRoomType(types, { cheap: 3, mid: 1, dear: 1 }),
  "cheap",
  "keep cheapest when it has rooms",
)
assert.equal(
  pickDefaultRoomType([{ name: "only" }], {}),
  "only",
  "missing count treated as zero → fall back to first",
)

console.log("booking-defaults-check: ok")
