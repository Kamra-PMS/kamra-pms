/*  Special instructions on a stay - one line per department (a VIP amenity
    for Housekeeping, a 6am wake-up for the Front Desk), Open until someone
    marks it Done. Reads and writes go through the role-gated
    stay_instructions endpoints, never a raw doctype save. */

import { useCallback, useEffect, useState } from "react"
import { Check, ListChecks, RotateCcw } from "lucide-react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "./ui/button"
import { cn } from "../lib/utils"

const DEPARTMENTS = ["Housekeeping", "Front Desk", "F&B", "Concierge", "Transport", "Maintenance", "Security"]

interface Instruction {
  name: string
  department: string
  instruction: string
  status: "Open" | "Done"
  done_by: string | null
  done_on: string | null
}

export default function StayInstructions({
  reservation,
  canAdd = true,
}: {
  reservation: string
  canAdd?: boolean
}) {
  const [rows, setRows] = useState<Instruction[] | null>(null)
  const [dept, setDept] = useState(DEPARTMENTS[0])
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    call<Instruction[]>("kamra.api.stay_instructions", { reservation })
      .then((r) => {
        setRows(r)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
  }, [reservation])

  useEffect(load, [load])

  async function act(method: string, params: Record<string, unknown>) {
    setBusy(true)
    setError(null)
    try {
      setRows(await call<Instruction[]>(method, { reservation, ...params }))
      return true
    } catch (e) {
      setError(serverError(e))
      return false
    } finally {
      setBusy(false)
    }
  }

  const open = (rows ?? []).filter((r) => r.status === "Open").length

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-700">
        <ListChecks className="size-4 text-zinc-400" aria-hidden />
        Instructions
        {open > 0 && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
            {open} open
          </span>
        )}
      </div>

      {rows && rows.length === 0 && (
        <p className="text-sm text-zinc-400">No instructions on this stay.</p>
      )}
      {rows && rows.length > 0 && (
        <ul className="divide-y divide-zinc-100">
          {rows.map((r) => (
            <li key={r.name} className="flex items-start gap-3 py-2">
              <span className="mt-0.5 shrink-0 rounded bg-zinc-100 px-1.5 py-0.5 text-[11px] font-medium text-zinc-600">
                {r.department}
              </span>
              <div className="min-w-0 flex-1">
                <p
                  className={cn(
                    "whitespace-pre-wrap text-sm",
                    r.status === "Done" ? "text-zinc-400 line-through" : "text-zinc-800",
                  )}
                >
                  {r.instruction}
                </p>
                {r.status === "Done" && r.done_by && (
                  <p className="text-xs text-zinc-400">
                    Done by {r.done_by}
                    {r.done_on ? ` · ${String(r.done_on).slice(0, 16)}` : ""}
                  </p>
                )}
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  act("kamra.api.set_stay_instruction_status", {
                    row: r.name,
                    status: r.status === "Done" ? "Open" : "Done",
                  })
                }
                className="inline-flex shrink-0 items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-600 hover:bg-zinc-50"
              >
                {r.status === "Done" ? (
                  <>
                    <RotateCcw className="size-3" aria-hidden /> Reopen
                  </>
                ) : (
                  <>
                    <Check className="size-3" aria-hidden /> Done
                  </>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      {canAdd && (
        <div className="mt-3 flex flex-wrap gap-2">
          <select
            aria-label="For"
            value={dept}
            onChange={(e) => setDept(e.target.value)}
            className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm"
          >
            {DEPARTMENTS.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. Fruit basket before arrival"
            className="min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
          />
          <Button
            variant="outline"
            disabled={busy || !text.trim()}
            onClick={async () => {
              if (await act("kamra.api.add_stay_instruction", { department: dept, instruction: text.trim() }))
                setText("")
            }}
          >
            Add
          </Button>
        </div>
      )}
      {error && <p className="mt-2 text-sm text-rose-700">{error}</p>}
    </div>
  )
}
