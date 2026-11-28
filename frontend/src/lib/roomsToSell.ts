/** What the booking screens show for each room type, from
 * kamra.api.rooms_to_sell: the rules a save applies, so a type sold to stays
 * with no room number does not look free. */
export interface RoomSale {
  /** stays that can still be sold, each with a room */
  free: number
  /** no room to give, but a booking without a room number is still accepted */
  without_room: boolean
}

export type RoomSales = Record<string, RoomSale>

export type SaleState = "left" | "without_room" | "sold_out"

/** null while unknown: loading, a failed call, or a type the answer leaves out. */
export function saleState(sale?: RoomSale): SaleState | null {
  if (!sale) return null
  if (sale.free > 0) return "left"
  return sale.without_room ? "without_room" : "sold_out"
}

/** The rooms to offer a walk-in: none for a type with nothing left to sell. */
export function sellableRooms<T>(rooms: T[], sale?: RoomSale): T[] {
  return sale && sale.free <= 0 ? [] : rooms
}

export function freeCounts(sales: RoomSales): Record<string, number> {
  return Object.fromEntries(
    Object.entries(sales).map(([roomType, sale]) => [roomType, sale.free]),
  )
}
