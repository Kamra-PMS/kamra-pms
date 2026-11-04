/** Kamra Agent's guided desk tasks. A tap on "Check in" asks who, lists
 *  today's arrivals to tap, and so on step by step, so nobody has to know
 *  what to type. Lists come straight from the desk's own endpoints; the
 *  AI is only handed a finished, plain request at the end (or the normal
 *  booking form is opened, filled in). */
import type { LucideIcon } from "lucide-react"
import {
  BedDouble,
  CalendarClock,
  CalendarPlus,
  ConciergeBell,
  LogIn,
  LogOut,
  Moon,
  Receipt,
  Search,
  Sparkles,
  UserPlus,
  UtensilsCrossed,
  Wallet,
  XCircle,
} from "lucide-react"

import type { BookingOptions, ReservationRow, Snapshot } from "../lib/api"
import { t as translate } from "../lib/i18n"
import { cur, moneyLocale } from "../lib/money"
import type { BookingInitial } from "../AppShell"
import type { AgentCard } from "./AgentCards"

export type FlowId =
  | "checkin"
  | "checkout"
  | "walkin"
  | "booking"
  | "find"
  | "cancel"
  | "charge"
  | "payment"
  | "change"
  | "request"
  | "today"
  | "housekeeping"
  | "audit"
  | "order"

/** A food order the guide sends to the kitchen itself (kamra.pos.send_order),
 *  the same call the POS till makes - no AI involved. */
export interface OrderRequest {
  outlet: string
  items: { menu_item: string; qty: number }[]
  order_type: "Room Service" | "Dine In" | "Takeaway"
  reservation?: string
  table_no?: string
}

/** One tappable answer. Exactly one of value / goto / prompt / book / order
 *  acts: value answers the step being asked, goto starts a task ("menu"
 *  lists them), prompt goes to the AI as typed, book opens the booking
 *  form, order sends a food order to the kitchen. */
export interface Choice {
  label: string
  hint?: string
  value?: string
  goto?: FlowId | "menu"
  prompt?: string
  book?: BookingInitial
  order?: OrderRequest
}

export interface Answer {
  label: string
  value: string
  /** typed rather than picked from the list */
  typed?: boolean
}
export type Answers = Record<string, Answer>

export interface GuideOutlet {
  name: string
  outlet_name: string
  outlet_type?: string
}
export interface GuideMenu {
  categories: {
    category: string
    items: { name: string; item_name: string; price: number }[]
  }[]
}

export interface GuideData {
  snapshot: () => Promise<Snapshot>
  options: () => Promise<BookingOptions>
  outlets: () => Promise<GuideOutlet[]>
  menu: (outlet: string) => Promise<GuideMenu>
}

interface Step {
  key: string
  /** placeholder for a typed answer; no placeholder = tap only */
  text?: string
  /** not asked at all when this says so (e.g. a table number for room service) */
  skip?: (a: Answers) => boolean
  /** a basket: each answer is folded into the last one and the same question
   *  is asked again; null moves on with what was gathered */
  collect?: (prev: Answer | undefined, picked: Answer) => Answer | null
  /** auto: the only possible answer, taken without asking */
  load: (a: Answers, d: GuideData) => Promise<{ ask: string; choices: Choice[]; auto?: Answer }>
}

export type Outcome =
  | { prompt: string }
  | { say: string; cards?: AgentCard[]; choices?: Choice[] }

interface Flow {
  steps: Step[]
  finish: (a: Answers, ai: boolean) => Outcome
}

export interface Tile {
  id: FlowId
  label: string
  hint: string
  icon: LucideIcon
}

