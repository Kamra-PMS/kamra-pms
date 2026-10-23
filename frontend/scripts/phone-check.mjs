#!/usr/bin/env node
/** Regression checks only. Country availability comes from libphonenumber-js
 * metadata in src/lib/phone.ts, not from the examples in this script. */
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

// Derive coverage from the whole catalog, so dependency updates include new
// countries automatically instead of requiring a hand-maintained test list.
const { getCountries, getCountryCallingCode, getExampleNumber } = require("libphonenumber-js/core")
const metadata = require("libphonenumber-js/metadata.min.json")
const examples = require("libphonenumber-js/mobile/examples")
const countries = getCountries(metadata)
const displayNames = ["en", "es", "ar"].map((language) => new Intl.DisplayNames([language], { type: "region" }))
const expectedDialCodes = [...new Set([
  ...countries.map((country) => getCountryCallingCode(country, metadata)),
  ...Object.keys(metadata.nonGeographic),
])].sort((a, b) => Number(a) - Number(b))
assert.deepEqual(phone.PHONE_DIAL_CODES, expectedDialCodes, "The selector must include every catalog calling code")

for (const country of countries) {
  const dial = getCountryCallingCode(country, metadata)
  assert.equal(phone.dialForCountry(country), dial, `${country}: hotel country code`)
  assert.equal(phone.dialForCountry(` ${country.toLowerCase()} `), dial, `${country}: normalized country code`)
  for (const names of displayNames) {
    const name = names.of(country)
    assert.equal(phone.dialForCountry(name), dial, `${country}: country name ${name}`)
  }
  assert.deepEqual(phone.splitPhone("", country), { dial, local: "" }, `${country}: hotel default`)
  assert.ok(phone.isPhoneComplete("", country), `${country}: phone remains optional`)

  const example = getExampleNumber(country, examples, metadata)
  assert.ok(example, `${country}: missing phone fixture in the catalog`)
  const local = example.nationalNumber
  const stored = example.number
  const length = phone.phoneLengthForDial(dial)
  assert.ok(local.length >= length.min && local.length <= length.max, `${country}: national length`)
  assert.equal(phone.joinPhone(dial, local), stored, `${country}: storage format`)
  assert.deepEqual(phone.splitPhone(stored, country), { dial, local }, `${country}: stored number`)
  assert.ok(phone.isPhoneComplete(stored, country), `${country}: example accepted`)
  assert.equal(phone.formatPhoneTel(stored, country), stored, `${country}: calling link`)

  const foreignHotel = countries.find((hotel) => getCountryCallingCode(hotel, metadata) !== dial)
  assert.ok(foreignHotel, `${country}: foreign hotel fixture`)
  assert.deepEqual(phone.splitPhone(stored, foreignHotel), { dial, local }, `${country}: guest keeps their own code abroad`)
  assert.deepEqual(phone.splitPhone(`00${stored.slice(1)}`, foreignHotel), { dial, local }, `${country}: international paste`)
  assert.ok(phone.isPhoneComplete(stored, foreignHotel), `${country}: guest accepted abroad`)
  assert.equal(phone.formatPhoneTel(stored, foreignHotel), stored, `${country}: foreign calling link`)
}

// Specific regressions: the original Nicaragua bug, existing India handling,
// an Arabic country-name alias, and significant Italian leading zeros.
assert.equal(phone.dialForCountry("Nicaragua"), "505")
assert.equal(phone.dialForCountry(" ni "), "505")
assert.equal(phone.dialForCountry("India"), "91")
assert.equal(phone.dialForCountry("مصر"), "20")
assert.equal(phone.dialForCountry("Unknown country"), "")
assert.deepEqual(phone.phoneLengthForDial("505"), { min: 8, max: 8 })
assert.deepEqual(phone.splitPhone("", "Nicaragua"), { dial: "505", local: "" })
assert.equal(phone.joinPhone("505", "8888 1234"), "+50588881234")
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
console.log(`Phone checks passed: ${countries.length} countries/territories, ${expectedDialCodes.length} calling codes, hotel defaults, foreign guests, paste, lengths and significant zeros`)
