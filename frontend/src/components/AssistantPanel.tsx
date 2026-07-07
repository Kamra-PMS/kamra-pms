import { useEffect, useRef, useState } from "react"
import { Loader2, Send, Sparkles, Trash2, X } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { cn } from "../lib/utils"
import { Markdown } from "../lib/markdown"

/** The front-desk copilot - appears only when the property has enabled
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
  find_reservations: "Looked up reservations",
  stay_detail: "Checked the stay",
  waitlist_ready: "Checked waitlist openings",
  promote_waitlist: "Promoted from waitlist",
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
    // append a growing assistant bubble right after the user's message
    const aIdx = history.length
    setMsgs([...history, { role: "assistant", content: "", actions: [] }])
    setBusy(true)

    const patch = (fn: (m: Msg) => Msg) =>
      setMsgs((ms) => ms.map((m, i) => (i === aIdx ? fn(m) : m)))
    const payload = {
      property: getCurrentProperty(),
      messages: history.map(({ role, content }) => ({ role, content })),
    }

    try {
      const csrf = (window as unknown as { csrf_token?: string }).csrf_token
      const res = await fetch("/api/method/kamra.assistant.ask_stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(csrf && csrf !== "None"
            ? { "X-Frappe-CSRF-Token": csrf }
            : {}),
        },
        credentials: "include",
        body: JSON.stringify(payload),
      })
      if (!res.ok || !res.body) throw new Error(`stream ${res.status}`)

      const reader = res.body.getReader()
      const dec = new TextDecoder()
      let buf = ""
      let gotAny = false
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
            gotAny = true
            patch((m) => ({ ...m, content: m.content + d.text }))
          } else if (event === "action") {
            patch((m) => ({
              ...m,
              actions: [...(m.actions ?? []), { tool: d.tool, ok: d.ok }],
            }))
          } else if (event === "error") {
            setError(d.message)
          }
        }
      }
      if (!gotAny) throw new Error("empty stream")
    } catch {
      // fallback to the non-streaming endpoint (older server / stream blocked)
      try {
        const out = await call<{ reply: string; actions: Msg["actions"] }>(
          "kamra.assistant.ask",
          payload,
        )
        patch(() => ({
          role: "assistant",
          content: out.reply,
          actions: out.actions,
        }))
      } catch (e) {
        setError(serverError(e))
        setMsgs((ms) => ms.filter((_, i) => i !== aIdx)) // drop empty bubble
      }
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
            {msgs.length > 0 && (
              <button
                aria-label="Clear conversation"
                title="Clear conversation"
                onClick={() => {
                  setMsgs([])
                  setError(null)
                }}
                className="rounded-md p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
              >
                <Trash2 className="size-3.5" aria-hidden />
              </button>
            )}
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {msgs.length === 0 && (
              <div className="space-y-2">
                <p className="text-sm text-zinc-600">
                  I can act on the property through Kamra's governed tools:
                </p>
                <ul className="list-disc space-y-0.5 pl-5 text-sm text-zinc-500">
                  <li>Read today's board - arrivals, departures, in-house</li>
                  <li>Check availability &amp; price a stay</li>
                  <li>Create bookings, check guests in / out</li>
                  <li>Open folios, post charges, take payments</li>
                  <li>Preview &amp; apply cancellations with the policy</li>
                  <li>Search guests and their history</li>
                </ul>
                <p className="text-xs text-zinc-400">
                  Every action is audit-logged. This chat lives on your device
                  and clears when you close or clear it.
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
                    "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm",
                    m.role === "user"
                      ? "ml-auto whitespace-pre-wrap bg-brand-600 text-white"
                      : "space-y-1.5 bg-zinc-100 text-zinc-800",
                  )}
                >
                  {m.role === "assistant" ? (
                    <Markdown text={m.content} />
                  ) : (
                    m.content
                  )}
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
                        {!a.ok && " - failed"}
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
