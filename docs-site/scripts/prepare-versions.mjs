#!/usr/bin/env node
/**
 * Sync versions.json for a release snapshot and rewrite labels so only
 * `latest` is marked "(latest)". Used by CI before building docs.
 *
 *   DOCS_VERSION=2.6.16 node scripts/prepare-versions.mjs
 *   DOCS_VERSION=2.6.17 DOCS_MAKE_LATEST=1 node scripts/prepare-versions.mjs
 */
import { readFileSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const root = join(dirname(fileURLToPath(import.meta.url)), "..")
const path = join(root, "versions.json")
const raw = JSON.parse(readFileSync(path, "utf8"))

const version = (process.env.DOCS_VERSION || "").replace(/^v/, "")
const makeLatest = process.env.DOCS_MAKE_LATEST === "1" || process.env.DOCS_MAKE_LATEST === "true"

if (!version) {
  console.log("prepare-versions: no DOCS_VERSION - leaving versions.json unchanged")
  process.exit(0)
}

const versions = Array.isArray(raw.versions) ? [...raw.versions] : []
// Re-freezing an older release must not demote the current latest
const newer = !raw.latest || version.localeCompare(raw.latest, undefined, { numeric: true }) >= 0
const latest = makeLatest && newer ? version : raw.latest || version

// Upsert this version: latest → path "/", archives → /vX.Y.Z/
function entryFor(v, isLatest) {
  return {
    version: v,
    label: isLatest ? `${v} (latest)` : v,
    path: isLatest ? "/" : `/v${v}/`,
  }
}

const byVersion = new Map()
for (const v of versions) {
  if (v?.version) byVersion.set(v.version, v)
}
byVersion.set(version, entryFor(version, version === latest))

// Re-label every known version against the current latest
const ordered = [...byVersion.values()]
  .map((v) => entryFor(v.version, v.version === latest))
  .sort((a, b) => {
    if (a.version === latest) return -1
    if (b.version === latest) return 1
    return b.version.localeCompare(a.version, undefined, { numeric: true })
  })

const out = { latest, versions: ordered }
writeFileSync(path, `${JSON.stringify(out, null, 2)}\n`)
console.log(`prepare-versions: latest=${latest} current=${version} count=${ordered.length}`)
