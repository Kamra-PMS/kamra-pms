import { call, getCurrentProperty } from "../../lib/api"

/** Shapes returned by kamra.settings / kamra.staff - the settings hub's
 *  only backend. Every write goes through a role-checked endpoint. */

export type SettingType =
  | "text" | "number" | "time" | "check" | "select" | "textarea" | "image" | "email"

export interface SettingSpec {
  key: string
  label: string
  type: SettingType
  default: unknown
  hint: string
  store: "property" | "kv" | "turnover"
  options?: string[]
  options_source?: "countries" | "timezones"
  min?: number
  max?: number
  unit?: string
}

export interface SettingsSection {
  id: string
  title: string
  description: string
  settings: SettingSpec[]
}

export interface SettingsModule {
  id: string
  title: string
  description: string
  group: "organisation" | "modules"
  toggle: boolean
  enabled: boolean
  editors: string[]
  can_edit: boolean
  related: { label: string; to: string }[]
  sections: SettingsSection[]
  values: Record<string, unknown>
}

export interface SettingsSchema {
  modules: SettingsModule[]
  enabled_modules: string[]
  is_admin: boolean
  is_it_admin: boolean
}

export const settingsSchema = () =>
  call<SettingsSchema>("kamra.settings.settings_schema", {
    property: getCurrentProperty(),
  })

export const saveSettings = (module: string, changes: Record<string, unknown>) =>
  call<{ ok: boolean; values: Record<string, unknown>; changed?: string[] }>(
    "kamra.settings.save_settings",
    { property: getCurrentProperty(), module, changes },
  )

export const setModuleEnabled = (module: string, enabled: boolean) =>
  call<{ ok: boolean; modules: string[] }>("kamra.settings.set_module_enabled", {
    property: getCurrentProperty(),
    module,
    enabled: enabled ? 1 : 0,
  })

// --- staff & access ----------------------------------------------------------

export interface RoleInfo {
  role: string
  label: string
  description: string
  assignable: boolean
}

export interface StaffRow {
  user: string
  full_name: string
  email: string
  enabled: number | boolean
  roles: string[]
  /** null = every property */
  properties: string[] | null
  last_login: string | null
  last_active: string | null
  pin: "set" | "none" | "reset"
  is_self: boolean
  editable: boolean
  job_title?: string
  user_image?: string | null
}

export interface StaffInput {
  email: string
  full_name: string
  job_title: string
  roles: string[]
  properties: string[] | null
  enabled: boolean
  send_welcome: boolean
}

export const staffRoles = () => call<RoleInfo[]>("kamra.staff.staff_roles")

export const listStaff = () =>
  call<StaffRow[]>("kamra.staff.list_staff", { property: getCurrentProperty() })

export const saveStaff = (s: StaffInput) =>
  call("kamra.staff.save_staff", {
    property: getCurrentProperty(),
    email: s.email,
    full_name: s.full_name,
    job_title: s.job_title,
    roles: s.roles,
    properties: s.properties ?? "all",
    enabled: s.enabled ? 1 : 0,
    send_welcome: s.send_welcome ? 1 : 0,
  })

export const resetCashierPin = (user: string) =>
  call("kamra.api.reset_cashier_pin", { user })
