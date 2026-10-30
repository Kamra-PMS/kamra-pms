/*  Currency and tax vocabulary, from the property's localization pack. Loaded
    once per session; neutral defaults (no symbol, plain "Tax") until it resolves.
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
  /** A help line per ID type, e.g. which copy of a national ID is fine. */
  id_type_hints: Record<string, string>
  /** Ways to pay the desk offers - always canonical Folio Payment modes. */
  payment_modes: string[]
  /** The pack's own instant / wallet modes; the till keeps
   *  them in their own bucket (system_upi). Empty where there are none. */
  instant_payment_modes: string[]
  /** What an outlet bill settles with: Cash, Card and the instant modes. */
  outlet_payment_modes: string[]
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
  currency_symbol: "",
  locale: "en",
  currency: "",
  tax_label: "Tax",
  tax_id_label: "Tax ID",
  tax_rates: [],
  id_types: [],
  payment_modes: [],
  instant_payment_modes: [],
  outlet_payment_modes: [],
  id_type_hints: {},
  default_nationality: "",
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
  if (saved && saved.currency) cache = { ...cache, ...saved }
} catch {
  /* first run - neutral defaults until the pack resolves */
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
export function adoptUiLocale(ui?: { currency_symbol?: string; locale?: string; currency?: string } | null) {
  if (!ui) return
  cache = {
    ...cache,
    // "" is a valid symbol (generic pack shows bare numbers)
    currency_symbol: ui.currency_symbol ?? cache.currency_symbol,
    locale: ui.locale || cache.locale,
    currency: ui.currency || cache.currency,
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
/** Heading for the till's instant-mode bucket, "" where the country has none. */
export const instantLabel = () => (cache.instant_payment_modes ?? []).join(" / ")

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
