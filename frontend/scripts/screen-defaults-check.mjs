#!/usr/bin/env node
/** Two things a screen can get wrong without any error: a background in a brand shade the theme never
 *  defines (it paints nothing, so a bar looks empty), and a new record's tick box showing off while the
 *  record is saved with it on. */
import assert from "node:assert/strict"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { build } from "esbuild"

const src = fileURLToPath(new URL("../src/", import.meta.url))

// ---- backgrounds: every brand shade used as one is a shade the theme defines
const css = fs.readFileSync(path.join(src, "index.css"), "utf8")
const theme = css.slice(css.indexOf("@theme"), css.indexOf("\n}", css.indexOf("@theme")))
const shades = new Set([...theme.matchAll(/--color-brand-(\d+):/g)].map((m) => m[1]))
assert.ok(shades.has("600"), "the theme's brand shades were not read")
const unpainted = fs.readdirSync(src, { recursive: true })
  .filter((f) => /\.tsx?$/.test(f))
  .flatMap((f) => [...fs.readFileSync(path.join(src, f), "utf8").matchAll(/\bbg-brand-(\d+)/g)]
    .filter((m) => !shades.has(m[1]))
    .map((m) => `${f.replaceAll(path.sep, "/")}: ${m[0]}`))
  .sort()
assert.deepEqual(unpainted, [], "backgrounds in a shade the theme does not define")

// ---- tick boxes: a new record starts as it would be saved
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "screen-defaults-"))
const stubs = `export const floorSource = {}; export const lazy = () => null
export const cur = () => ""; export const locale = () => "en"; export const sellsAlcohol = () => true`
await build({
  entryPoints: [path.join(src, "screens/configs.ts")],
  bundle: true, format: "esm", platform: "node", outfile: path.join(dir, "configs.mjs"), logLevel: "silent",
  plugins: [{
    name: "stand-ins",
    setup(b) {
      b.onResolve({ filter: /.*/ }, (a) => a.kind === "entry-point" ? undefined
        : { path: a.kind === "dynamic-import" ? "none" : "stubs", namespace: "stub" })
      b.onLoad({ filter: /.*/, namespace: "stub" },
        (a) => ({ contents: a.path === "stubs" ? stubs : "export default null", loader: "js" }))
    },
  }],
})
const configs = Object.values(await import(pathToFileURL(path.join(dir, "configs.mjs")).href))
  .filter((c) => c?.doctype && Array.isArray(c.form))
const doctypes = new URL("../../kamra/kamra/doctype/", import.meta.url)
const off = []
let seen = 0
for (const config of configs) {
  const name = config.doctype.toLowerCase().replaceAll(" ", "_")
  const file = new URL(`${name}/${name}.json`, doctypes)
  if (!fs.existsSync(file)) continue
  const saved = Object.fromEntries(JSON.parse(fs.readFileSync(file, "utf8")).fields
    .map((f) => [f.fieldname, String(f.default ?? "")]))
  for (const spec of config.form) {
    if (spec.type !== "check" && spec.type !== "switch") continue
    seen += 1
    if (saved[spec.field] === "1" && Number(spec.defaultValue) !== 1) off.push(`${config.doctype}: ${spec.field}`)
  }
}
assert.ok(seen >= 20, `only ${seen} tick boxes were read`)
assert.deepEqual(off.sort(), [], "saved ticked, but a new record shows them off")

fs.rmSync(dir, { recursive: true, force: true })
console.log(`screen defaults check passed: ${seen} tick boxes, ${shades.size} brand shades`)
