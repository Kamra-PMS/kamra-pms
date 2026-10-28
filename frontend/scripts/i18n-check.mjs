#!/usr/bin/env node
/** Check locale parameters and guard against translating text twice. */
import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import { createRequire } from "node:module"
import { fileURLToPath } from "node:url"
import ts from "typescript"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const localeDirectory = path.join(root, "src/i18n/locales")
const dictionaries = { en: {} }
const parameters = (value) => [...new Set([...value.matchAll(/\{(\w+)\}/g)].map((match) => match[1]))].sort()

for (const filename of fs.readdirSync(localeDirectory).filter((name) => name.endsWith(".json"))) {
  const language = filename.slice(0, -5)
  const source = fs.readFileSync(path.join(localeDirectory, filename), "utf8")
  const document = ts.parseJsonText(filename, source)
  const names = document.statements[0].expression.properties.map((property) => property.name.text)
  assert.equal(new Set(names).size, names.length, `${language}: duplicate dictionary keys`)
  const dictionary = JSON.parse(source)
  dictionaries[language] = dictionary
  for (const [key, value] of Object.entries(dictionary)) {
    assert.equal(typeof value, "string", `${language}: non-string translation for ${key}`)
    assert.ok(value.trim(), `${language}: empty translation for ${key}`)
    assert.deepEqual(parameters(value), parameters(key), `${language}: placeholder mismatch for ${key}`)
  }
}

const translatorNames = new Set(["t", "tn", "translate", "translateUI"])
function isTranslation(node) {
  return ts.isCallExpression(node) && ts.isIdentifier(node.expression) && translatorNames.has(node.expression.text)
}
function containsTranslation(node) {
  return isTranslation(node) || !!ts.forEachChild(node, containsTranslation)
}
function checkDirectory(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const filename = path.join(directory, entry.name)
    if (entry.isDirectory()) checkDirectory(filename)
    else if (/\.tsx?$/.test(filename)) {
      const source = ts.createSourceFile(filename, fs.readFileSync(filename, "utf8"), ts.ScriptTarget.Latest, true)
      function visit(node) {
        if (isTranslation(node) && node.arguments[0] && containsTranslation(node.arguments[0])) {
          const line = source.getLineAndCharacterOfPosition(node.getStart()).line + 1
          assert.fail(`${path.relative(root, filename)}:${line}: nested translation`)
        }
        ts.forEachChild(node, visit)
      }
      visit(source)
    }
  }
}
checkDirectory(path.join(root, "src"))

// Exercise the real translator with a selected language and real dictionaries.
// React hooks are imported normally; these checks call only the pure t()/tn().
const require = createRequire(import.meta.url)
let language = "en"
const output = ts.transpileModule(fs.readFileSync(path.join(root, "src/lib/i18n.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const api = {}
new Function("require", "exports", output)((name) => {
  if (name === "react") return require("react")
  if (name === "./dir") return { getLang: () => language }
  if (name === "./locales") return { dictionaryFor: (key) => dictionaries[key] ?? {} }
  throw new Error(`Unexpected translator import: ${name}`)
}, api)
assert.equal(api.t("Phone"), "Phone")
assert.equal(api.t("Room {n}", { n: 12 }), "Room 12")
assert.equal(api.tn(1, "{n} night", "{n} nights"), "1 night")
assert.equal(api.tn(2, "{n} night", "{n} nights"), "2 nights")
language = "es"
assert.equal(api.t("Phone"), "Teléfono")
assert.equal(api.tn(2, "{n} night", "{n} nights"), "2 noches")
for (const raw of ["Room types not configured", "Room 17: unexpected error", "constructor", "__proto__"]) {
  assert.equal(api.t(raw), raw, "Unknown runtime text must remain unchanged")
}
assert.equal(api.t(undefined), undefined)
const content = { message: "React content" }
assert.equal(api.t(content), content)
language = "ar"
assert.equal(api.t("Phone"), "الهاتف")
language = "pt"
assert.equal(api.t("Phone"), "Telefone")
assert.equal(api.tn(2, "{n} night", "{n} nights"), "2 noites")
language = "unknown"
assert.equal(api.t("Phone"), "Phone")
const app = fs.readFileSync(path.join(root, "src/App.tsx"), "utf8")
assert.ok(!/(?:translate|translateUI|t)\(this\.state\.error\.message\)/.test(app), "Keep raw ErrorBoundary diagnostics intact")
console.log("i18n checks passed: dictionaries, placeholders, duplicate calls, English/Spanish/Arabic/Portuguese and fallback behavior")
