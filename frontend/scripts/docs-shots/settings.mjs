// Docs images for docs-site/settings.md - the settings hub, a module page,
// staff & access, roles, modules, integrations and appearance.
import { done, gif, open, session, settle, shot, typeSlow } from "./lib.mjs"

const ctx = await session()
const page = await ctx.newPage()

await open(page, "/settings", 2500)
await shot(page, "settings/hub")

await open(page, "/settings/front-desk", 2000)
await shot(page, "settings/module-page")

await open(page, "/settings/staff", 2500)
await shot(page, "settings/staff")
const add = page.getByRole("button", { name: "Add staff" })
if (await add.count()) {
  await add.click()
  await page.waitForTimeout(900)
  await shot(page, "settings/add-staff")
  await page.keyboard.press("Escape")
  await page.getByRole("button", { name: "Cancel" }).click().catch(() => {})
}

await open(page, "/settings/roles", 2000)
await shot(page, "settings/roles")
await open(page, "/settings/modules", 2000)
await shot(page, "settings/modules")
await open(page, "/settings/payments", 2000)
await shot(page, "settings/payments")
await open(page, "/settings/ai", 2000)
await shot(page, "settings/ai")
await open(page, "/settings/appearance", 1500)
await shot(page, "settings/appearance")

await gif("settings/search", async (p, _c, rec) => {
  await open(p, "/settings", 2000)
  rec()
  await p.waitForTimeout(600)
  await typeSlow(p.getByPlaceholder(/Search settings/), "no-show", 90)
  await p.waitForTimeout(1200)
  await p.keyboard.press("Enter")
  await settle(p, 1500)
})

await done()
