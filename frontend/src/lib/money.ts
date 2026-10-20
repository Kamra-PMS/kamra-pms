/*  Currency and tax vocabulary, from the property's localization pack. Loaded
    once per session; defaults keep India output identical until it resolves.
    The last resolved locale is kept in localStorage so screens render with
    the right symbol immediately on reload, before the network answers. */

import { useEffect, useState } from "react"
import { call, getCurrentProperty } from "./api"

interface Locale {
  currency_symbol: string
  locale: string
  currency: string
  tax_label: string
  tax_id_label: string
  tax_rates: number[]
  /** ID documents this country's desk records (pack ID_TYPES). */
  id_types: string[]
  /** Ways to pay the desk offers - always canonical Folio Payment modes. */
  payment_modes: string[]
  default_nationality: string
  /** Under this age an occupant is a minor: name and age only. */
  adult_age: number
  /** "foreign": a minor's ID is kept only for foreign nationals;
   *  "all": the country's register covers every guest. */
  minor_ids: "foreign" | "all"
  /** Country integrations this property has - India: Razorpay/Cashfree,
   *  GSTR-1, Kamra Verify. Off until the pack resolves. */
  integrations: Integrations
  /** The rate the server puts on any food & beverage charge, whatever the
   *  caller picked, and the words that make a charge F&B. */
  fnb_tax_rate?: number
  fnb_charge_words?: string[]
}

export interface Integrations {
  payment_gateways: string[]
  tax_return: boolean
  verify_tax_id: boolean
  verify_guest_id: boolean
}

let cache: Locale = {
  currency_symbol: "₹",
  locale: "en-IN",
  currency: "INR",
  tax_label: "GST",
  tax_id_label: "GSTIN",
  tax_rates: [0, 5, 12, 18, 28],
  id_types: ["Aadhaar", "Passport", "Driving License", "Voter ID", "PAN", "Other"],
  payment_modes: ["Cash", "Card", "UPI", "Bank Transfer"],
  default_nationality: "Indian",
  adult_age: 18,
  minor_ids: "foreign",
  integrations: {
    payment_gateways: [],
    tax_return: false,
    verify_tax_id: false,
    verify_guest_id: false,
  },
}

const listeners = new Set<() => void>()

try {
  const saved = JSON.parse(localStorage.getItem("kamra_locale") || "")
  if (saved && saved.currency_symbol) cache = { ...cache, ...saved }
} catch {
  /* first run - Indian defaults until the pack resolves */
}

function remember() {
  listeners.forEach((fn) => fn())
  try {
    localStorage.setItem("kamra_locale", JSON.stringify(cache))
  } catch {
    /* private mode */
  }
}

export function loadLocale(): Promise<Locale> {
  return call<Locale>("kamra.api.property_locale", {
    property: getCurrentProperty(),
  })
    .then((l) => {
      cache = { ...cache, ...l }
      remember()
      return cache
    })
    .catch(() => cache)
}

/** Public pages carry `ui_locale` in their payload - adopt it directly. */
export function adoptUiLocale(ui?: { currency_symbol?: string; locale?: string } | null) {
  if (!ui) return
  cache = {
    ...cache,
    // "" is a valid symbol (generic pack shows bare numbers)
    currency_symbol: ui.currency_symbol ?? cache.currency_symbol,
    locale: ui.locale || cache.locale,
  }
  remember()
}

export const locale = () => cache
/** The property's currency symbol, e.g. "₹" or "Rp". */
export const cur = () => cache.currency_symbol
/** The number-formatting locale, e.g. "en-IN" (lakhs) or "id-ID". */
export const moneyLocale = () => cache.locale
export const fmtMoney = (n: unknown) =>
  cache.currency_symbol +
  Number(n ?? 0).toLocaleString(cache.locale, { maximumFractionDigits: 2 })
export const taxRates = () => cache.tax_rates
export const taxLabel = () => cache.tax_label

/** The property's locale, re-rendering when the country pack resolves. */
export function useLocale(): Locale {
  const [l, setL] = useState(cache)
  useEffect(() => {
    const fn = () => setL(cache)
    listeners.add(fn)
    loadLocale()
    return () => {
      listeners.delete(fn)
    }
  }, [])
  return l
}
