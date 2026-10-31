import { useCallback, useEffect, useRef, useState } from "react"
import { Link, useLocation } from "react-router-dom"
import {
  ArrowRight,
  KeyRound,
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
  getConversation,
  getCurrentProperty,
  listConversations,
  saveConversation,
  type ChatMsg,
  type ConversationSummary,
} from "../lib/api"
import { cn } from "../lib/utils"
import { Markdown } from "../lib/markdown"
import AgentCards, { type AgentCard } from "../components/AgentCards"
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

// one tap, sent as typed: the desk's most common asks
const SHORTCUTS: { label: string; prompt: string }[] = [
  { label: "Today's arrivals", prompt: "Who is arriving today, and are their rooms ready?" },
  { label: "Departures and balances", prompt: "Who is leaving today and what does each still owe?" },
  { label: "In-house guests", prompt: "List the guests in house now with their rooms." },
  { label: "Quote a stay", prompt: "Quote a stay for 2 adults: " },
  { label: "Night audit check", prompt: "Run the night audit precheck and tell me what blocks it." },
]

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
  const endRef = useRef<HTMLDivElement>(null)
  const [aiEnabled, setAiEnabled] = useState<boolean | null>(null)
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
      setMsgs(c.messages)
    } catch {
      setError(translate("Couldn't open that conversation."))
    }
  }

  function newChat() {
    if (busy) return
    setActiveId(null)
    setMsgs([])
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
    const isFirst = msgs.length === 0
    const history: ChatMsg[] = [...msgs, { role: "user", content: q }]
    const aIdx = history.length
    setMsgs([...history, { role: "assistant", content: "", actions: [] }])
    setBusy(true)
    const patch = (fn: (m: ChatMsg) => ChatMsg) =>
      setMsgs((ms) => ms.map((m, i) => (i === aIdx ? fn(m) : m)))

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

      const csrf = (window as unknown as { csrf_token?: string }).csrf_token
      const res = await fetch("/api/method/kamra.assistant.ask_stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(csrf && csrf !== "None" ? { "X-Frappe-CSRF-Token": csrf } : {}),
        },
        credentials: "include",
        body: JSON.stringify({
          property: getCurrentProperty(),
          messages: history.map(({ role, content }) => ({ role, content })),
        }),
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
      if (!content) setMsgs((ms) => ms.filter((_, i) => i !== aIdx))
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
            <div className="mx-auto max-w-xl space-y-3 py-8 text-center">
              <Sparkles className="mx-auto size-8 text-brand-500" />
              <h2 className="text-lg font-semibold">{translate("Your AI, acting as you")}</h2>
              <p className="text-sm text-zinc-500">{translate("It can look things up and act - quote and book stays, check guests in and out, post charges and payments, work the waitlist, and read the day's numbers.")}</p>
              <div className="grid gap-2 pt-2 sm:grid-cols-2">
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
          {msgs.map((m, i) => (
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
                    {m.content ? (
                      <Markdown text={m.content} />
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
            </div>
          ))}
          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">
              {translate(error)}
            </p>
          )}
          <div ref={endRef} />
        </div>

        {aiEnabled !== false && (
          <div className="flex gap-1.5 overflow-x-auto border-t border-zinc-100 dark:border-zinc-800 px-3 pt-2.5">
            {SHORTCUTS.map((sc) => (
              <button
                key={sc.label}
                type="button"
                disabled={busy}
                onClick={() =>
                  sc.prompt.endsWith(": ") ? setInput(translate(sc.prompt)) : send(translate(sc.prompt))
                }
                className="shrink-0 rounded-full border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/90 px-3 py-1 text-xs font-medium text-zinc-700 dark:text-zinc-200 hover:border-brand-300 dark:hover:border-brand-500 hover:bg-brand-50 dark:hover:bg-brand-950/80 hover:text-brand-700 dark:hover:text-brand-300 transition-colors shadow-xs disabled:opacity-50"
              >
                {translate(sc.label)}
              </button>
            ))}
          </div>
        )}
        <form
          className="p-3"
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
        >
          <div className="flex items-center gap-2 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/90 px-4 py-1.5 shadow-sm transition focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100 dark:focus-within:ring-brand-900">
            <input
              className="flex-1 bg-transparent py-2 text-sm outline-none text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 disabled:cursor-not-allowed"
              placeholder={
                (aiEnabled === false
                  ? translate("Add an AI key in Settings to start chatting")
                  : translate("Ask anything about the hotel…"))
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={busy || aiEnabled === false}
            />
            <button
              type="submit"
              aria-label={translate("Send")}
              disabled={busy || aiEnabled === false || !input.trim()}
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
