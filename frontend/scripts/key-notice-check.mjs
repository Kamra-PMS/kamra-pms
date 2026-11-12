#!/usr/bin/env node
/** Regression checks: undoing a check-in shows the lock system's message
 * (key_result.message) to the desk instead of dropping it when the panel
 * closes - the way CheckInDialog shows key_result after check-in. */
import assert from "node:assert/strict"
import fs from "node:fs"
import ts from "typescript"

const read = (rel) => fs.readFileSync(new URL(`../src/${rel}`, import.meta.url), "utf8")
const code = ts.transpileModule(read("lib/keyNotice.ts"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const mod = {}
new Function("exports", code)(mod)
const { keyResultMessage } = mod

const failed = "The lock system did not answer. Cancel the keys at the encoder."
assert.equal(keyResultMessage({ key_result: { ok: false, message: failed } }), failed, "connector failure is shown")
assert.equal(keyResultMessage({ key_result: { ok: true, message: "Keys cancelled" } }), "Keys cancelled", "vendor message is shown")
assert.equal(keyResultMessage({ key_result: null }), null, "manual keys: nothing to show")
assert.equal(keyResultMessage({ key_result: { ok: true, message: "  " } }), null, "blank message: nothing to show")
assert.equal(keyResultMessage({}), null, "no key_result")
assert.equal(keyResultMessage(undefined), null, "no response")

// the panel unmounts once the stay is no longer checked in, so it hands the
// message to the reservation screen, which keeps it on screen
function calls(rel, name) {
  const source = ts.createSourceFile(rel, read(rel), ts.ScriptTarget.Latest, true)
  const found = []
  const visit = (node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === name) found.push(node)
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found
}
const done = calls("components/ReverseCheckInPanel.tsx", "onDone")
assert.ok(
  done.some((c) => c.arguments.some((a) => ts.isCallExpression(a) && a.expression.getText() === "keyResultMessage")),
  "ReverseCheckInPanel passes keyResultMessage(<reverse_check_in result>) to onDone",
)
const detail = read("screens/ReservationDetail.tsx")
assert.match(detail, /<ReverseCheckInPanel[^>]*onDone=\{\(\w+\) =>/, "ReservationDetail keeps the panel's message")
assert.match(detail, /translate\(reverseKeys\)/, "ReservationDetail shows the message, translated")

for (const language of ["ar", "es", "pt"]) {
  const dictionary = JSON.parse(read(`i18n/locales/${language}.json`))
  assert.ok(dictionary[failed]?.trim(), `${language}: translation for the lock failure message`)
}
assert.ok(read("i18n/catalog.csv").includes(`\n${failed},`), "catalog row for the lock failure message")

console.log("key-notice-check: ok")
