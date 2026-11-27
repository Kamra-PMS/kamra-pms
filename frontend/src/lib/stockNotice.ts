/* The till's word about an item with its own stock and nothing left. */

/** What to say when such an item is added; null while there is some left, or
 *  for an item without its own stock. The sale goes ahead either way. */
export function stockNotice(item: { item_name: string; stock_left?: number | null }) {
  const left = item.stock_left
  if (left === undefined || left === null || left > 0) return null
  return { name: item.item_name, qty: String(Math.round(left * 1000) / 1000) }
}
