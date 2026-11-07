import { useCallback, useEffect, useRef, useState } from "react"
import { Link, useLocation, useOutletContext } from "react-router-dom"
import {
  ArrowRight,
  KeyRound,
  LayoutGrid,
  Loader2,
  MessageSquare,
  Plus,
  Send,
  Sparkles,
  Trash2,
  Wrench,
} from "lucide-react"

import {
  call,
  createConversation,
  deleteConversation,
  getBookingOptions,
  getConversation,
  getCurrentProperty,
  getSnapshot,
  listConversations,
  postRaw,
  saveConversation,
  type BookingOptions,
  type ChatMsg,
  type ConversationSummary,
  type Snapshot,
} from "../lib/api"
import { cn } from "../lib/utils"
import { cur, moneyLocale } from "../lib/money"
import { Markdown } from "../lib/markdown"
import AgentCards, { type AgentCard } from "../components/AgentCards"
import {
  flows,
  menuChoices,
  menuTiles,
  splitOptions,
  startOver,
  type Answers,
  type Choice,
  type FlowId,
  type GuideData,
  type GuideMenu,
  type GuideOutlet,
  type Outcome,
} from "../components/AgentGuide"
import VoiceButton, { agentLang, type VoiceHandle } from "../components/VoiceButton"
import type { ShellContext } from "../AppShell"
import { t as translate, useUILanguage } from "../lib/i18n"

const TOOL_LABEL: Record<string, string> = {
  availability: "Checked availability",
  quote: "Priced the stay",
  create_booking: "Created a booking",
  check_in: "Checked in",
  check_out: "Checked out",
  post_charge: "Posted a charge",
  take_payment: "Recorded a payment",
  find_reservations: "Looked up reservations",
  stay_detail: "Opened a stay",
  cancel_reservation: "Cancelled a booking",
  owner_briefing: "Read the day's numbers",
  front_desk_today: "Checked today's desk",
  waitlist_ready: "Checked waitlist openings",
  promote_waitlist: "Promoted from waitlist",
  booking_options: "Read booking options",
  checkout_context: "Read the check-out bill",
  get_folio: "Opened the folio",
  record_payment: "Recorded a payment",
  cancellation_preview: "Priced the cancellation",
  cancel_booking: "Cancelled a booking",
  waive_security_deposit: "Waived the deposit",
  collect_security_deposit: "Took the deposit",
  security_deposit_status: "Read the deposit",
  raise_ticket: "Raised a ticket",
  hk_queue: "Read housekeeping",
}
const toolLabel = (t: string) =>
  TOOL_LABEL[t] ?? t.replace(/_/g, " ")

const SUGGESTIONS = [
  "What does today look like - arrivals, departures, occupancy?",
  "Find the reservation for room 101 and show me the folio.",
  "Quote 2 nights in a Deluxe for 2 adults from this Friday.",
  "Which waitlisted guests can I now give a room?",
]

// one tap above the box: the desk's most common tasks, then the full list
const SHORTCUT_FLOWS: FlowId[] = ["walkin", "checkin", "checkout", "booking", "order", "payment", "today"]

// "check in", "Check-in" and "check in." all name the same task
const norm = (s: string) => s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim()

type FlowState = { id: FlowId; step: number; answers: Answers }

function ThinkingDots() {
  useUILanguage()
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-zinc-500">{translate("Thinking")}<span className="inline-flex gap-0.5">
        <span className="size-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:0ms]" />
        <span className="size-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:150ms]" />
        <span className="size-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:300ms]" />
      </span>
    </span>
  )
}

const SETUP_STEPS = [
  "Create an API key with your AI provider (OpenAI works out of the box).",
  "Open Settings → AI assistant, paste the key, pick a model and Test.",
  "Switch it on, save, and come back here.",
]

