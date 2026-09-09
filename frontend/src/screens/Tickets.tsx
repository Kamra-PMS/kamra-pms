import { useCallback, useEffect, useState } from "react"
import { useRealtime } from "../lib/realtime"
import { AlertTriangle, Plus } from "lucide-react"
import { Sheet } from "../components/ui/sheet"
import { call, getCurrentProperty } from "../lib/api"
import { listResource, serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"
import { cn } from "../lib/utils"
import { useT } from "../lib/i18n"

interface Ticket {
  name: string
  subject: string
  category: string
  priority: string
  status: string
  source: string
  room: string | null
  guest_name: string | null
  due_by: string
  breached: 0 | 1
  overdue: boolean
  creation: string
}

const CATEGORIES = [
  "Housekeeping", "Room Service", "Maintenance", "Front Desk",
  "Concierge", "Complaint", "Other",
]

const prioTone: Record<string, "zinc" | "sky" | "amber" | "rose"> = {
  Low: "zinc",
  Medium: "sky",
  High: "amber",
  Urgent: "rose",
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function Tickets() {
  const { t } = useT()
  const [rows, setRows] = useState<Ticket[]>([])
  const [showClosed, setShowClosed] = useState(false)
  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rooms, setRooms] = useState<string[]>([])
  const [form, setForm] = useState({
    subject: "", category: "Housekeeping", priority: "Medium",
    room: "", description: "",
  })

  const load = useCallback(() => {
    call<Ticket[]>("kamra.api.tickets_list", {
      property: getCurrentProperty(),
      show_closed: showClosed ? 1 : 0,
    }).then(setRows)
  }, [showClosed])

  useEffect(load, [load])
  useRealtime(load)
  useEffect(() => {
    listResource("Room", { fields: ["name"], orderBy: "room_number asc" })
      .then((r) => setRooms(r.map((x) => x.name)))
  }, [])

  async function advance(ticket: string, status: string) {
    setBusy(ticket)
    setError(null)
    try {
      await call("kamra.api.advance_ticket", { ticket, status })
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  async function create() {
    setBusy("new")
    setError(null)
    try {
      await call("kamra.api.create_ticket", {
        property: getCurrentProperty(),
        subject: form.subject,
        category: form.category,
        priority: form.priority,
        room: form.room || undefined,
        description: form.description || undefined,
      })
      setCreating(false)
      setForm({ subject: "", category: "Housekeeping", priority: "Medium", room: "", description: "" })
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t("Service Tickets")}</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            {t("Guest requests with SLA - Urgent 15m · High 30m · Medium 1h · Low 4h")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-zinc-500">
            <input
              type="checkbox"
              className="size-3.5 accent-brand-600"
              checked={showClosed}
              onChange={(e) => setShowClosed(e.target.checked)}
            />
            {t("Show closed")}
          </label>
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" aria-hidden />
            {t("New ticket")}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}
        <ul className="divide-y divide-zinc-100">
          {rows.map((row) => (
            <li key={row.name} className="flex flex-wrap items-center gap-3 py-3">
              <div
                className={cn(
                  "min-w-0 flex-1",
                  row.status === "Resolved" && "opacity-60",
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{row.subject}</span>
                  <Badge tone={prioTone[row.priority] ?? "zinc"}>
                    {t(row.priority)}
                  </Badge>
                  <Badge tone="zinc">{t(row.category)}</Badge>
                  {row.source !== "Manual" && (
                    <Badge tone="brand">{t(row.source)}</Badge>
                  )}
                  {row.overdue && (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-600">
                      <AlertTriangle className="size-3.5" aria-hidden />
                      {t("overdue")}
                    </span>
                  )}
                  {Boolean(row.breached) && row.status === "Resolved" && (
                    <span className="text-xs text-rose-400">{t("SLA breached")}</span>
                  )}
                </div>
                <div className="mt-0.5 text-xs text-zinc-500">
                  {row.name}
                  {row.room && ` · ${t("Room {n}", { n: row.room.split("-").pop() ?? "" })}`}
                  {row.guest_name && ` · ${row.guest_name}`}
                  {" · "}{t("due")}{" "}
                  {row.due_by?.slice(5, 16)}
                </div>
              </div>
              <div className="flex gap-2">
                {row.status === "Open" && (
                  <Button
                    variant="outline"
                    disabled={busy === row.name}
                    onClick={() => advance(row.name, "In Progress")}
                  >
                    {t("Start")}
                  </Button>
                )}
                {(row.status === "Open" || row.status === "In Progress") && (
                  <Button
                    disabled={busy === row.name}
                    onClick={() => advance(row.name, "Resolved")}
                  >
                    {t("Resolve")}
                  </Button>
                )}
                {row.status === "Resolved" && (
                  <Badge tone="green">{t("Resolved")}</Badge>
                )}
                {(row.status === "Closed" || row.status === "Cancelled") && (
                  <Badge tone="zinc">{t(row.status)}</Badge>
                )}
              </div>
            </li>
          ))}
          {rows.length === 0 && (
            <li className="py-8 text-center text-sm text-zinc-400">
              {t("No open tickets - a quiet day at the desk.")}
            </li>
          )}
        </ul>
      </CardContent>

      {creating && (
        <Sheet
          title={t("New ticket")}
          description={t("Guest request - SLA starts from priority at creation")}
          onClose={() => setCreating(false)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreating(false)}>
                {t("Cancel")}
              </Button>
              <Button
                disabled={busy === "new" || !form.subject}
                onClick={create}
              >
                {t("Create ticket")}
              </Button>
            </div>
          }
        >
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                {t("Subject")}
              </span>
              <input
                className={inputCls}
                placeholder={t("What does the guest need?")}
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                autoFocus
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                  {t("Category")}
                </span>
                <select
                  className={inputCls}
                  value={form.category}
                  onChange={(e) =>
                    setForm({ ...form, category: e.target.value })
                  }
                >
                  {CATEGORIES.map((c) => (
                    <option key={c}>{t(c)}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                  {t("Priority")}
                </span>
                <select
                  className={inputCls}
                  value={form.priority}
                  onChange={(e) =>
                    setForm({ ...form, priority: e.target.value })
                  }
                >
                  {["Low", "Medium", "High", "Urgent"].map((p) => (
                    <option key={p}>{t(p)}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                {t("Room")}
              </span>
              <select
                className={inputCls}
                value={form.room}
                onChange={(e) => setForm({ ...form, room: e.target.value })}
              >
                <option value="">{t("No room")}</option>
                {rooms.map((r) => (
                  <option key={r} value={r}>
                    {t("Room {n}", { n: r.split("-").pop() ?? "" })}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                {t("Details")}
              </span>
              <textarea
                className={inputCls}
                rows={3}
                placeholder={t("Anything the staff should know (optional)")}
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
              />
            </label>
          </div>
        </Sheet>
      )}
    </Card>
  )
}
