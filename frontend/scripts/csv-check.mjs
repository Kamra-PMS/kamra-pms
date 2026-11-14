#!/usr/bin/env node
/** Regression checks for src/lib/csv.ts: quoting and the formula guard. */
import assert from "node:assert/strict"
import fs from "node:fs"
import ts from "typescript"

const filename = new URL("../src/lib/csv.ts", import.meta.url)
const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const csv = {}
new Function("exports", code)(csv)
const { csvCell, toCsv } = csv

assert.equal(csvCell("plain"), "plain")
assert.equal(csvCell(null), "")
assert.equal(csvCell(undefined), "")
assert.equal(csvCell(12.5), "12.5")
assert.equal(csvCell(-120), "-120")
assert.equal(csvCell("-120.50"), "-120.50", "a negative amount as text stays a number")
assert.equal(csvCell('say "hi"'), '"say ""hi"""')
assert.equal(csvCell("a,b"), '"a,b"')
assert.equal(csvCell("line\nbreak"), '"line\nbreak"')
assert.equal(csvCell("carriage\rreturn"), '"carriage\rreturn"')
assert.equal(csvCell("=HYPERLINK(\"x\")"), "\"'=HYPERLINK(\"\"x\"\")\"")
assert.equal(csvCell("+1 555"), "'+1 555")
assert.equal(csvCell("@sum"), "'@sum")
assert.equal(csvCell("-"), "'-")
assert.equal(csvCell("  =1+1"), "'  =1+1", "a leading space does not hide a formula")
assert.equal(csvCell("\n=cmd"), "\"'\n=cmd\"")
assert.equal(csvCell("＝SUM(A1)"), "'＝SUM(A1)", "full-width equals")
assert.equal(csvCell(" -5 "), " -5 ", "a padded number stays a number")
assert.equal(toCsv(["A", "B"], [[1, "x"], [null, "y,z"]]), 'A,B\r\n1,x\r\n,"y,z"')

console.log("csv check passed")
