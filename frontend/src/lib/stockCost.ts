/* Kitchen stock money: what a unit of an ingredient costs. */

import { moneyDigits, moneyLocale } from "./money"

/** A cost per unit with the currency's decimals, and up to 4 when the figure
 *  needs them: 18.5714 a gram must not read as 19. */
export function fmtUnitCost(n: unknown, currency?: string | null): string {
  const digits = moneyDigits(currency || undefined)
  return Number(n ?? 0).toLocaleString(moneyLocale(), {
    minimumFractionDigits: digits, maximumFractionDigits: Math.max(digits, 4),
  })
}

/** One row of the Receive window, as typed. */
export interface ReceiveEntry { qty: string; unit: "buy" | "stock"; size: string; price: string }

export interface StockUnits {
  ingredient: string
  uom: string
  buy_uom?: string | null
  buy_size?: number | null
  cost_per_unit?: number | null
}

/** A fresh row: bought by the box where the ingredient has a buying unit. */
export function defaultEntry(i: StockUnits): ReceiveEntry {
  const buy = !!i.buy_uom && Number(i.buy_size) > 0
  return { qty: "", unit: buy ? "buy" : "stock", size: buy ? String(i.buy_size) : "", price: "" }
}

/** What a row puts into stock and costs, per stock unit and in all. Null until
 *  the quantity (and the pack size, when buying by the pack) is above zero. */
export function receiveLine(_i: StockUnits, e: ReceiveEntry) {
  const qty = Number(e.qty)
  const size = e.unit === "buy" ? Number(e.size) : 1
  if (!(qty > 0) || !(size > 0)) return null
  const price = e.price.trim() === "" ? null : Number(e.price)
  return {
    stockQty: qty * size,
    perUnit: price === null ? null : price / size,
    total: price === null ? null : price * qty,
  }
}

/** The row receive_stock takes: quantity and price in the unit chosen. An
 *  empty price is left out; 0 means free goods. */
export function receiveRow(i: StockUnits, e: ReceiveEntry): Record<string, unknown> | null {
  if (!receiveLine(i, e)) return null
  return {
    ingredient: i.ingredient,
    uom: i.uom,
    qty: Number(e.qty),
    ...(e.unit === "buy"
      ? { in_buying_unit: 1, buy_uom: i.buy_uom, buy_size: Number(e.size) }
      : {}),
    ...(e.price.trim() === "" ? {} : { cost_per_unit: Number(e.price) }),
  }
}
