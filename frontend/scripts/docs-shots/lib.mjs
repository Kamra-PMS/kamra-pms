// Screenshots and GIFs for the docs site (docs-site/public/img).
//
// Capture from a fresh site so the screens show today's sample hotel, not
// a dev database's leftovers:
//   bench new-site docs.localhost --install-app kamra
//   bench --site docs.localhost execute kamra.scripts.seed_demo.execute
// add a docs user with the staff roles, serve that site, then run against it:
//   KAMRA_DOCS_BASE=http://localhost:5173 \
//   KAMRA_DOCS_USER=docs@kamra.localhost KAMRA_DOCS_PASSWORD=... \
//   node scripts/docs-shots/<section>.mjs
//
// Every image is captured fresh from the real app at 1440x900, so the docs
// show what the code does today. GIFs are recorded with Playwright and
// encoded with ffmpeg (must be on PATH).

import { execFileSync } from "node:child_process"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import { chromium } from "playwright"

export const BASE = process.env.KAMRA_DOCS_BASE || "http://localhost:5173"
export const PROPERTY = process.env.KAMRA_DOCS_PROPERTY || "Kamra Demo Palace"
const USER = process.env.KAMRA_DOCS_USER
const PASSWORD = process.env.KAMRA_DOCS_PASSWORD
export const OUT = path.resolve(import.meta.dirname, "../../../docs-site/public/img")
export const VIEWPORT = { width: 1440, height: 900 }

// The playground banner and the floating help button are not part of the
// product a hotel sees.
const CLEAN_CSS = `
  div.bg-amber-500.text-center { display: none !important; }
  button.fixed.bottom-5.right-5.rounded-full { display: none !important; }
`

let browser

/** A logged-in browser context on the sample property. */
export async function session({ viewport = VIEWPORT } = {}) {
  if (!USER || !PASSWORD) throw new Error("Set KAMRA_DOCS_USER and KAMRA_DOCS_PASSWORD")
  browser ??= await chromium.launch({ channel: "chrome", headless: true })
  const ctx = await browser.newContext({
    viewport, deviceScaleFactor: 1, locale: "en-GB", colorScheme: "light",
  })
  await ctx.addInitScript(([prop, css]) => {
    try { localStorage.setItem("kamra_property", prop) } catch { /* ignore */ }
    const add = () => {
      const s = document.createElement("style")
      s.textContent = css
      document.head.appendChild(s)
    }
    if (document.head) add(); else document.addEventListener("DOMContentLoaded", add)
  }, [PROPERTY, CLEAN_CSS])
  // the dev server is single-process; retry a busy moment rather than fail the run
  let r
  for (let i = 0; i < 4; i++) {
    r = await ctx.request.post(`${BASE}/api/method/login`, { form: { usr: USER, pwd: PASSWORD } })
    if (r.ok()) break
    await new Promise((res) => setTimeout(res, 1500))
  }
  if (!r.ok()) throw new Error(`login failed: ${r.status()}`)
  return ctx
}

/** Call a whitelisted method as the docs user (to set up or clean up data). */
export async function api(ctx, method, data = {}) {
  const res = await ctx.request.post(`${BASE}/api/method/${method}`, { data })
  const j = await res.json().catch(() => ({}))
  if (!res.ok()) throw new Error(`${method} ${res.status()} ${JSON.stringify(j).slice(0, 400)}`)
  return j.message
}

/** Open a route of the SPA and let it settle. */
export async function open(page, route, wait = 1800) {
  await page.goto(`${BASE}${route}`)
  await settle(page, wait)
}

/** Wait until the screen has data: network quiet and no "Loading" text or
 *  spinner left. Several capture scripts can share one dev server, so a
 *  fixed sleep isn't enough. */
export async function settle(page, wait = 1200) {
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => {})
  await page.waitForFunction(() => {
    const t = document.body?.innerText || ""
    return t.length > 200 && !/^\s*Loading/m.test(t) && !document.querySelector(".animate-spin")
  }, null, { timeout: 25_000 }).catch(() => {})
  await page.waitForTimeout(wait)
}

/** Save a PNG under docs-site/public/img/<name>.png. Pass `locator` to
 *  capture one element, or `clip` for a region; default is the viewport. */
export async function shot(page, name, { locator, clip, fullPage = false } = {}) {
  const file = path.join(OUT, `${name}.png`)
  fs.mkdirSync(path.dirname(file), { recursive: true })
  if (locator) await locator.screenshot({ path: file })
  else await page.screenshot({ path: file, clip, fullPage })
  console.log("shot", path.relative(OUT, file), Math.round(fs.statSync(file).size / 1024) + " KB")
  return file
}

/** Record `steps` in a fresh page and save docs-site/public/img/<name>.gif.
 *  Frames are screenshots taken while the steps run (no Playwright video,
 *  so only the system ffmpeg is needed), stitched with their real timing.
 *  Keep flows short (5-15 s). If `steps` takes a third argument, recording
 *  waits until it calls `rec()` (so the GIF skips the loading); otherwise it
 *  starts when the first page loads. The GIF is scaled to `width`. `viewport`
 *  records at another size (e.g. a phone). */
export async function gif(name, steps, { width = 960, fps = 8, crop, viewport } = {}) {
  const ctx = await session(viewport ? { viewport } : {})
  const page = await ctx.newPage()
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "kamra-gif-"))
  const frames = []
  let recording = false
  let stop = false
  const every = 1000 / fps
  const loop = (async () => {
    while (!stop) {
      const t0 = Date.now()
      if (recording) {
        const f = path.join(dir, `f${String(frames.length).padStart(5, "0")}.png`)
        try {
          await page.screenshot({ path: f, clip: crop })
          frames.push({ f, at: t0 })
        } catch { /* page navigating */ }
      }
      await new Promise((r) => setTimeout(r, Math.max(0, every - (Date.now() - t0))))
    }
  })()
  try {
    // Steps may call rec() once their screen is ready, so the GIF starts
    // there; otherwise recording starts when the first page loads.
    const rec = () => { recording = true }
    if (steps.length < 3) page.once("load", () => { recording = true })
    await steps(page, ctx, rec)
    recording = true
    await page.waitForTimeout(1200)
  } finally {
    stop = true
    await loop
    await page.close()
    await ctx.close()
  }
  if (!frames.length) throw new Error(`gif ${name}: no frames`)
  // concat list with each frame's real duration
  const list = frames.map((fr, i) => {
    const next = frames[i + 1]?.at ?? fr.at + every
    return `file '${fr.f}'\nduration ${((next - fr.at) / 1000).toFixed(3)}`
  }).join("\n") + `\nfile '${frames.at(-1).f}'\n`
  const listFile = path.join(dir, "frames.txt")
  fs.writeFileSync(listFile, list)
  const file = path.join(OUT, `${name}.gif`)
  fs.mkdirSync(path.dirname(file), { recursive: true })
  const vf = `fps=${fps},scale=${width}:-1:flags=lanczos,split[a][b];` +
    `[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle`
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listFile, "-vf", vf, file])
  fs.rmSync(dir, { recursive: true, force: true })
  console.log("gif ", path.relative(OUT, file), Math.round(fs.statSync(file).size / 1024) + " KB")
  return file
}

/** Slow, visible typing for GIFs. */
export async function typeSlow(locator, text, delay = 60) {
  await locator.click()
  await locator.pressSequentially(text, { delay })
}

export async function done() {
  await browser?.close()
}
