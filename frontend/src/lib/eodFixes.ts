/** How to clear each End of Day (night audit) check. Shown under a check
 *  that has something to fix: the usual ways to fix it, a hand-off to the
 *  Kamra Agent, and what overriding it means. The override itself is the
 *  existing acknowledge-with-a-reason; this only says what it implies. */

export interface FixStep {
  text: string
  /** an app route to do it in */
  to?: string
  cta?: string
}

export interface CheckFix {
  /** why the audit cares */
  why: string
  steps: FixStep[]
  /** what overriding with a reason lets through */
  override: string
  /** what to ask the Kamra Agent, given the check's count */
  ask: (count: number, date: string) => string
}

export const CHECK_FIXES: Record<string, CheckFix> = {
  arrivals_pending: {
    why: "Guests due today who never checked in. Tonight's audit applies your no-show policy to them.",
    steps: [
      { text: "If the guest has arrived, check them in.", cta: "Check in" },
      { text: "If they have not and are not coming, mark them no-show (the policy fee applies as shown)." },
      { text: "If they are arriving late tonight, leave them: late arrivals are protected by the policy." },
    ],
    override: "The audit continues and the no-show policy applies to whoever is still listed.",
    ask: (n, d) => `${n} arrivals for ${d} are not checked in. List them and tell me which look like no-shows versus late arrivals. Do not change anything yet.`,
  },
  departures_due: {
    why: "Stays past their departure date. The audit does not post a night for a stay past its departure.",
    steps: [
      { text: "Zero balance: use Quick check out above, or Check out on the row." },
      { text: "Balance due: collect it from the row's Check out, or move the balance to a company or city ledger." },
      { text: "Staying on: use Extend stay so the stay covers tonight.", to: "/reservations", cta: "Open reservations" },
    ],
    override: "The stay is left in house past its departure and tonight is not charged for it. Use only if someone will fix it first thing.",
    ask: (n, d) => `${n} departures for ${d} are still in house. Check out the ones with a zero balance and list the rest with what each owes.`,
  },
  open_pos_bills: {
    why: "Restaurant, bar and room-service bills that are still open. Closing the day with them open loses or misdates the revenue.",
    steps: [
      { text: "Settle each bill in the POS (cash, card, UPI), or charge it to the guest's room.", to: "/pos", cta: "Open POS" },
      { text: "Bill for a guest who left or a mistake: cancel it, or mark it complimentary (NC) with who authorised it." },
      { text: "Still being served overnight (a late bar): leave it and override with a reason." },
    ],
    override: "The bill stays open into the next business date. Its sale is dated tomorrow, not today.",
    ask: (n, d) => `${n} restaurant bills are open for ${d}. Show each one with its table or room and total, and say which ones I can safely settle or charge to a room.`,
  },
  open_tills: {
    why: "A till that is still open has money in it nobody has counted. Every till should be counted and closed for the business date.",
    steps: [
      { text: "Count the drawer and close the session on its row below (it asks for the counted cash)." },
      { text: "The cashier has gone home: a manager counts the drawer with the envelope and closes it." },
      { text: "See every till and who holds it.", to: "/cashier/board", cta: "All tills" },
    ],
    override: "The till stays open and rolls into tomorrow with its float and takings. Variance is not recorded for tonight.",
    ask: (n, d) => `${n} cashier tills are still open for ${d}. Tell me who holds each, what it should contain, and who to chase to count and close it.`,
  },
  rate_variance: {
    why: "Room nights posted at a different rate from the one booked.",
    steps: [
      { text: "Open the folio and check why: a manual rate change is fine if intended.", cta: "Open folio" },
      { text: "A wrong rate: correct the night on the folio before the audit posts." },
    ],
    override: "The audit posts as it stands.",
    ask: (n, d) => `${n} room nights for ${d} differ from the booked rate. List them with the reason, manual or not.`,
  },
  pos_room_postings: {
    why: "Outlet bills charged to rooms. A bill for the wrong room means the wrong guest pays.",
    steps: [
      { text: "Check each row marked 'Wrong room?' against the guest's room.", to: "/pos", cta: "Open POS" },
      { text: "If wrong, move the charge to the right folio." },
    ],
    override: "The bills stay where they are posted.",
    ask: (n, d) => `${n} outlet bills for ${d} were charged to rooms. Flag any where the bill's room differs from the folio it posted to.`,
  },
  high_balance: {
    why: "In-house guests whose balance is above the alert threshold.",
    steps: [{ text: "Ask the guest for a payment on account, or confirm a company will pay.", to: "/billing", cta: "Open billing" }],
    override: "Nothing is blocked. It is only flagged.",
    ask: (n, d) => `${n} in-house folios are over the balance threshold on ${d}. List them with what each owes and any deposit held.`,
  },
  departed_balances: {
    why: "Guests who left with an unpaid balance.",
    steps: [{ text: "Collect it, move it to a company or city ledger account, or write it off with approval.", to: "/billing", cta: "Open billing" }],
    override: "The balance stays on the departed folio.",
    ask: (n, d) => `${n} departed stays still have a balance on ${d}. List them with the amount and whether a company can be billed.`,
  },
  credit_limit: {
    why: "Companies whose open bills plus in-house stays exceed their credit limit.",
    steps: [{ text: "Ask the company to pay or raise the limit.", to: "/ledgers", cta: "Open ledgers" }],
    override: "Nothing is blocked. It is only flagged.",
    ask: (n, d) => `${n} companies are over their credit limit on ${d}. Show each exposure and what is overdue.`,
  },
  overdue_ar: {
    why: "Companies with bills past their credit terms.",
    steps: [{ text: "Send a reminder or log a payment promise.", to: "/ledgers", cta: "Open ledgers" }],
    override: "Nothing is blocked. It is only flagged.",
    ask: (n, d) => `${n} companies have overdue bills on ${d}. Summarise the overdue amount and age for each.`,
  },
  room_status: {
    why: "The front office and the room board disagree, for example a room occupied in one and vacant in the other.",
    steps: [
      { text: "Fix whichever side is wrong: check the guest in or out, or update the room's status.", to: "/rooms", cta: "Open rooms" },
    ],
    override: "The mismatch stays and may show up as a wrong room status tomorrow.",
    ask: (n, d) => `${n} rooms have a status mismatch on ${d}. For each say which side looks wrong.`,
  },
  zero_rate: {
    why: "Rooms in house at a zero rate, usually complimentary or an entry error.",
    steps: [{ text: "Confirm it is complimentary on purpose; otherwise correct the rate.", to: "/reservations", cta: "Open reservations" }],
    override: "Nothing is blocked. It is only flagged.",
    ask: (n, d) => `${n} rooms are at zero rate on ${d}. List them and whether each is a booked complimentary.`,
  },
}
