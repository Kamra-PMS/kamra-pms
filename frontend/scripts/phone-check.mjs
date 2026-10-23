#!/usr/bin/env node
import assert from "node:assert/strict"
import fs from "node:fs"
import { createRequire } from "node:module"
import ts from "typescript"

const require = createRequire(import.meta.url)
const filename = new URL("../src/lib/phone.ts", import.meta.url)
const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText
const phone = {}
new Function("require", "exports", code)(require, phone)
assert.equal(phone.dialForCountry("Nicaragua"), "505")
assert.equal(phone.dialForCountry(" ni "), "505")
assert.equal(phone.dialForCountry("India"), "91")
assert.equal(phone.dialForCountry("مصر"), "20")
assert.equal(phone.dialForCountry("Unknown country"), "")
assert.deepEqual(phone.phoneLengthForDial("505"), { min: 8, max: 8 })
assert.deepEqual(phone.splitPhone("", "Nicaragua"), { dial: "505", local: "" })
assert.equal(phone.joinPhone("505", "8888 1234"), "+50588881234")
for (const [dial, local] of [["1", "4155552671"], ["34", "911234567"], ["504", "99881234"], ["502", "55123456"], ["506", "88881234"]]) {
  assert.ok(phone.PHONE_DIAL_CODES.includes(dial), `Missing calling code ${dial}`)
  const stored = phone.joinPhone(dial, local)
  assert.deepEqual(phone.splitPhone(stored, "Nicaragua"), { dial, local })
  assert.ok(phone.isPhoneComplete(stored, "Nicaragua"), `Foreign number rejected: ${stored}`)
}
assert.deepEqual(phone.splitPhone("0034911234567", "Nicaragua"), { dial: "34", local: "911234567" })
assert.equal(phone.formatPhoneTel("50588881234", "Nicaragua"), "+50588881234")
assert.equal(phone.joinPhone("39", "0212345678"), "+390212345678")
assert.equal(phone.splitPhone("+390212345678", "Nicaragua").local, "0212345678")
assert.ok(phone.isPhoneComplete("88881234", "Nicaragua"))
assert.ok(phone.isPhoneComplete("", "Nicaragua"))
for (const incomplete of ["+5058888123", "+505888812345", "+99912345678", "+505"]) {
  assert.equal(phone.isPhoneComplete(incomplete, "Nicaragua"), false, `Invalid number accepted: ${incomplete}`)
}
assert.equal(phone.splitPhone("+99912345678", "Nicaragua").dial, "")
console.log("Phone checks passed: hotel defaults, international prefixes, paste, lengths and significant zeros")
