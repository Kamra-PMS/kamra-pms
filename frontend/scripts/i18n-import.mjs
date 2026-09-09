#!/usr/bin/env node
/**
 * Import filled catalog.csv into locales/<lang>.json.
 *
 * Usage:
 *   node scripts/i18n-import.mjs              # arabic → ar.json
 *   node scripts/i18n-import.mjs --lang hi --column hindi
 */
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.join(__dirname, "..")
const csvPath = path.join(root, "src/i18n/catalog.csv")

const args = process.argv.slice(2)
let lang = "ar"
let column = "arabic"
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--lang") lang = args[++i]
  if (args[i] === "--column") column = args[++i]
}

function parseCsv(text) {
  // strip BOM
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1)
  const rows = []
  let i = 0
  let field = ""
  let row = []
  let inQ = false
  while (i < text.length) {
    const c = text[i]
    if (inQ) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"'
          i += 2
          continue
        }
        inQ = false
        i++
        continue
      }
      field += c
      i++
      continue
    }
    if (c === '"') {
      inQ = true
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
      if (row.some((x) => x.length)) rows.push(row)
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
    if (row.some((x) => x.length)) rows.push(row)
  }
  return rows
}

const raw = fs.readFileSync(csvPath, "utf8")
const table = parseCsv(raw)
const header = table[0].map((h) => h.trim().toLowerCase())
const keyIdx = header.indexOf("key")
const colIdx = header.indexOf(column.toLowerCase())
if (keyIdx < 0 || colIdx < 0) {
  console.error(`Need columns 'key' and '${column}'. Found: ${header.join(", ")}`)
  process.exit(1)
}

const dict = {}
let filled = 0
for (const row of table.slice(1)) {
  const key = row[keyIdx]
  const val = (row[colIdx] || "").trim()
  if (!key) continue
  if (val) {
    dict[key] = val
    filled++
  }
}

const out = path.join(root, `src/i18n/locales/${lang}.json`)
fs.mkdirSync(path.dirname(out), { recursive: true })
fs.writeFileSync(out, JSON.stringify(dict, null, 2) + "\n", "utf8")
console.log(`Wrote ${filled} translations → ${path.relative(root, out)}`)
