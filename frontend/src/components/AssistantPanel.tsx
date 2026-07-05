import { useEffect, useRef, useState } from "react"
import { Loader2, Send, Sparkles, X } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { cn } from "../lib/utils"

/** The front-desk copilot — appears only when the property has enabled
 * it with their own key. Model talks; the governed tool layer acts. */

interface Msg {
  role: "user" | "assistant"
  content: string
  actions?: { tool: string; ok: boolean }[]
}

const SUGGESTIONS = [
  "Who's arriving today?",
  "Any departures with money due?",
  "Quote a double room for this weekend",
  "What does cancelling RES-… cost?",
]

const toolLabel: Record<string, string> = {
  front_desk_today: "Checked today's board",
  availability: "Checked availability",
  quote: "Priced the stay",
  booking_options: "Looked up options",
  create_booking: "Created a booking",
  guest_search: "Searched guests",
  check_in: "Checked in",
  check_out: "Checked out",
  get_folio: "Opened the folio",
  post_charge: "Posted a charge",
  record_payment: "Recorded a payment",
  cancellation_preview: "Previewed cancellation",
  cancel_booking: "Cancelled the booking",
}

export default function AssistantPanel() {
  const [enabled, setEnabled] = useState(false)
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    call<{ enabled: boolean }>("kamra.assistant.assistant_status", {
      property: getCurrentProperty(),
    })
      .then((s) => setEnabled(s.enabled))
      .catch(() => setEnabled(false))
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [msgs, busy])

  if (!enabled) return null

  async function send(text: string) {
    const q = text.trim()
    if (!q || busy) return
    setInput("")
    setError(null)
    const history = [...msgs, { role: "user" as const, content: q }]
    setMsgs(history)
    setBusy(true)
    try {
      const out = await call<{ reply: string; actions: Msg["actions"] }>(
        "kamra.assistant.ask",
        {
          property: getCurrentProperty(),
          messages: history.map(({ role, content }) => ({ role, content })),
        },
      )
      setMsgs((m) => [
        ...m,
        { role: "assistant", content: out.reply, actions: out.actions },
      ])
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        aria-label="Open the assistant"
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-5 right-5 z-40 flex size-12 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg hover:bg-brand-700 print:hidden"
      >
        {open ? (
          <X className="size-5" aria-hidden />
        ) : (
          <Sparkles className="size-5" aria-hidden />
        )}
      </button>

      {open && (
        <div className="fixed bottom-20 right-5 z-40 flex h-[560px] w-[380px] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-2xl print:hidden">
          <div className="flex items-center gap-2 border-b border-zinc-100 px-4 py-3">
            <Sparkles className="size-4 text-brand-600" aria-hidden />
            <span className="text-sm font-semibold">Front-desk copilot</span>
            <span className="ml-auto text-[10px] uppercase tracking-wider text-zinc-400">
              your key · your data
            </span>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {msgs.length === 0 && (
              <div className="space-y-2">
                <p className="text-sm text-zinc-500">
                  Ask anything about today's board, price a stay, book,
                  check in, take a payment, cancel with the policy applied.
                </p>
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    className="block w-full rounded-lg border border-zinc-200 px-3 py-1.5 text-left text-sm text-zinc-600 hover:border-brand-600"
                    onClick={() => send(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i}>
                <div
                  className={cn(
                    "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm",
                    m.role === "user"
                      ? "ml-auto bg-brand-600 text-white"
                      : "bg-zinc-100 text-zinc-800",
                  )}
                >
                  {m.content}
                </div>
                {m.actions && m.actions.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {m.actions.map((a, j) => (
                      <span
                        key={j}
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-medium",
                          a.ok
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-rose-50 text-rose-600",
                        )}
                      >
                        {toolLabel[a.tool] ?? a.tool}
                        {!a.ok && " — failed"}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {busy && (
              <Loader2
                className="size-4 animate-spin text-zinc-400"
                aria-label="Thinking"
              />
            )}
            {error && (
              <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-600">
                {error}
              </p>
            )}
            <div ref={endRef} />
          </div>

          <form
            className="flex items-center gap-2 border-t border-zinc-100 px-3 py-2.5"
            onSubmit={(e) => {
              e.preventDefault()
              send(input)
            }}
          >
            <input
              className="flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
              placeholder="Ask the copilot…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button
              type="submit"
              aria-label="Send"
              disabled={busy || !input.trim()}
              className="rounded-lg bg-brand-600 p-2 text-white disabled:opacity-40"
            >
              <Send className="size-4" aria-hidden />
            </button>
          </form>
        </div>
      )}
    </>
  )
}
