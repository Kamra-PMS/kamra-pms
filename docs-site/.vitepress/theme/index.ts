import DefaultTheme from "vitepress/theme"
import { h } from "vue"
import type { Theme } from "vitepress"
import VersionSwitcher from "./VersionSwitcher.vue"
import VersionBanner from "./VersionBanner.vue"
import "./custom.css"

export default {
  extends: DefaultTheme,
  Layout() {
    return h(DefaultTheme.Layout, null, {
      "nav-bar-content-before": () => h(VersionSwitcher),
      "layout-top": () => h(VersionBanner),
    })
  },
  enhanceApp({ app, router, siteData }) {
    app.component("VersionSwitcher", VersionSwitcher)
    // English-only pages have no /es/ or /ar/ copy, so the language menu goes to
    // that language's home instead of a 404.
    router.onBeforeRouteChange = (to) => {
      const { base, themeConfig } = siteData.value
      const path = new URL(to, "http://x").pathname.slice(base.length)
      const hit = path.match(/^(es|ar)\/(.+?)(?:\.html)?$/)
      if (hit && !themeConfig.docTranslated.includes(hit[2])) {
        router.go(`${base}${hit[1]}/`)
        return false
      }
    }
  },
} satisfies Theme