/** Everything the agent can walk someone through, in desk order. */
export function menuTiles(): Tile[] {
  return [
    { id: "walkin", icon: UserPlus, label: translate("Walk-in check-in"),
      hint: translate("A guest is at the desk with no booking") },
    { id: "checkin", icon: LogIn, label: translate("Check in"),
      hint: translate("Someone arriving today") },
    { id: "checkout", icon: LogOut, label: translate("Check out"),
      hint: translate("Settle the bill and free the room") },
    { id: "booking", icon: CalendarPlus, label: translate("New booking"),
      hint: translate("Reserve a room for later") },
    { id: "find", icon: Search, label: translate("Find a booking"),
      hint: translate("By name, room or booking number") },
    { id: "change", icon: CalendarClock, label: translate("Change a stay"),
      hint: translate("Extra night, new dates, another room") },
    { id: "payment", icon: Wallet, label: translate("Take a payment"),
      hint: translate("Cash, UPI, card or bank") },
    { id: "order", icon: UtensilsCrossed, label: translate("Food order"),
      hint: translate("Room service or a table, straight to the kitchen") },
    { id: "charge", icon: Receipt, label: translate("Add a charge"),
      hint: translate("Food, laundry, minibar…") },
    { id: "cancel", icon: XCircle, label: translate("Cancel a booking"),
      hint: translate("Shows the fee before anything happens") },
    { id: "request", icon: ConciergeBell, label: translate("Guest request"),
      hint: translate("Towels, a fault, a complaint") },
    { id: "today", icon: Sparkles, label: translate("Today at a glance"),
      hint: translate("Arrivals, departures, rooms") },
    { id: "housekeeping", icon: BedDouble, label: translate("Housekeeping"),
      hint: translate("Which rooms are ready") },
    { id: "audit", icon: Moon, label: translate("Night audit check"),
      hint: translate("What stops the day closing") },
  ]
}

export const menuChoices = (): Choice[] =>
  menuTiles().map((tl) => ({ label: tl.label, hint: tl.hint, goto: tl.id }))

export const startOver = (): Choice => ({ label: translate("Start over"), goto: "menu" })

const money = (n: number) =>
  `${cur()}${Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })}`

const isoDay = (offset = 0) => {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return d.toLocaleDateString("en-CA")
}

function roomOf(r: ReservationRow, s: Snapshot) {
  const n = s.rooms.find((x) => x.name === r.room)?.room_number
  return n ? translate("Room {n}", { n }) : translate("No room yet")
}

const guestChoice = (r: ReservationRow, hint: string): Choice => ({
  label: r.guest_name,
  hint,
  value: r.name,
})

/** the picked guest as "RES-… (Name)" for a request to the AI */
const who = (a: Answer) => (a.typed ? `"${a.value}"` : `${a.value} (${a.label})`)

const nums = (list: number[]): Choice[] => list.map((n) => ({ label: String(n), value: String(n) }))

const stay = (key: string, ask: string, pick: (s: Snapshot) => Choice[]): Step => ({
  key,
  text: translate("Guest name, room or booking number"),
  load: async (_a, d) => {
    const choices = pick(await d.snapshot())
    return {
      ask: choices.length ? ask : translate("I don't see anyone to list here. Type the guest's name, room or booking number."),
      choices,
    }
  },
})

const inHouse = (s: Snapshot) =>
  s.in_house.map((r) =>
    guestChoice(r, [roomOf(r, s), Number(r.balance_due) > 0
      ? translate("{amount} due", { amount: money(Number(r.balance_due)) })
      : translate("Nothing due")].join(" · ")))

const arriving = (s: Snapshot) =>
  s.arrivals.map((r) =>
    guestChoice(r, [roomOf(r, s), translate("{n} nights", { n: r.nights }), r.name].join(" · ")))

/** the whole booking form at once, for someone who'd rather fill it in one go */
const oneForm = (walkIn: boolean): Choice => ({
  label: translate("Fill it all in one form"),
  hint: translate("Every detail on one screen"),
  book: { walkIn },
})

