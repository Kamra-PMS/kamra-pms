export interface FloorOrder {
  name: string
  sort_order: number
}

const num = (s: string) => {
  const m = s.match(/-?\d+/)
  return m ? parseInt(m[0], 10) : null
}

/** Floor names in the Floor master's order; floors the master does not list
 *  (or an old payload without `floors`) follow in natural order. */
export function sortFloors(names: string[], master: FloorOrder[] = []): string[] {
  const rank = new Map(master.map((f, i) => [f.name, i]))
  const natural = (a: string, b: string) => {
    const x = num(a), y = num(b)
    if (x !== null && y !== null && x !== y) return x - y
    if ((x === null) !== (y === null)) return x === null ? 1 : -1
    return a.localeCompare(b, undefined, { numeric: true })
  }
  return [...names].sort((a, b) => {
    const ra = rank.get(a), rb = rank.get(b)
    if (ra !== undefined && rb !== undefined) return ra - rb
    if (ra !== undefined) return -1
    if (rb !== undefined) return 1
    return natural(a, b)
  })
}
