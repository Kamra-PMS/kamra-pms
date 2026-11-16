/** Picker fallback when a saved UI language is switched off. */
import assert from "node:assert/strict"
import fs from "node:fs"
import ts from "typescript"

const filename = new URL("../src/lib/enabledLanguages.ts", import.meta.url)
const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  },
}).outputText
const mod = {}
new Function("exports", code)(mod)
const { effectiveLanguage, listedLanguages } = mod

const known = ["en", "es", "pt", "ar"]
const langs = known.map((code) => ({ code }))

assert.equal(effectiveLanguage("es", null, known), "es", "before the site answers, keep the saved language")
assert.equal(effectiveLanguage("es", new Set(["en", "pt"]), known, ["pt"]), "pt", "disabled choice falls back to the property language")
assert.equal(effectiveLanguage("es", new Set(["en"]), known, ["ar"]), "en", "disabled property language falls back to English")
assert.equal(effectiveLanguage("zz", new Set(["en", "es"]), known), "en", "unknown code falls back to English")
assert.equal(effectiveLanguage("pt", new Set(["en"]), known), "en", "a switched-off language falls back to English")
assert.equal(effectiveLanguage("en", new Set(), known), "en", "English stays available even if the set forgot it")
assert.equal(effectiveLanguage("PT", new Set(["en", "pt"]), known), "en", "codes are exact; the caller normalises")

const offered = listedLanguages(langs, new Set(["en", "ar"]))
assert.deepEqual(offered.map((lang) => lang.code), ["en", "ar"])
assert.deepEqual(listedLanguages(langs, null).map((lang) => lang.code), known)

const catalog = JSON.parse(fs.readFileSync(new URL("../src/i18n/languages.json", import.meta.url), "utf8"))
assert.equal(catalog[0].code, "en")
assert.ok(catalog.every((row) => row.nativeLabel && row.englishLabel && (row.dir === "ltr" || row.dir === "rtl")))

for (const file of [
  "src/components/LanguageSwitcher.tsx",
  "src/AppShell.tsx",
  "src/screens/Login.tsx",
  "src/screens/settings/cards.tsx",
  "src/screens/BookingEngine.tsx",
]) {
  const text = fs.readFileSync(new URL(`../${file}`, import.meta.url), "utf8")
  assert.equal(text.includes("LANGS.map"), false, `${file} must list offered languages, not every registered one`)
}
const settings = fs.readFileSync(new URL("../src/screens/settings/LanguagesPage.tsx", import.meta.url), "utf8")
assert.ok(settings.includes("LANGS"), "the settings toggles list the whole registry, including languages that are off")

console.log("language picker checks passed")