// the questions a new stay needs, shared by walk-in and booking
const stayQuestions = (walkIn: boolean): Step[] => [
  {
    key: "adults",
    text: translate("Number of adults"),
    load: async () => ({
      ask: translate("How many adults?"),
      // walk-ins are asked this first, so the one-form way out goes here
      choices: walkIn ? [...nums([1, 2, 3, 4]), oneForm(true)] : nums([1, 2, 3, 4]),
    }),
  },
  {
    key: "nights",
    text: translate("Number of nights"),
    load: async () => ({ ask: translate("How many nights?"), choices: nums([1, 2, 3, 4, 5, 7]) }),
  },
  {
    key: "room_type",
    load: async (a, d) => {
      const [opts, snap] = await Promise.all([d.options(), d.snapshot()])
      const adults = Number(a.adults?.value) || 1
      const fit = opts.room_types.filter((rt) => !rt.adults_capacity || rt.adults_capacity >= adults)
      const choices = (fit.length ? fit : opts.room_types).map((rt) => {
        const free = snap.rooms.filter(
          (r) => r.room_type === rt.name && r.occupancy_status === "Vacant").length
        return {
          label: rt.room_type_name,
          hint: [translate("{n} free now", { n: free }),
                 translate("from {amount}", { amount: money(rt.base_price) })].join(" · "),
          value: rt.name,
        }
      })
      return { ask: translate("Which room type?"), choices }
    },
  },
  {
    key: "guest",
    text: translate("Guest's full name"),
    load: async () => ({ ask: translate("What is the guest's name?"), choices: [] }),
  },
  {
    key: "phone",
    text: translate("Phone number"),
    load: async () => ({
      ask: translate("Their phone number? You can skip it."),
      choices: [{ label: translate("Skip"), value: "" }],
    }),
  },
]

function newStay(a: Answers, ai: boolean, walkIn: boolean): Outcome {
  const date = a.date?.value ?? isoDay()
  const when = walkIn ? translate("from today") : a.date?.label ?? date
  const summary = [
    a.guest.value,
    a.phone?.value || null,
    translate("{n} adults", { n: a.adults.value }),
    translate("{n} nights", { n: a.nights.value }),
    a.room_type.label,
    when,
  ].filter(Boolean).join(" · ")
  const facts = translate(
    "Name: {name}. Phone: {phone}. {adults} adults. Room type: {room}. Arriving {date} for {nights} nights.",
    { name: a.guest.value, phone: a.phone?.value || translate("none"), adults: a.adults.value,
      room: a.room_type.label, date: walkIn ? translate("today") : date, nights: a.nights.value })
  const form: Choice = {
    label: walkIn ? translate("Open the walk-in form, filled in") : translate("Open the booking form, filled in"),
    book: {
      walkIn,
      room_type: a.room_type.value,
      guest_name: a.guest.value,
      phone: a.phone?.value || undefined,
      ...(/^\d{4}-\d{2}-\d{2}$/.test(date) ? { date } : {}),
    },
  }
  const agent: Choice = walkIn
    ? { label: translate("Book and check in for me"),
        prompt: translate("A walk-in guest is at the desk now. {facts} Quote it and tell me the total. When I say yes, create the booking and check them in.", { facts }) }
    : { label: translate("Book it for me"),
        prompt: translate("New booking. {facts} Quote it and tell me the total. When I say yes, create the booking.", { facts }) }
  return {
    say: translate("Got it: {summary}. How should we do it?", { summary }),
    choices: ai ? [agent, form, startOver()] : [form, startOver()],
  }
}