function AiSetupNotice() {
  useUILanguage()
  return (
    <div className="mx-auto max-w-md text-center">
      <span className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-brand-50 ring-1 ring-brand-100">
        <KeyRound className="size-5 text-brand-600" aria-hidden />
      </span>
      <h2 className="mt-4 text-lg font-semibold tracking-tight text-zinc-900">{translate("Add an AI key to start")}</h2>
      <p className="mt-1 text-sm text-zinc-500">{translate("Kamra Agent runs on your own AI account. It takes about two minutes.")}</p>
      <ol className="mt-5 space-y-2.5 text-left">
        {SETUP_STEPS.map((step, i) => (
          <li
            key={step}
            className="flex gap-3 rounded-lg border border-zinc-100 bg-zinc-50/70 px-3 py-2.5 text-sm text-zinc-700"
          >
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-brand-600 text-[11px] font-semibold text-white">
              {i + 1}
            </span>
            {translate(step)}
          </li>
        ))}
      </ol>
      <Link
        to="/settings/ai"
        className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
      >{translate("Open AI settings")}<ArrowRight className="size-4" aria-hidden />
      </Link>
      <p className="mt-4 text-xs text-zinc-400">{translate("The key stays on your server, stored masked. Usage is billed to your own provider account.")}</p>
    </div>
  )
}

