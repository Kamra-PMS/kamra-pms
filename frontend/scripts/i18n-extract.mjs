#!/usr/bin/env node
/**
 * Extract English UI strings from staff frontend sources into catalog.csv.
 * Also merges any existing Arabic from locales/ar.json.
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

const SKIP_DIRS = new Set([
  "PublicBooking.tsx",
  "PublicListing.tsx",
  "PublicCheckin.tsx",
  "QrMenu.tsx",
])

/** Collect t("...") / t('...') / useT().t("...") and common label/title/placeholder literals. */
function walk(dir, files = []) {
  for (const name of fs.readdirSync(dir)) {
    if (SKIP_DIRS.has(name)) continue
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
  const m = [...s.matchAll(/\{(\w+)\}/g)].map((x) => x[1])
  return [...new Set(m)].join(" ")
}

const existingAr = fs.existsSync(arPath)
  ? JSON.parse(fs.readFileSync(arPath, "utf8"))
  : {}

const keys = new Map() // key -> Set<source>

function add(key, source) {
  if (!key || key.length < 2) return
  // skip pure code-ish
  if (/^[\d\s./:_-]+$/.test(key)) return
  if (!/[A-Za-z]/.test(key)) return
  if (!keys.has(key)) keys.set(key, new Set())
  keys.get(key).add(path.relative(src, source))
}

const tCall =
  /\b(?:t|translate)\(\s*(["'`])((?:\\.|(?!\1)[^\\])*)\1/g
const labelLit =
  /\b(?:label|title|placeholder|description|hint|aria-label|CardTitle)\s*[:=]\s*(["'])((?:\\.|(?!\1)[^\\])*)\1/g
const jsxText =
  />\s*([A-Z][^<{]*?[a-zA-Z][^<{]*?)\s*</g

for (const file of walk(src)) {
  const text = fs.readFileSync(file, "utf8")
  for (const re of [tCall, labelLit]) {
    re.lastIndex = 0
    let m
    while ((m = re.exec(text))) {
      const raw = m[2].replace(/\\n/g, "\n").replace(/\\'/g, "'").replace(/\\"/g, '"')
      if (raw.includes("${")) continue
      add(raw, file)
    }
  }
  // apps.ts name/description
  if (file.endsWith("apps.ts") || file.endsWith("configs.ts")) {
    const nameRe = /\b(?:name|description|title|label)\s*:\s*(["'])((?:\\.|(?!\1)[^\\])*)\1/g
    let m
    while ((m = nameRe.exec(text))) add(m[2], file)
  }
}

const rows = [...keys.entries()].sort((a, b) => a[0].localeCompare(b[0]))
const header = "key,english,arabic,sources,placeholders,status"
const lines = [header]
for (const [key, sources] of rows) {
  const ar = existingAr[key] ?? ""
  const status = ar ? "translated" : "needs_translation"
  lines.push(
    [
      csvEscape(key),
      csvEscape(key),
      csvEscape(ar),
      csvEscape([...sources].sort().join("; ")),
      csvEscape(placeholders(key)),
      status,
    ].join(","),
  )
}

// UTF-8 BOM for Excel
fs.writeFileSync(outCsv, "\uFEFF" + lines.join("\n") + "\n", "utf8")
console.log(`Wrote ${rows.length} keys → ${path.relative(root, outCsv)}`)
