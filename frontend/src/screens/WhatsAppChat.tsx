import { useCallback, useEffect, useRef, useState } from "react"
import { MessageCircle, Send, Settings2 } from "lucide-react"
import { Link } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { toFullPath } from "../lib/routing"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"

/* The desk's WhatsApp inbox - threads on the left, the conversation on
   the right, replies into the guest's 24-hour session window. Modeled on
   Frappe CRM's WhatsApp tab, scoped to the property's own number. */

interface Thread {
  number: string
  guest: string | null
  guest_name: string
  reservation: string | null
  last_message: string
  last_direction: "Inbound" | "Outbound"
  last_status: string
  last_at: string
}
interface Msg {
  name: string
  direction: "Inbound" | "Outbound"
  message_type: "Text" | "Template"
  template_name: string | null
  content: string
  status: string
  error: string | null
  creation: string
  reservation: string | null
}

const fmtTime = (d: string) =>
  new Date(d.replace(" ", "T")).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  })

export default function WhatsAppChat() {
  const property = getCurrentProperty()
  const [threads, setThreads] = useState<Thread[]>([])
  const [active, setActive] = useState<string | null>(null)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [sessionOpen, setSessionOpen] = useState(false)
  const [draft, setDraft] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const loadThreads = useCallback(() => {
    call<Thread[]>("kamra.whatsapp.threads", { property })
      .then((t) => {
        setThreads(t)
        setLoaded(true)
        setActive((a) => a ?? t[0]?.number ?? null)
      })
      .catch((e) => setError(serverError(e)))
  }, [property])

  const loadThread = useCallback(() => {
    if (!active) return
    call<{ messages: Msg[]; session_open: boolean }>(
      "kamra.whatsapp.thread",
      { property, number: active },
    )
      .then((d) => {
        setMsgs(d.messages)
        setSessionOpen(d.session_open)
      })
      .catch((e) => setError(serverError(e)))
  }, [property, active])

  useEffect(() => {
    loadThreads()
    const t = setInterval(loadThreads, 15_000)
    return () => clearInterval(t)
  }, [loadThreads])
  useEffect(() => {
    loadThread()
    const t = setInterval(loadThread, 10_000)
    return () => clearInterval(t)
  }, [loadThread])
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [msgs.length])

  async function sendReply() {
    if (!draft.trim() || !active) return
    setBusy(true)
    setError(null)
    try {
      await call("kamra.whatsapp.reply", {
        property,
        number: active,
        text: draft.trim(),
      })
      setDraft("")
      loadThread()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const activeThread = threads.find((t) => t.number === active)

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <MessageCircle className="size-5 text-brand-600" aria-hidden />
          <h1 className="text-xl font-semibold tracking-tight">WhatsApp</h1>
        </div>
        <p className="text-sm text-zinc-500">
          Guest conversations on your own number - confirmations go out
          automatically, replies land here and on the desk queue.
        </p>
        <Link
          to="/channels"
          className="ml-auto flex items-center gap-1.5 rounded-full border border-zinc-200 px-3 py-1.5 text-sm text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700"
        >
          <Settings2 className="size-4" aria-hidden />
          Connect a number
        </Link>
      </header>

      {loaded && threads.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-zinc-300 p-10 text-center">
          <MessageCircle className="mx-auto size-8 text-zinc-300" aria-hidden />
          <p className="mt-3 text-sm font-medium text-zinc-600">
            No conversations yet
          </p>
          <p className="mx-auto mt-1 max-w-md text-sm text-zinc-500">
            Connect your WhatsApp Business number under Channels and messages
            will start flowing: booking confirmations and check-in links go
            out on their own, and anything guests write appears here.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-2xl border border-zinc-200 bg-white">
            <ul className="max-h-[70vh] divide-y divide-zinc-100 overflow-y-auto">
              {threads.map((t) => (
                <li key={t.number}>
                  <button
                    onClick={() => setActive(t.number)}
                    className={cn(
                      "w-full px-4 py-3 text-left transition hover:bg-zinc-50",
                      active === t.number && "bg-brand-50/60",
                    )}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-zinc-800">
                        {t.guest_name}
                      </span>
                      <span className="shrink-0 text-[11px] text-zinc-400">
                        {fmtTime(t.last_at)}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-zinc-500">
                      {t.last_direction === "Outbound" && "You: "}
                      {t.last_message}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex max-h-[70vh] flex-col rounded-2xl border border-zinc-200 bg-white lg:col-span-2">
            {activeThread && (
              <div className="flex items-center gap-2 border-b border-zinc-100 px-4 py-3">
                <div>
                  <p className="text-sm font-semibold text-zinc-800">
                    {activeThread.guest_name}
                  </p>
                  <p className="text-xs text-zinc-400">{activeThread.number}</p>
                </div>
                {activeThread.reservation && (
                  <a
                    href={toFullPath(`/grc/${activeThread.reservation}`)}
                    target="_blank"
                    rel="noreferrer"
                    className="ml-auto text-xs font-medium text-brand-700 hover:underline"
                  >
                    Open stay →
                  </a>
                )}
              </div>
            )}
            <div className="flex-1 space-y-2 overflow-y-auto bg-zinc-50/60 p-4">
              {msgs.map((m) => (
                <div
                  key={m.name}
                  className={cn(
                    "max-w-[78%] rounded-2xl px-3.5 py-2 text-sm shadow-sm",
                    m.direction === "Outbound"
                      ? "ml-auto rounded-br-md bg-brand-600 text-white"
                      : "rounded-bl-md border border-zinc-200 bg-white text-zinc-800",
                  )}
                >
                  {m.message_type === "Template" && (
                    <p
                      className={cn(
                        "mb-0.5 text-[10px] font-semibold uppercase tracking-wide",
                        m.direction === "Outbound"
                          ? "text-brand-100"
                          : "text-zinc-400",
                      )}
                    >
                      template · {m.template_name}
                    </p>
                  )}
                  <p className="whitespace-pre-wrap">{m.content}</p>
                  <p
                    className={cn(
                      "mt-1 text-right text-[10px]",
                      m.direction === "Outbound"
                        ? "text-brand-100"
                        : "text-zinc-400",
                    )}
                  >
                    {fmtTime(m.creation)}
                    {m.direction === "Outbound" && ` · ${m.status}`}
                  </p>
                  {m.status === "Failed" && m.error && (
                    <p className="mt-0.5 text-[11px] text-rose-200">{m.error}</p>
                  )}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
            <div className="border-t border-zinc-100 p-3">
              {!sessionOpen && (
                <p className="mb-2 text-xs text-amber-700">
                  No guest message in the last 24 hours - WhatsApp only
                  delivers templates outside the session window. A guest
                  writing to you reopens it.
                </p>
              )}
              {error && <p className="mb-2 text-xs text-rose-600">{error}</p>}
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded-xl border border-zinc-300 bg-white px-3.5 py-2 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
                  placeholder="Reply to the guest…"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendReply()}
                  disabled={!active}
                />
                <Button disabled={busy || !draft.trim() || !active} onClick={sendReply}>
                  <Send className="size-4" aria-hidden />
                  Send
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
