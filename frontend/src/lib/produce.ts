/* What a batch of something made here takes off the shelf: the same rule as
   kamra/inventory.py (produce). */

export interface BatchLine { ingredient: string; qty: number | string }

/** Per ingredient, recipe quantity x made / batch size, to 3 decimals. Empty
 *  until there is something to take. */
export function batchUse(
  recipe: BatchLine[], batch: number, made: number,
): { ingredient: string; qty: number }[] {
  if (!(batch > 0) || !(made > 0)) return []
  const per = new Map<string, number>()
  for (const line of recipe) {
    const qty = Number(line.qty)
    if (line.ingredient && qty > 0) per.set(line.ingredient, (per.get(line.ingredient) ?? 0) + qty)
  }
  return [...per]
    .map(([ingredient, qty]) => ({ ingredient, qty: Math.round((qty * made / batch) * 1000) / 1000 }))
    .filter((use) => use.qty > 0)
}
