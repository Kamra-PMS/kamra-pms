/** Pick the booking dialog's default room type (#549).
 *
 * `roomTypes` must already be cheapest-first (then name). Prefer the first
 * type that has at least one free room for the selected dates; if none do,
 * fall back to the first configured type so the form still has a value.
 */
export function pickDefaultRoomType(
  roomTypes: { name: string }[],
  availableCount: Record<string, number>,
): string {
  if (!roomTypes.length) return ""
  const withRooms = roomTypes.find((rt) => (availableCount[rt.name] ?? 0) > 0)
  return withRooms?.name ?? roomTypes[0].name
}
