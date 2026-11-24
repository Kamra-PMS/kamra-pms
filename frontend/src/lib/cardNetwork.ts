/** Which card network a card payment came from, picked from the card machine slip. */

export const CARD_NETWORKS = [
  "Visa", "Mastercard", "RuPay", "American Express", "Diners Club", "Discover",
  "JCB", "UnionPay", "Maestro", "Mir", "Elo", "Other",
] as const
export type CardNetwork = (typeof CARD_NETWORKS)[number]

/** The payment mode that means a card. UPI and the rest are not split by network. */
export const isCard = (mode: string) => /^card$/i.test(mode.trim())

/** Why the card details cannot be accepted, or "" when they can. The last 4 digits are optional. */
export function cardProblem(mode: string, network?: string, last4?: string): string {
  if (!isCard(mode)) return ""
  if (!network) return "Choose the card type for the Card payment."
  const l = (last4 ?? "").trim()
  if (l && !/^\d{4}$/.test(l)) return "Give exactly the last 4 digits of the card, or leave them empty."
  return ""
}

/** The extra arguments to send with a card payment; nothing for any other mode. */
export function cardArgs(mode: string, network?: string, last4?: string): { card_network?: string; card_last4?: string } {
  if (!isCard(mode) || !network) return {}
  const l = (last4 ?? "").trim()
  return l ? { card_network: network, card_last4: l } : { card_network: network }
}
