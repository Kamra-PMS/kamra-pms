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
  enhanceApp({ app }) {
    app.component("VersionSwitcher", VersionSwitcher)
  },
} satisfies Theme
