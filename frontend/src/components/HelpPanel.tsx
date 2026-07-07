import { useEffect, useRef, useState } from "react"
import { HelpCircle, Loader2, Send, X } from "lucide-react"

import { call, getCurrentProperty } from "../lib/api"
import { cn } from "../lib/utils"
import { Markdown } from "../lib/markdown"

/** How-to help assistant - explains how to use Kamra (it never acts on data;
 *  that's the front-desk copilot). Streams answers, grounded in the app. */

interface Msg {
  role: "user" | "assistant"
  content: string
}

const SUGGESTIONS = [
  "How do I check a guest in?",
  "How do I add photos to a room type?",
  "How do I waitlist a booking?",
  "What is RevPAX?",
  "Where do I manage users?",
]

export default function HelpPanel() {
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
    const aIdx = history.length
    setMsgs([...history, { role: "assistant", content: "" }])
    setBusy(true)
    const patch = (fn: (m: Msg) => Msg) =>
      setMsgs((ms) => ms.map((m, i) => (i === aIdx ? fn(m) : m)))
    const payload = {
      property: getCurrentProperty(),
      messages: history.map(({ role, content }) => ({ role, content })),
    }
    try {
      const csrf = (window as unknown as { csrf_token?: string }).csrf_token
      const res = await fetch("/api/method/kamra.assistant.help_ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(csrf && csrf !== "None" ? { "X-Frappe-CSRF-Token": csrf } : {}),
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
          } else if (event === "error") {
            setError(d.message)
          }
        }
      }
      if (!gotAny) throw new Error("empty")
    } catch {
      setError(
        "Couldn't reach the help assistant - check the AI key in Settings.",
      )
      setMsgs((ms) => ms.filter((_, i) => i !== aIdx))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        aria-label="Open help"
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-5 right-5 z-40 flex size-12 items-center justify-center rounded-full border border-zinc-200 bg-white text-zinc-600 shadow-lg hover:text-brand-700 print:hidden"
      >
        {open ? <X className="size-5" /> : <HelpCircle className="size-5" />}
      </button>

      {open && (
        <div className="fixed bottom-20 right-5 z-40 flex h-[520px] w-[360px] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-2xl print:hidden">
          <div className="flex items-center gap-2 border-b border-zinc-100 px-4 py-3">
            <HelpCircle className="size-4 text-brand-600" />
            <span className="text-sm font-semibold">How-to help</span>
            <span className="ml-auto text-[10px] uppercase tracking-wider text-zinc-400">
              explains, doesn't act
            </span>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {msgs.length === 0 && (
              <div className="space-y-2">
                <p className="text-sm text-zinc-600">
                  Ask how to do anything in Kamra - I'll walk you through it.
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
              <div
                key={i}
                className={cn(
                  "max-w-[88%] rounded-2xl px-3.5 py-2 text-sm",
                  m.role === "user"
                    ? "ml-auto whitespace-pre-wrap bg-brand-600 text-white"
                    : "space-y-1.5 bg-zinc-100 text-zinc-800",
                )}
              >
                {m.role === "assistant" ? <Markdown text={m.content} /> : m.content}
              </div>
            ))}
            {busy && (
              <Loader2 className="size-4 animate-spin text-zinc-400" />
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
              placeholder="How do I…?"
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button
              type="submit"
              aria-label="Send"
              disabled={busy || !input.trim()}
              className="rounded-lg bg-brand-600 p-2 text-white disabled:opacity-40"
            >
              <Send className="size-4" />
            </button>
          </form>
        </div>
      )}
    </>
  )
}