export default function Assistant() {
  useUILanguage()
  const [convos, setConvos] = useState<ConversationSummary[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [msgs, setMsgs] = useState<ChatMsg[]>([])
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // the provider refused for money: the error gets a link to the AI settings
  const [noCredit, setNoCredit] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const voiceRef = useRef<VoiceHandle>(null)
  const [aiEnabled, setAiEnabled] = useState<boolean | null>(null)
  const shell = useOutletContext<ShellContext | undefined>()

  // msgs mirrored in a ref so a guided step can add a message and send
  // to the AI in the same tick without reading stale state
  const msgsRef = useRef<ChatMsg[]>([])
  const setAll = (next: ChatMsg[]) => {
    msgsRef.current = next
    setMsgs(next)
  }
  const push = (...m: ChatMsg[]) => setAll([...msgsRef.current, ...m])

  // the guided task in progress, if any (components/AgentGuide)
  const [flow, setFlowState] = useState<FlowState | null>(null)
  const flowRef = useRef<FlowState | null>(null)
  const setFlow = (f: FlowState | null) => {
    flowRef.current = f
    setFlowState(f)
  }
  const [stepping, setStepping] = useState(false)
  // today's board, the booking options, outlets and menus, fetched once per task
  const cache = useRef<{
    snap?: Promise<Snapshot>
    opts?: Promise<BookingOptions>
    outlets?: Promise<GuideOutlet[]>
    menus?: Record<string, Promise<GuideMenu>>
  }>({})
  const data: GuideData = {
    snapshot: () => (cache.current.snap ??= getSnapshot()),
    options: () => (cache.current.opts ??= getBookingOptions()),
    outlets: () =>
      (cache.current.outlets ??= call<GuideOutlet[]>("kamra.pos.outlets", { property: getCurrentProperty() })),
    menu: (outlet) =>
      ((cache.current.menus ??= {})[outlet] ??= call<GuideMenu>("kamra.pos.pos_menu", { outlet })),
  }

  async function runStep(f: FlowState) {
    const def = flows()[f.id]
    // questions that don't apply to this answer set are passed over
    while (f.step < def.steps.length && def.steps[f.step].skip?.(f.answers)) f = { ...f, step: f.step + 1 }
    if (f.step >= def.steps.length) {
      setFlow(null)
      return finish(def.finish(f.answers, aiEnabled !== false))
    }
    setFlow(f)
    setStepping(true)
    try {
      const step = def.steps[f.step]
      const { ask, choices, auto } = await step.load(f.answers, data)
      // one possible answer (a hotel with one kitchen): taken, not asked
      if (auto) return runStep({ ...f, step: f.step + 1, answers: { ...f.answers, [step.key]: auto } })
      push({ role: "assistant", content: ask, choices: [...choices, startOver()] })
    } catch {
      cache.current = {}
      push({
        role: "assistant",
        content: translate("I couldn't load that list. Type the answer instead."),
        choices: [startOver()],
      })
    } finally {
      setStepping(false)
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }

  function startFlow(id: FlowId | "menu", label?: string) {
    if (busy) return
    setError(null)
    if (label) push({ role: "user", content: label })
    if (id === "menu") {
      setFlow(null)
      push({ role: "assistant", content: translate("What would you like to do? Tap one."), choices: menuChoices() })
      return
    }
    cache.current = {}
    runStep({ id, step: 0, answers: {} })
  }

  function answer(value: string, label: string, typed = false) {
    const f = flowRef.current
    if (!f) return
    const step = flows()[f.id].steps[f.step]
    push({ role: "user", content: label || translate("Skip") })
    const picked = { label, value, typed }
    if (step.collect) {
      // a basket (food order): add to it and ask again until Done
      const next = step.collect(f.answers[step.key], picked)
      if (next) return runStep({ ...f, answers: { ...f.answers, [step.key]: next } })
      return runStep({ ...f, step: f.step + 1 })
    }
    runStep({ ...f, step: f.step + 1, answers: { ...f.answers, [step.key]: picked } })
  }

  // the guide sends a food order itself - the same call the POS till makes
  async function placeOrder(c: Choice) {
    if (!c.order) return
    push({ role: "user", content: c.label })
    setStepping(true)
    try {
      const r = await call<{ order: string; order_total: number }>("kamra.pos.send_order", {
        ...c.order,
        property: getCurrentProperty(),
      })
      push({
        role: "assistant",
        content: translate("Sent to the kitchen. Order {order}, total {total}.", {
          order: r.order,
          total: `${cur()}${Number(r.order_total || 0).toLocaleString(moneyLocale())}`,
        }),
        choices: [{ label: translate("Another food order"), goto: "order" }, startOver()],
      })
    } catch (e) {
      push({
        role: "assistant",
        content: translate("The order didn't go through: {reason}", {
          reason: e instanceof Error ? e.message : translate("unknown error"),
        }),
        choices: [{ label: translate("Try again"), goto: "order" }, startOver()],
      })
    } finally {
      setStepping(false)
    }
  }

  function finish(o: Outcome) {
    if ("prompt" in o) {
      if (aiEnabled === false) {
        push({ role: "assistant", content: translate("This step needs the AI. Add an AI key in Settings → AI assistant."), choices: [startOver()] })
        return
      }
      send(o.prompt)
      return
    }
    push({ role: "assistant", content: o.say, cards: o.cards, choices: o.choices })
  }

  function pick(c: Choice) {
    if (busy || stepping) return
    if (c.goto) return startFlow(c.goto, c.label)
    if (c.book) {
      push({ role: "user", content: c.label })
      setFlow(null)
      shell?.openBooking(c.book)
      return
    }
    if (c.order) return placeOrder(c)
    if (c.prompt !== undefined) return send(c.prompt)
    if (c.value !== undefined && flowRef.current) return answer(c.value, c.label)
    // an option the AI offered: sent back as the reply
    send(c.label)
  }

  function submit(text: string) {
    const q = text.trim()
    const f = flowRef.current
    if (!q || busy || stepping) return
    if (f && flows()[f.id].steps[f.step]?.text) {
      setInput("")
      return answer(q, q, true)
    }
    // a tap-only question: typing (or saying) one of the answers counts as
    // tapping it - the guest's name, or the room number shown under it
    const open = msgsRef.current[msgsRef.current.length - 1]?.choices ?? []
    const said = norm(q)
    const hit = said && open.find((c) =>
      (f ? c.value !== undefined : !!(c.goto || c.order || c.book)) &&
      (norm(c.label).includes(said) ||
       (/\d/.test(said) && !!c.hint && ` ${norm(c.hint)} `.includes(` ${said} `))))
    if (hit) {
      setInput("")
      return pick(hit)
    }
    // no task open: naming one ("check in", "food order") starts it
    const tile = !f && menuTiles().find((tl) => norm(tl.label) === said)
    if (tile) {
      setInput("")
      return startFlow(tile.id, tile.label)
    }
    // typed while a tap-only question was open: a free question for the AI
    setFlow(null)
    send(q)
  }
  // a screen can hand the agent a ready question (End of Day blockers);
  // it is put in the box for the user to read and send, not sent for them
  const handoff = (useLocation().state as { prompt?: string } | null)?.prompt
  useEffect(() => {
    if (handoff) setInput(handoff)
  }, [handoff])

  useEffect(() => {
    call<{ enabled: boolean }>("kamra.assistant.assistant_status", {
      property: getCurrentProperty(),
    })
      .then((s) => setAiEnabled(s.enabled))
      .catch(() => setAiEnabled(true))
  }, [])

  const refreshList = useCallback(
    () => listConversations().then(setConvos).catch(() => setConvos([])),
    [],
  )

  useEffect(() => {
    refreshList()
  }, [refreshList])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
  }, [msgs, busy])

  async function openConvo(name: string) {
    if (busy) return
    setError(null)
    try {
      const c = await getConversation(name)
      setActiveId(c.name)
      setFlow(null)
      setAll(c.messages)
    } catch {
      setError(translate("Couldn't open that conversation."))
    }
  }

  function newChat() {
    if (busy) return
    setActiveId(null)
    setFlow(null)
    setAll([])
    setError(null)
  }

  async function removeConvo(name: string, e: React.MouseEvent) {
    e.stopPropagation()
    await deleteConversation(name).catch(() => {})
    setConvos((cs) => cs.filter((c) => c.name !== name))
    if (activeId === name) newChat()
  }

  async function send(text: string) {
    const q = text.trim()
    if (!q || busy) return
    setInput("")
    setError(null)
    setNoCredit(false)
    setFlow(null)
    const isFirst = !activeId
    // the AI reads only what was said; old tap buttons stay on screen
    const history: ChatMsg[] = [...msgsRef.current, { role: "user", content: q }]
    const aIdx = history.length
    setAll([...history, { role: "assistant", content: "", actions: [] }])
    setBusy(true)
    const patch = (fn: (m: ChatMsg) => ChatMsg) =>
      setAll(msgsRef.current.map((m, i) => (i === aIdx ? fn(m) : m)))

    let content = ""
    const actions: { tool: string; ok: boolean }[] = []
    const cards: AgentCard[] = []
    try {
      let convId = activeId
      if (!convId) {
        const c = await createConversation(q.slice(0, 60))
        convId = c.name
        setActiveId(convId)
        setConvos((cs) => [
          { name: c.name, title: c.title, modified: "" },
          ...cs,
        ])
      }

      const res = await postRaw("/api/method/kamra.assistant.ask_stream", {
        property: getCurrentProperty(),
        messages: history.map(({ role, content }) => ({ role, content })),
        lang: agentLang(),
      })
      if (!res.ok || !res.body) throw new Error(`stream ${res.status}`)
      const reader = res.body.getReader()
      const dec = new TextDecoder()
      let buf = ""
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        let sep: number
        while ((sep = buf.indexOf("\n\n")) >= 0) {
          const block = buf.slice(0, sep)
          buf = buf.slice(sep + 2)
          let event = ""
          let data = ""
          for (const line of block.split("\n")) {
            if (line.startsWith("event:")) event = line.slice(6).trim()
            else if (line.startsWith("data:")) data = line.slice(5).trim()
          }
          if (!event || !data) continue
          const d = JSON.parse(data)
          if (event === "token") {
            content += d.text
            patch((m) => ({ ...m, content }))
          } else if (event === "action") {
            actions.push({ tool: d.tool, ok: d.ok })
            patch((m) => ({ ...m, actions: [...actions] }))
          } else if (event === "card") {
            cards.push(d as AgentCard)
            patch((m) => ({ ...m, cards: [...cards] }))
          } else if (event === "error") {
            setError(d.message)
            setNoCredit(d.code === "out_of_credit")
          }
        }
      }
      // persist the completed turn
      const finalMsgs: ChatMsg[] = [
        ...history,
        { role: "assistant", content, actions, cards },
      ]
      await saveConversation(
        convId,
        finalMsgs,
        isFirst ? q.slice(0, 60) : undefined,
      )
      if (isFirst) refreshList()
    } catch {
      setError(translate("The agent couldn't finish - check the AI key in Settings."))
      if (!content) setAll(msgsRef.current.filter((_, i) => i !== aIdx))
    } finally {
      setBusy(false)
    }
  }

  return (
    // fills the viewport under the top bar + page header; only panes scroll
    <div className="flex h-[calc(100dvh-11rem)] min-h-[440px] gap-4">
      {/* conversations */}
      <div className="hidden w-60 shrink-0 flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm md:flex">
        <div className="border-b border-zinc-100 p-2">
          <button
            onClick={newChat}
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-200 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
          >
            <Plus className="size-4" />{translate(" New chat")}</button>
        </div>
        <div className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {convos.length === 0 && (
            <div className="flex flex-col items-center gap-2 px-3 py-10 text-center">
              <MessageSquare className="size-5 text-zinc-300" aria-hidden />
              <p className="text-xs text-zinc-400">{translate("Your chats will show up here.")}</p>
            </div>
          )}
          {convos.map((c) => (
            <div
              key={c.name}
              onClick={() => openConvo(c.name)}
              className={cn(
                "group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm",
                activeId === c.name
                  ? "bg-brand-50 text-brand-800"
                  : "text-zinc-600 hover:bg-zinc-50",
              )}
            >
              <span className="flex-1 truncate">{c.title || translate("Untitled")}</span>
              <button
                onClick={(e) => removeConvo(c.name, e)}
                aria-label={translate("Delete conversation")}
                className="opacity-0 group-hover:opacity-100"
              >
                <Trash2 className="size-3.5 text-zinc-400 hover:text-rose-500" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* chat */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-zinc-100 px-4 py-2.5 text-xs text-zinc-500">
          <span
            className={cn(
              "size-2 rounded-full",
              aiEnabled === false ? "bg-zinc-300" : "bg-brand-500",
            )}
            aria-hidden
          />
          <span className="truncate">
            {aiEnabled === false ? translate("Not set up") : translate("Acting as you")} ·{" "}
            <span className="font-medium text-zinc-700">
              {getCurrentProperty()?.split("-")[0] ?? translate("your hotel")}
            </span>
          </span>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5">
          {msgs.length === 0 && aiEnabled === false && (
            <div className="flex min-h-full items-center justify-center py-6">
              <AiSetupNotice />
            </div>
          )}
          {msgs.length === 0 && aiEnabled !== false && (
            <div className="mx-auto max-w-3xl space-y-3 py-4 text-center">
              <Sparkles className="mx-auto size-8 text-brand-500" />
              <h2 className="text-lg font-semibold">{translate("What would you like to do?")}</h2>
              <p className="text-sm text-zinc-500">{translate("Tap a task and I'll ask you one thing at a time. Or just type what you need.")}</p>
              <div className="grid grid-cols-2 gap-2 pt-2 sm:grid-cols-3 lg:grid-cols-4">
                {menuTiles().map((tl) => (
                  <button
                    key={tl.id}
                    onClick={() => startFlow(tl.id, tl.label)}
                    className="flex items-start gap-2.5 rounded-xl border border-zinc-200 bg-white px-3 py-3 text-left shadow-sm transition hover:border-brand-400 hover:bg-brand-50/40"
                  >
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 ring-1 ring-brand-100">
                      <tl.icon className="size-4 text-brand-600" aria-hidden />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-zinc-900">{tl.label}</span>
                      <span className="block text-xs text-zinc-500">{tl.hint}</span>
                    </span>
                  </button>
                ))}
              </div>
              <p className="pt-3 text-xs font-medium uppercase tracking-wide text-zinc-400">{translate("Or ask in your own words")}</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(translate(s))}
                    className="rounded-lg border border-zinc-200 px-3 py-2 text-left text-sm text-zinc-600 hover:border-brand-400 hover:bg-zinc-50"
                  >
                    {translate(s)}
                  </button>
                ))}
              </div>
            </div>
          )}
          {msgs.map((m, i) => {
            const last = i === msgs.length - 1
            const { text, options } =
              m.role === "assistant" ? splitOptions(m.content) : { text: m.content, options: [] }
            const choices: Choice[] =
              m.choices ?? (last && !busy ? options.map((o) => ({ label: o })) : [])
            return (
            <div key={i} className="space-y-2">
            <div
              className={cn(
                "flex items-end gap-2",
                m.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              {m.role === "assistant" && (
                <span className="mb-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-600/10">
                  <Sparkles className="size-3.5 text-brand-600" aria-hidden />
                </span>
              )}
              <div
                className={cn(
                  "max-w-[75%] rounded-2xl px-4 py-2.5 text-sm shadow-sm",
                  m.role === "user"
                    ? "whitespace-pre-wrap rounded-br-md bg-brand-600 text-white"
                    : "space-y-2 rounded-bl-md border border-zinc-100 bg-white text-zinc-800",
                )}
              >
                {m.role === "assistant" ? (
                  <>
                    {m.actions && m.actions.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {m.actions.map((a, j) => (
                          <span
                            key={j}
                            className={cn(
                              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px]",
                              a.ok
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-rose-100 text-rose-700",
                            )}
                          >
                            <Wrench className="size-3" />
                            {translate(toolLabel(a.tool))}
                          </span>
                        ))}
                      </div>
                    )}
                    {text ? (
                      <Markdown text={text} />
                    ) : (
                      busy && <ThinkingDots />
                    )}
                  </>
                ) : (
                  m.content
                )}
              </div>
            </div>
            {m.role === "assistant" && m.cards && m.cards.length > 0 && (
              <div className="ms-9 max-w-[75%]">
                <AgentCards cards={m.cards} />
              </div>
            )}
            {m.role === "assistant" && choices.length > 0 && (
              // only the newest question can still be answered
              <div className={cn("ms-9 flex max-w-[85%] flex-wrap gap-1.5", !last && "opacity-50")}>
                {choices.map((c, j) => (
                  <button
                    key={j}
                    type="button"
                    disabled={!last || busy || stepping}
                    onClick={() => pick(c)}
                    className={cn(
                      "rounded-xl border px-3 py-1.5 text-left text-sm transition disabled:cursor-default",
                      c.goto === "menu"
                        ? "border-transparent text-zinc-500 hover:text-zinc-800"
                        : "border-brand-200 bg-white text-zinc-800 shadow-sm hover:border-brand-400 hover:bg-brand-50",
                    )}
                  >
                    <span className="block font-medium">{c.label}</span>
                    {c.hint && <span className="block text-xs text-zinc-500">{c.hint}</span>}
                  </button>
                ))}
              </div>
            )}
            </div>
            )
          })}
          {stepping && (
            <div className="ms-9">
              <ThinkingDots />
            </div>
          )}
          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">
              {translate(error)}
              {noCredit && (
                <Link to="/settings/ai" className="ms-2 font-medium underline">
                  {translate("Open AI settings")}
                </Link>
              )}
            </p>
          )}
          <div ref={endRef} />
        </div>

        {aiEnabled !== false && (
          // wraps rather than scrolls; no dark:bg — .dark remaps zinc/white vars
          <div className="flex flex-wrap gap-1.5 border-t border-zinc-100 px-3 pt-2.5">
            <button
              type="button"
              disabled={busy || stepping}
              onClick={() => startFlow("menu", translate("All tasks"))}
              className="inline-flex shrink-0 items-center gap-1 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700 hover:border-brand-300 disabled:opacity-50"
            >
              <LayoutGrid className="size-3.5" aria-hidden />
              {translate("All tasks")}
            </button>
            {menuTiles()
              .filter((tl) => SHORTCUT_FLOWS.includes(tl.id))
              .map((tl) => (
                <button
                  key={tl.id}
                  type="button"
                  disabled={busy || stepping}
                  onClick={() => startFlow(tl.id, tl.label)}
                  className="shrink-0 rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-medium text-zinc-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 transition-colors shadow-xs disabled:opacity-50"
                >
                  {tl.label}
                </button>
              ))}
          </div>
        )}
        <form
          className="p-3"
          onSubmit={(e) => {
            e.preventDefault()
            // Send is the only way spoken words go out; it ends the listening
            voiceRef.current?.stop()
            submit(input)
          }}
        >
          <div className="flex items-center gap-2 rounded-2xl border border-zinc-200 bg-white px-4 py-1.5 shadow-sm transition focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100">
            <input
              ref={inputRef}
              className="flex-1 bg-transparent py-2 text-sm outline-none text-zinc-900 placeholder:text-zinc-400 disabled:cursor-not-allowed"
              placeholder={
                (aiEnabled === false
                  ? translate("Add an AI key in Settings to start chatting")
                  : (flow && flows()[flow.id].steps[flow.step]?.text) ||
                    translate("Ask anything about the hotel…"))
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={busy || aiEnabled === false}
            />
            <VoiceButton
              ref={voiceRef}
              disabled={busy || stepping || aiEnabled === false}
              onText={setInput}
              onError={setError}
            />
            <button
              type="submit"
              aria-label={translate("Send")}
              disabled={busy || stepping || aiEnabled === false || !input.trim()}
              className="flex size-9 items-center justify-center rounded-full bg-brand-600 text-white transition hover:bg-brand-700 disabled:opacity-40"
            >
              {busy ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Send className="size-4" />
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
