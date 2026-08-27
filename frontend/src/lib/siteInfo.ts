import { call } from "./api"

export type SiteInfo = {
  demo_mode: boolean
  version?: string
  app?: string
  site?: string
  branch?: string | null
  commit?: string | null
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
