#!/usr/bin/env node
/**
 * Find user-visible English that never goes through t(): raw JSX text and the
 * common label/title/placeholder/aria-label attributes. A string inside t() /
 * translate() / tn() is fine; so is anything with a {expression} in it.
 *
 * Usage:
 *   node scripts/i18n-english-scan.mjs             # counts per file
 *   node scripts/i18n-english-scan.mjs --list      # every hit, file:line
 *   node scripts/i18n-english-scan.mjs src/screens/Today.tsx
 */
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const list = process.argv.includes("--list")
const only = process.argv.slice(2).filter((a) => !a.startsWith("--"))

function walk(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, files)
    else if (/\.tsx?$/.test(entry.name) && !entry.name.endsWith(".d.ts")) files.push(p)
  }
  return files
}

// JSX text: >Up to 12 guests<  (no {expression}, starts with a capital or a digit)
const jsxText = />\s*([A-Z0-9][^<>{}`]*?[A-Za-z][^<>{}`]*?)\s*</g
// Attributes a person reads. Values in braces are expressions and are skipped.
const attrText =
  /\b(label|title|placeholder|aria-label|alt|description|subtitle|heading|summary)="([A-Za-z][^"]*[A-Za-z][^"]*)"/g

const files = only.length
  ? only.map((p) => path.resolve(root, p))
  : walk(path.join(root, "src"))

let total = 0
const rows = []
for (const file of files) {
  if (!fs.existsSync(file)) continue
  const source = fs.readFileSync(file, "utf8")
  const lines = source.split("\n")
  for (const [regex, kind] of [
    [jsxText, "text"],
    [attrText, "attr"],
  ]) {
    regex.lastIndex = 0
    let match
    while ((match = regex.exec(source))) {
      const value = (kind === "text" ? match[1] : match[2]).trim()
      // skip code-ish fragments, single words that are clearly identifiers or units
      if (value.length < 3) continue
      if (!/[A-Za-z]{2}/.test(value)) continue
      if (/^[a-z][A-Za-z0-9]*$/.test(value)) continue // camelCase identifier
      if (/^[A-Z]+$/.test(value)) continue // acronym
      if (/^[\w./:-]+$/.test(value)) continue // path, url, class-ish
      if (/(?:^|\s)(?:px|rem|flex|grid|text-|bg-|border)/.test(value)) continue
      const line = source.slice(0, match.index).split("\n").length
      rows.push({ file: path.relative(root, file), line, kind, value, text: lines[line - 1].trim() })
      total++
    }
  }
}

if (list) {
  for (const row of rows) console.log(`${row.file}:${row.line}  [${row.kind}]  ${row.value}`)
} else {
  const byFile = new Map()
  for (const row of rows) byFile.set(row.file, (byFile.get(row.file) ?? 0) + 1)
  for (const [file, count] of [...byFile.entries()].sort((a, b) => b[1] - a[1])) {
    console.log(`${String(count).padStart(4)}  ${file}`)
  }
}
console.log(`\n${total} candidate(s) in ${files.length} file(s)`)
