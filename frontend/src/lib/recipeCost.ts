/* Recipe cost and margin per portion: the same rule as kamra/inventory.py. */

import { moneyDigits, moneyLocale } from "./money"

export interface CostIngredient { name: string; ingredient_name: string; cost_per_unit: number | null }

/** Money to at least the currency's decimals, and 2 where the figure needs them. */
export function fmtCost(n: number): string {
  const digits = moneyDigits()
  return Number(n).toLocaleString(moneyLocale(), {
    minimumFractionDigits: digits, maximumFractionDigits: Math.max(digits, 2),
  })
}

const six = (n: number) => Math.round(n * 1e6) / 1e6

/** What one portion costs and what is left of the price. `lines` answers the
 *  recipe line by line; a line still being typed counts for nothing. With any
 *  ingredient that has no cost yet there is no total: a part total would read
 *  as a fine margin. `missing` names those ingredients. */
export function recipeTotals(
  lines: { ingredient: string; qty: number | string }[],
  ingredients: CostIngredient[],
  price: number,
) {
  const missing: string[] = []
  let sum = 0
  let counted = 0
  const per = lines.map((l) => {
    const qty = Number(l.qty)
    if (!l.ingredient || !(qty > 0)) return null
    counted += 1
    const ing = ingredients.find((i) => i.name === l.ingredient)
    const cost = Number(ing?.cost_per_unit ?? 0)
    if (!(cost > 0)) {
      const name = ing?.ingredient_name ?? l.ingredient
      if (!missing.includes(name)) missing.push(name)
      return null
    }
    sum += qty * cost
    return six(qty * cost)
  })
  const cost = counted && !missing.length ? six(sum) : null
  const margin = cost === null ? null : six(price - cost)
  const pct = margin === null || !(price > 0) ? null : (margin / price) * 100
  return { lines: per, cost, margin, pct, missing }
}
