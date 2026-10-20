import { call } from "./api"

export type SiteInfo = {
  demo_mode: boolean
  version?: string
  app?: string
  site?: string
  channel?: string | null
  build?: string | null
  frappe_version?: string
}

let cached: Promise<SiteInfo> | null = null

export function getSiteInfo(): Promise<SiteInfo> {
  if (!cached) {
    cached = call<SiteInfo>("kamra.public_api.site_info").catch(() => ({
      demo_mode: false,
    }))
  }
  return cached
}

/** "2.6.17", "2.6.17 · nightly", "2.6.17 · nightly · 8f32098" */
export function versionLabel(info: SiteInfo | null): string | null {
  if (!info?.version) return null
  return [info.version, info.channel, info.build].filter(Boolean).join(" · ")
}
