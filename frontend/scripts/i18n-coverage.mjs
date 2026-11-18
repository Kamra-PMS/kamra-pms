#!/usr/bin/env node
/**
 * Report how much of the UI catalog each shipped language covers.
 *
 * The catalog (src/i18n/catalog.csv) is the list of English strings the code
 * asks t()/tn() to translate; a locale file is what a language actually ships.
 * "missing" means the UI falls back to English there, "extra" means the locale
 * carries a key no screen uses any more (safe, but worth pruning).
 *
 * Usage:
 *   node scripts/i18n-coverage.mjs                   # one line per language
 *   node scripts/i18n-coverage.mjs --missing zh-CN   # list the missing keys
 *   node scripts/i18n-coverage.mjs --strict          # exit 1 if any language is incomplete
 */
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const catalogPath = path.join(root, "src/i18n/catalog.csv")
const localesDir = path.join(root, "src/i18n/locales")

const args = process.argv.slice(2)
const missingIndex = args.indexOf("--missing")
const missingFor = missingIndex >= 0 ? args[missingIndex + 1] : null
const strict = args.includes("--strict")

/** Minimal RFC-4180 parser: keys with a comma, quote or newline are quoted. */
function parseCsv(text) {
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1)
  const rows = []
  let i = 0
  let field = ""
  let row = []
  let inQuotes = false
  while (i < text.length) {
    const c = text[i]
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"'
          i += 2
          continue
        }
        inQuotes = false
        i++
        continue
      }
      field += c
      i++
      continue
    }
    if (c === '"') {
      inQuotes = true
      i++
      continue
    }
    if (c === ",") {
      row.push(field)
      field = ""
      i++
      continue
    }
    if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++
      row.push(field)
      if (row.some((value) => value.length)) rows.push(row)
      row = []
      field = ""
      i++
      continue
    }
    field += c
    i++
  }
  if (field.length || row.length) {
    row.push(field)
    if (row.some((value) => value.length)) rows.push(row)
  }
  return rows
}

const table = parseCsv(fs.readFileSync(catalogPath, "utf8"))
const header = table[0].map((name) => name.trim().toLowerCase())
const keyIndex = header.indexOf("key")
if (keyIndex < 0) {
  console.error(`Need a 'key' column in ${path.relative(root, catalogPath)}. Found: ${header.join(", ")}`)
  process.exit(2)
}
const catalogKeys = table.slice(1).map((row) => row[keyIndex]).filter(Boolean)
const catalogSet = new Set(catalogKeys)

const languages = fs
  .readdirSync(localesDir)
  .filter((name) => name.endsWith(".json"))
  .map((name) => name.slice(0, -5))
  .sort()

if (missingFor && !languages.includes(missingFor)) {
  console.error(
    `Unknown language '${missingFor}'. Locale files: ${languages.map((code) => `${code}.json`).join(", ")}`,
  )
  process.exit(2)
}

let incomplete = false
for (const language of languages) {
  const dictionary = JSON.parse(fs.readFileSync(path.join(localesDir, `${language}.json`), "utf8"))
  const translatedKeys = new Set(
    catalogKeys.filter((key) => typeof dictionary[key] === "string" && dictionary[key].trim()),
  )
  const missing = catalogKeys.filter((key) => !translatedKeys.has(key))
  const extra = Object.keys(dictionary).filter((key) => !catalogSet.has(key))
  const percent = catalogKeys.length ? (translatedKeys.size / catalogKeys.length) * 100 : 100
  if (missing.length) incomplete = true
  console.log(
    `${language.padEnd(6)} ${String(translatedKeys.size).padStart(5)}/${catalogKeys.length}  ${percent.toFixed(1).padStart(5)}%` +
      `  missing ${String(missing.length).padStart(5)}  extra ${extra.length}`,
  )
  if (missingFor === language) {
    for (const key of missing) console.log(key)
  }
}

if (strict && incomplete) process.exit(1)
