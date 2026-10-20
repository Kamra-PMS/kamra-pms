#!/usr/bin/env node
/**
 * Build the docs site.
 *
 * Latest (default):
 *   node scripts/build.mjs
 *   → .vitepress/dist  with base /docs/
 *
 * Frozen archive for a release:
 *   DOCS_VERSION=2.6.16 node scripts/build.mjs --archive
 *   → .vitepress/dist-archive  with base /docs/v2.6.16/
 */
import { spawnSync } from "node:child_process"
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const root = join(dirname(fileURLToPath(import.meta.url)), "..")
const archive = process.argv.includes("--archive")
const version = (process.env.DOCS_VERSION || "").replace(/^v/, "")

if (archive && !version) {
  console.error("DOCS_VERSION is required for --archive")
  process.exit(1)
}

const versionsPath = join(root, "versions.json")
const versions = JSON.parse(readFileSync(versionsPath, "utf8"))

const base = archive ? `/docs/v${version}/` : "/docs/"
const outDir = archive ? ".vitepress/dist-archive" : ".vitepress/dist"
const current = archive ? version : versions.latest

// VitePress reads base from config; override via a tiny generated sidecar
// that config.mts imports when present.
const overridePath = join(root, ".vitepress/version.override.json")
writeFileSync(
  overridePath,
  `${JSON.stringify({ base, current, outDir }, null, 2)}\n`,
)

const env = {
  ...process.env,
  DOCS_BASE: base,
  DOCS_CURRENT: current,
  DOCS_OUT_DIR: outDir,
}

console.log(`build docs: base=${base} current=${current} outDir=${outDir}`)
const r = spawnSync("npx", ["vitepress", "build"], {
  cwd: root,
  env,
  stdio: "inherit",
})
if (r.status !== 0) process.exit(r.status || 1)

// Copy versions.json into the built site for runtime fetch fallbacks
const dist = join(root, outDir)
if (existsSync(dist)) {
  writeFileSync(join(dist, "versions.json"), `${JSON.stringify(versions, null, 2)}\n`)
}

if (archive) {
  // Keep a local copy under public-archives for optional commit/debug
  const keep = join(root, "archives", `v${version}`)
  mkdirSync(dirname(keep), { recursive: true })
  rmSync(keep, { recursive: true, force: true })
  cpSync(dist, keep, { recursive: true })
  console.log(`archive copy: ${keep}`)
}