/** built per call so every label follows the current UI language */
export function flows(): Record<FlowId, Flow> {
  return {
  checkin: {
    steps: [{
      key: "res",
      text: translate("Guest name, room or booking number"),
      load: async (_a, d) => {
        const choices = arriving(await d.snapshot())
        return {
          ask: choices.length
            ? translate("Who is checking in? Tap their name, or type a name, room or booking number.")
            : translate("Nobody else is due to arrive today. Is it a walk-in? Or type the guest's name, room or booking number."),
          choices: [...choices, { label: translate("Walk-in - no booking"), goto: "walkin" }],
        }
      },
    }],
    finish: (a) =>
      a.res.typed
        ? { prompt: translate("Find the booking for {q} that is arriving and show it, so I can check them in.", { q: who(a.res) }) }
        : { say: translate("Here is {name}'s booking. Tap Check in - it takes the ID and any payment, then the room is theirs.", { name: a.res.label }),
            cards: [{ type: "stay", reservation: a.res.value }] },
  },
  checkout: {
    steps: [{
      key: "res",
      text: translate("Guest name, room or booking number"),
      load: async (_a, d) => {
        const s = await d.snapshot()
        const leaving = new Set(s.departures.map((r) => r.name))
        const today = inHouse({ ...s, in_house: s.departures })
          .map((c) => ({ ...c, hint: `${translate("Leaving today")} · ${c.hint}` }))
        const others = inHouse({ ...s, in_house: s.in_house.filter((r) => !leaving.has(r.name)) })
        const choices = [...today, ...others]
        return {
          ask: choices.length
            ? translate("Who is checking out? People leaving today are at the top.")
            : translate("Nobody is in house right now. Type the guest's name, room or booking number."),
          choices,
        }
      },
    }],
    finish: (a) =>
      a.res.typed
        ? { prompt: translate("Find the in-house stay for {q} and show what they owe to check out.", { q: who(a.res) }) }
        : { say: translate("Here is {name}'s stay. Tap Check out - it shows the bill, takes the payment and frees the room.", { name: a.res.label }),
            cards: [{ type: "stay", reservation: a.res.value }] },
  },
  walkin: {
    steps: stayQuestions(true),
    finish: (a, ai) => newStay(a, ai, true),
  },
  booking: {
    steps: [
      {
        key: "date",
        text: translate("Arrival date, e.g. 12 Nov"),
        load: async () => ({
          ask: translate("When do they arrive?"),
          choices: [
            { label: translate("Today"), value: isoDay() },
            { label: translate("Tomorrow"), value: isoDay(1) },
            { label: translate("In 2 days"), value: isoDay(2) },
            oneForm(false),
          ],
        }),
      },
      ...stayQuestions(false),
    ],
    finish: (a, ai) => newStay(a, ai, false),
  },
  find: {
    steps: [{
      key: "q",
      text: translate("Guest name, room or booking number"),
      load: async () => ({ ask: translate("Who are you looking for? Type the guest's name, room number or booking number."), choices: [] }),
    }],
    finish: (a) => ({ prompt: translate("Find the booking for {q} and show it.", { q: who(a.q) }) }),
  },
  cancel: {
    steps: [stay("res", translate("Whose booking is it? Today's arrivals are below, or type a name or booking number."), arriving)],
    finish: (a) => ({ prompt: translate("Tell me what cancelling the booking for {q} would cost. Don't cancel until I say yes.", { q: who(a.res) }) }),
  },
  charge: {
    steps: [
      stay("res", translate("Which guest is the charge for?"), inHouse),
      {
        key: "what",
        text: translate("What is it for?"),
        load: async () => ({
          ask: translate("What is the charge for?"),
          choices: [translate("Food & drinks"), translate("Room service"), translate("Laundry"),
                    translate("Minibar"), translate("Spa")].map((x) => ({ label: x, value: x })),
        }),
      },
      {
        key: "amount",
        text: translate("Amount"),
        load: async () => ({ ask: translate("How much?"), choices: [] }),
      },
    ],
    finish: (a) => ({
      prompt: translate("Post a charge to {q}: {what}, {amount}.", { q: who(a.res), what: a.what.value, amount: a.amount.value }),
    }),
  },
  payment: {
    steps: [
      stay("res", translate("Who is paying?"), inHouse),
      {
        key: "amount",
        text: translate("Amount"),
        load: async (a, d) => {
          const row = (await d.snapshot()).in_house.find((r) => r.name === a.res.value)
          const due = Number(row?.balance_due) || 0
          return {
            ask: translate("How much did they pay?"),
            choices: due > 0
              ? [{ label: translate("All of it ({amount})", { amount: money(due) }), value: String(due) }]
              : [],
          }
        },
      },
      {
        key: "mode",
        load: async () => ({
          ask: translate("How did they pay?"),
          choices: ["Cash", "UPI", "Card", "Bank"].map((m) => ({ label: translate(m), value: m })),
        }),
      },
    ],
    finish: (a) => ({
      prompt: translate("{q} paid {amount} by {mode}. Record it on their bill.", { q: who(a.res), amount: a.amount.value, mode: a.mode.value }),
    }),
  },
  change: {
    steps: [
      stay("res", translate("Whose stay is changing?"), (s) => [...inHouse(s), ...arriving(s)]),
      {
        key: "what",
        load: async () => ({
          ask: translate("What do you want to change?"),
          choices: [
            { label: translate("Add one night"), value: "extend" },
            { label: translate("Different dates"), value: "dates" },
            { label: translate("Another room"), value: "move" },
            { label: translate("Arriving late"), value: "late" },
          ],
        }),
      },
    ],
    finish: (a) => {
      const q = who(a.res)
      const prompts: Record<string, string> = {
        extend: translate("Add one night to the stay of {q}. Show me the new price first.", { q }),
        dates: translate("Change the dates of the stay of {q}. Ask me the new dates, then show the new price.", { q }),
        move: translate("Move {q} to another room. Show me the free rooms first.", { q }),
        late: translate("{q} is arriving late. Flag it so it is not marked a no-show, and ask me the arrival time.", { q }),
      }
      return { prompt: prompts[a.what.value] ?? translate("Change the stay of {q}: {what}", { q, what: a.what.value }) }
    },
  },
  request: {
    steps: [
      stay("res", translate("Which guest is asking?"), inHouse),
      {
        key: "what",
        text: translate("What do they need?"),
        load: async () => ({
          ask: translate("What do they need? Tap one or type it."),
          choices: [translate("Extra towels"), translate("Room cleaning"), translate("Something is broken"),
                    translate("Complaint")].map((x) => ({ label: x, value: x })),
        }),
      },
    ],
    finish: (a) => ({ prompt: translate("Raise a ticket for {q}: {what}.", { q: who(a.res), what: a.what.value }) }),
  },
  today: {
    steps: [],
    finish: () => ({ prompt: translate("What does today look like - arrivals, departures, occupancy?") }),
  },
  housekeeping: {
    steps: [],
    finish: () => ({ prompt: translate("Which rooms are ready, which are dirty, and what housekeeping tasks are open?") }),
  },
  audit: {
    steps: [],
    finish: () => ({ prompt: translate("Run the night audit precheck and tell me what blocks it.") }),
  },
  order: {
    steps: [
      {
        key: "outlet",
        load: async (_a, d) => {
          const list = await d.outlets()
          if (list.length === 1)
            return { ask: "", choices: [], auto: { label: list[0].outlet_name, value: list[0].name } }
          return {
            ask: list.length
              ? translate("Which kitchen is it for?")
              : translate("No restaurant or room service is set up yet. Add one in F&B first."),
            choices: list.map((o) => ({ label: o.outlet_name, hint: o.outlet_type, value: o.name })),
          }
        },
      },
      {
        key: "to",
        load: async (_a, d) => {
          const s = await d.snapshot()
          return {
            ask: translate("Who is it for? Tap a guest in a room, or a table or takeaway."),
            choices: [
              ...s.in_house.map((r) => ({ label: r.guest_name, hint: roomOf(r, s), value: `res:${r.name}` })),
              { label: translate("A restaurant table"), value: "table" },
              { label: translate("Takeaway"), value: "takeaway" },
            ],
          }
        },
      },
      {
        key: "table",
        text: translate("Table number, e.g. T4"),
        skip: (a) => a.to?.value !== "table",
        load: async () => ({ ask: translate("Which table?"), choices: [] }),
      },
      {
        key: "items",
        collect: (prev, picked) => {
          if (picked.value === DONE) return null
          const cart = picked.value === CLEAR ? [] : readCart(prev)
          if (picked.value !== CLEAR) {
            const it = JSON.parse(picked.value) as Omit<CartLine, "qty">
            const line = cart.find((l) => l.item === it.item)
            if (line) line.qty += 1
            else cart.push({ ...it, qty: 1 })
          }
          return { label: cartText(cart), value: JSON.stringify(cart) }
        },
        load: async (a, d) => {
          const menu = await d.menu(a.outlet.value)
          const cart = readCart(a.items)
          const dishes: Choice[] = menu.categories.flatMap((c) =>
            c.items.map((it) => ({
              label: it.item_name,
              hint: `${c.category} · ${money(it.price)}`,
              value: JSON.stringify({ item: it.name, name: it.item_name, price: Number(it.price) || 0 }),
            })))
          if (!dishes.length)
            return { ask: translate("This kitchen has no dishes on its menu yet."), choices: [] }
          if (!cart.length)
            return { ask: translate("What would they like? Tap a dish. Tap it again for one more."), choices: dishes }
          return {
            ask: translate("In the order: {items} - {total}. Tap more, or Done.",
              { items: cartText(cart), total: money(cartTotal(cart)) }),
            choices: [
              { label: translate("Done"), hint: translate("Check the order"), value: DONE },
              ...dishes,
              { label: translate("Clear the order"), value: CLEAR },
            ],
          }
        },
      },
    ],
    finish: (a) => {
      const cart = readCart(a.items)
      const to = a.to.value
      const room = to.startsWith("res:")
      const order: OrderRequest = {
        outlet: a.outlet.value,
        items: cart.map((l) => ({ menu_item: l.item, qty: l.qty })),
        order_type: room ? "Room Service" : to === "table" ? "Dine In" : "Takeaway",
        ...(room ? { reservation: to.slice(4) } : {}),
        ...(to === "table" ? { table_no: a.table?.value } : {}),
      }
      const where = room
        ? translate("room service for {name}", { name: a.to.label })
        : to === "table"
          ? translate("table {table}", { table: a.table?.value ?? "" })
          : translate("takeaway")
      return {
        say: translate("{items} for {where}. {total} before tax. Send it to the kitchen?",
          { items: cartText(cart), where, total: money(cartTotal(cart)) }),
        choices: [{ label: translate("Send to the kitchen"), order }, startOver()],
      }
    },
  },
  }
}

// the food-order basket, carried between taps as the answer's value
const DONE = "__done"
const CLEAR = "__clear"
interface CartLine { item: string; name: string; price: number; qty: number }
function readCart(a?: Answer): CartLine[] {
  try {
    return a ? (JSON.parse(a.value) as CartLine[]) : []
  } catch {
    return []
  }
}
const cartText = (cart: CartLine[]) => cart.map((l) => `${l.qty} × ${l.name}`).join(", ")
const cartTotal = (cart: CartLine[]) => cart.reduce((s, l) => s + l.qty * l.price, 0)

/** "Options: A | B" on the AI's last line becomes tap buttons. */
export function splitOptions(content: string): { text: string; options: string[] } {
  const m = content.match(/(^|\n)[ \t]*\**Options:?\**[ \t]*([^\n]*)\s*$/i)
  if (!m || m.index === undefined) return { text: content, options: [] }
  const options = m[2].split("|").map((x) => x.replace(/[*`]/g, "").trim()).filter(Boolean)
  return options.length > 1
    ? { text: content.slice(0, m.index).trimEnd(), options }
    : { text: content, options: [] }
}
