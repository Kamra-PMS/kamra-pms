#!/usr/bin/env node
/** The food-order basket stays put when someone types "complete the order"
 *  (#640). These checks cover the matching and the error wording. */
import assert from "node:assert/strict"
import fs from "node:fs"
import ts from "typescript"

const filename = new URL("../src/lib/agentMatch.ts", import.meta.url)
const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  },
}).outputText
const mod = {}
new Function("exports", code)(mod)
const { fold, isBasketClose, isBasketClear, spokenHitsChoice, agentFailureText } = mod

assert.equal(fold("Complete the order!"), "complete the order")
assert.equal(fold("أَكْمِل الطلب"), "اكمل الطلب")
assert.equal(fold("إكمال"), "اكمال")

assert.equal(isBasketClose("complete the order"), true)
assert.equal(isBasketClose("اكمل الطلب"), true)
assert.equal(isBasketClose("أكملي الطلب"), true)
assert.equal(isBasketClose("Done"), true)
assert.equal(isBasketClose("send to the kitchen"), true)
assert.equal(isBasketClose("fertig", ["Fertig"]), true)
assert.equal(isBasketClose("two mandi"), false)
assert.equal(isBasketClose(""), false)
assert.equal(isBasketClose("done please"), false)

assert.equal(isBasketClear("clear the order"), true)
assert.equal(isBasketClear("امسح الطلب"), true)
assert.equal(isBasketClear("done"), false)

assert.equal(spokenHitsChoice("mandi", "Chicken Mandi"), true)
assert.equal(spokenHitsChoice("مندي دجاج", "مندي دجاج"), true)
assert.equal(spokenHitsChoice("دجاج", "مندي دجاج"), true)
assert.equal(spokenHitsChoice("a", "Mandi"), false)
assert.equal(spokenHitsChoice("101", "Ada", "Room 101"), true)
assert.equal(spokenHitsChoice("soup", "Tomato soup"), true)

const key = agentFailureText("AI provider error (401): invalid")
assert.equal(key.credit, false)
assert.match(key.text, /check the AI key/)
assert.match(agentFailureText("AI provider error (403): no").text, /check the AI key/)
assert.match(agentFailureText("No API key configured - Settings → AI assistant.").text, /check the AI key/)
const other = agentFailureText("AI provider error (500): boom")
assert.equal(other.credit, false)
assert.match(other.text, /500/)
assert.doesNotMatch(other.text, /check the AI key/)
assert.equal(agentFailureText("You don't have permission for that.").text, "You don't have permission for that.")
assert.equal(agentFailureText("Your AI key is out of credit. Top it up.").credit, true)
assert.match(agentFailureText("").text, /Try again/)

console.log("agent-order-check: ok")
