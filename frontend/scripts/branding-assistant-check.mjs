#!/usr/bin/env node
// Isolated SPA regression checks. Uses the existing Vite/Playwright dependencies;
// every API call is intercepted, so no bench or customer account is contacted.
import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { test } from "node:test"
import { chromium } from "playwright"
import { createServer } from "vite"

const server = await createServer({
  server: { host: "127.0.0.1", port: 0, strictPort: false, proxy: {} },
})
await server.listen()
const base = `http://127.0.0.1:${server.httpServer.address().port}`
let browser
const screenshotDir = process.env.KAMRA_CHECK_SCREENSHOTS
if (screenshotDir) await fs.mkdir(screenshotDir, { recursive: true })

async function session({ enabled = false, statusError = false, pending = false,
  branding = {}, siteError = false } = {}) {
  browser ??= await chromium.launch({ channel: "chrome", headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  await context.addInitScript(() => localStorage.setItem("kamra_property", "Test Hotel"))
  const page = await context.newPage()
  const errors = []
  page.on("pageerror", (error) => errors.push(error.message))
  const calls = []
  let releaseStatus
  const held = new Promise((resolve) => { releaseStatus = resolve })
  await context.route("**/socket.io/**", (route) => route.abort())
  await context.route("**/files/test-logo.svg", (route) => route.fulfill({
    contentType: "image/svg+xml",
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#125780"/></svg>',
  }))
  await context.route("**/api/**", async (route) => {
    const method = new URL(route.request().url()).pathname.split("/").at(-1)
    calls.push(method)
    const payloads = {
      "kamra.api.whoami": { user: "staff@example.test", full_name: "Test Staff", roles: ["Hotel Admin", "Front Desk"] },
      "kamra.api.my_properties": [
        { name: "Test Hotel", property_name: "Test Hotel" },
        { name: "Other Hotel", property_name: "Other Hotel" },
      ],
      "kamra.api.enabled_modules": [],
      "kamra.api.guest_search": [],
      "kamra.api.find_reservations": [],
      "kamra.api.find_invoices": [],
      "kamra.api.property_locale": { currency: "USD", locale: "en-US", currency_symbol: "$" },
      "kamra.api.cashier_pin_status": { required: false, unlocked: true },
      "kamra.onboarding.setup_checklist": { percent: 100, done: 1, total: 1 },
      "kamra.settings.settings_schema": { modules: [] },
      "kamra.assistant.list_conversations": [],
      "kamra.public_api.site_info": {
        demo_mode: false, app: "kamra", version: "2.6.19", channel: "nightly", build: "abc123",
        ...branding,
      },
      "kamra.health.update_nag": {
        available: true, installed: "2.6.19",
        latest: { tag: "v2.6.23", name: "2.6.23", url: "https://example.test/release" },
      },
    }
    if (method === "kamra.assistant.assistant_status") {
      if (pending) await held
      if (statusError) return route.fulfill({ status: 503, json: { message: "unavailable" } })
      const property = route.request().postDataJSON()?.property
      return route.fulfill({ json: { message: {
        enabled: property === "Other Hotel" ? false : enabled,
        model: "test-model", base_url: "https://example.test/v1",
        key_hint: enabled ? "••••test" : null, processor_disclosure: {},
        redact_guest_contact_details: true,
      } } })
    }
    if (method === "kamra.public_api.site_info" && siteError)
      return route.fulfill({ status: 503, json: { message: "unavailable" } })
    return route.fulfill({ json: { message: payloads[method] ?? {} } })
  })
  return { page, calls, releaseStatus, close: async () => {
    await context.close()
    assert.deepEqual(errors, [], "SPA must not raise unhandled browser errors")
  } }
}

async function settled(page, route = "/apps", pending = false) {
  await page.goto(base + route)
  await page.getByRole("link", { name: "Home", exact: true }).waitFor()
  await page.getByRole("status").waitFor()
  if (!pending) await page.waitForLoadState("networkidle")
}

async function assistantLinks(page) {
  return page.locator('a[href="/assistant"], a[href="/agents"]').count()
}

try {
  await test("empty app registry never restores hidden assistant navigation", async () => {
    const { appForPath, visibleApps } = await server.ssrLoadModule("/src/lib/apps.ts")
    const apps = visibleApps([], undefined, false)
    for (const route of ["/", "/apps", "/assistant"])
      assert.deepEqual(appForPath(route, apps).items, [])
  })

  await test("fallback navigation keeps assistant filtering on non-menu routes", async () => {
    const s = await session({ pending: true })
    try {
      await settled(s.page, "/apps", true)
      const routes = await s.page.evaluate(async () => {
        const { appForPath, visibleApps } = await import("/src/lib/apps.ts")
        return appForPath("/apps", visibleApps(["Hotel Admin"], undefined, false))
          .items.map((item) => item.to)
      })
      assert.equal(routes.includes("/assistant"), false)
    } finally {
      s.releaseStatus()
      await s.close()
    }
  })

  for (const [name, options] of [
    ["disabled or unconfigured", { enabled: false }],
    ["status failure", { statusError: true }],
    ["missing enabled flag", { enabled: null }],
    ["malformed enabled flag", { enabled: "false" }],
    ["pending status", { pending: true }],
  ]) {
    await test(`assistant navigation is absent for ${name}`, async () => {
      const s = await session(options)
      try {
        await settled(s.page, "/apps", options.pending)
        assert.equal(await assistantLinks(s.page), 0)
        await s.page.evaluate(() => window.dispatchEvent(new Event("kamra:open-palette")))
        const input = s.page.locator('input').filter({ visible: true }).first()
        const searches = ["guest_search", "find_reservations", "find_invoices"]
          .map((method) => s.page.waitForResponse(`**/api/method/kamra.api.${method}`))
        await input.fill("Kamra Agent")
        await Promise.all(searches)
        await s.page.getByRole("dialog").locator(".animate-spin").waitFor({ state: "hidden" })
        assert.equal(await s.page.getByRole("button", { name: /Kamra Agent/ }).count(), 0)
        if (screenshotDir && name === "disabled or unconfigured")
          await s.page.screenshot({ path: path.join(screenshotDir, "disabled-assistant-search.png") })
      } finally {
        s.releaseStatus()
        await s.close()
      }
    })
  }

  for (const route of ["/assistant", "/agents"]) {
    for (const [name, options] of [
      ["disabled", {}], ["failed", { statusError: true }], ["pending", { pending: true }],
    ]) {
      await test(`${route} cannot open chat when status is ${name}`, async () => {
        const s = await session(options)
        try {
          await settled(s.page, route, options.pending)
          assert.equal(await s.page.getByRole("heading", { name: "Kamra Agent", exact: true }).count(), 0)
          assert.equal(s.calls.includes("kamra.assistant.list_conversations"), false)
          assert.equal(await s.page.getByRole("button", { name: "Send", exact: true }).count(), 0)
        } finally {
          s.releaseStatus()
          await s.close()
        }
      })
    }
  }

  await test("enabled and configured assistant remains reachable, then hides on property change", async () => {
    const s = await session({ enabled: true })
    try {
      await settled(s.page)
      assert.equal(await assistantLinks(s.page), 1)
      await s.page.locator('a[href="/assistant"]').click()
      await s.page.getByRole("heading", { name: "Kamra Agent", exact: true }).waitFor()
      await s.page.getByPlaceholder("Ask anything about the hotel…").waitFor()
      assert.equal(await s.page.getByPlaceholder("Ask anything about the hotel…").isEnabled(), true)
      await s.page.getByRole("combobox", { name: "Property", exact: true }).selectOption("Other Hotel")
      await s.page.waitForLoadState("networkidle")
      assert.equal(await assistantLinks(s.page), 0)
      assert.equal(await s.page.getByRole("button", { name: "Send", exact: true }).count(), 0)
    } finally { await s.close() }
  })

  for (const [name, branding, siteError, wantName, wantLogo] of [
    ["native branding", { app_name: "Example Hotels", app_logo: "/files/test-logo.svg" }, false, "Example Hotels", "/files/test-logo.svg"],
    ["name only", { app_name: "Example Hotels" }, false, "Example Hotels", "kamra-mark.svg"],
    ["logo only", { app_logo: "/files/test-logo.svg" }, false, "Kamra PMS", "/files/test-logo.svg"],
    ["unset branding", {}, false, "Kamra PMS", "kamra-mark.svg"],
    ["blank branding", { app_name: " ", app_logo: " " }, false, "Kamra PMS", "kamra-mark.svg"],
    ["unavailable metadata", {}, true, "Kamra PMS", "kamra-mark.svg"],
    ["plain text branding", { app_name: "<b>Example & Hotels</b>" }, false, "<b>Example & Hotels</b>", "kamra-mark.svg"],
  ]) {
    await test(`shell and browser title respect ${name}`, async () => {
      const s = await session({ branding, siteError })
      try {
        await settled(s.page)
        assert.equal(await s.page.title(), wantName)
        const home = s.page.getByRole("link", { name: "Home", exact: true })
        assert.equal((await home.innerText()).replace(/\s+/g, " ").trim(), wantName)
        assert.ok((await home.locator("img").getAttribute("src")).endsWith(wantLogo))
        assert.equal(await home.locator("b").count(), 0)
        if (screenshotDir && name === "native branding")
          await s.page.screenshot({ path: path.join(screenshotDir, "native-branding.png") })
      } finally { await s.close() }
    })
  }

  await test("update banner is product-neutral and preserves real versions", async () => {
    const s = await session()
    try {
      await settled(s.page)
      const text = await s.page.getByRole("status").innerText()
      assert.match(text, /2\.6\.23/)
      assert.match(text, /2\.6\.19/)
      assert.doesNotMatch(text, /Kamra/)
      assert.equal(await s.page.getByRole("link", { name: "View update", exact: true }).getAttribute("href"), "/health")
    } finally { await s.close() }
  })
} finally {
  await browser?.close()
  await server.close()
}
