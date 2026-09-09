#!/usr/bin/env node
/**
 * Extract English UI strings from t() / translate() calls into catalog.csv.
 * Merges existing Arabic from locales/ar.json.
 *
 * Usage: node scripts/i18n-extract.mjs
 */
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.join(__dirname, "..")
const src = path.join(root, "src")
const outCsv = path.join(root, "src/i18n/catalog.csv")
const arPath = path.join(root, "src/i18n/locales/ar.json")

const SKIP = new Set([
  "PublicBooking.tsx",
  "PublicListing.tsx",
  "PublicCheckin.tsx",
  "QrMenu.tsx",
])

function walk(dir, files = []) {
  for (const name of fs.readdirSync(dir)) {
    if (SKIP.has(name)) continue
    const p = path.join(dir, name)
    const st = fs.statSync(p)
    if (st.isDirectory()) walk(p, files)
    else if (/\.(tsx|ts)$/.test(name) && !name.endsWith(".d.ts")) files.push(p)
  }
  return files
}

function csvEscape(s) {
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

function placeholders(s) {
  return [...new Set([...s.matchAll(/\{(\w+)\}/g)].map((x) => x[1]))].join(" ")
}

const existingAr = fs.existsSync(arPath)
  ? JSON.parse(fs.readFileSync(arPath, "utf8"))
  : {}

const keys = new Map()
const tCall =
  /\b(?:t|translate)\(\s*(["'`])((?:\\.|(?!\1)[^\\])*)\1/g

function add(key, source) {
  if (!key || !/[A-Za-z]/.test(key)) return
  if (key.includes("${")) return
  if (!keys.has(key)) keys.set(key, new Set())
  keys.get(key).add(path.relative(src, source))
}

for (const file of walk(src)) {
  const text = fs.readFileSync(file, "utf8")
  tCall.lastIndex = 0
  let m
  while ((m = tCall.exec(text))) {
    add(
      m[2].replace(/\\n/g, "\n").replace(/\\'/g, "'").replace(/\\"/g, '"'),
      file,
    )
  }
}

const rows = [...keys.entries()].sort((a, b) => a[0].localeCompare(b[0]))
const lines = ["key,english,arabic,sources,placeholders,status"]
for (const [key, sources] of rows) {
  const ar = existingAr[key] ?? ""
  lines.push(
    [
      csvEscape(key),
      csvEscape(key),
      csvEscape(ar),
      csvEscape([...sources].sort().join("; ")),
      csvEscape(placeholders(key)),
      ar ? "translated" : "needs_translation",
    ].join(","),
  )
}

fs.writeFileSync(outCsv, "\uFEFF" + lines.join("\n") + "\n", "utf8")
console.log(`Wrote ${rows.length} keys → ${path.relative(root, outCsv)}`)
