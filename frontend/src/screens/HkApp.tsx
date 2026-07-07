import { useCallback, useEffect, useState } from "react"
import { BedDouble, LogOut, Plane, RefreshCw } from "lucide-react"
import {
  call,
  getCurrentProperty,
  isAuthError,
  logout,
  whoami,
} from "../lib/api"
import { Badge } from "../components/ui/badge"
import { cn } from "../lib/utils"
import { asset } from "../lib/asset"
import Login from "./Login"

/** The housekeeper's phone app - big targets, one thumb, zero training. */

interface HkTask {
  name: string
  room: string
  room_number: string
  task_type: string
  priority: string
  status: "Pending" | "In Progress"
  notes: string | null
  arrival_today: boolean
}

interface HkRoom {
  name: string
  room_number: string
  housekeeping_status: "Clean" | "Dirty" | "Inspected" | "Out of Order"
  occupancy_status: "Vacant" | "Occupied"
  arrival_today: boolean
}

const hkTone: Record<HkRoom["housekeeping_status"], string> = {
  Clean: "border-emerald-300 bg-emerald-50 text-emerald-900",
  Inspected: "border-sky-300 bg-sky-50 text-sky-900",
  Dirty: "border-amber-300 bg-amber-50 text-amber-900",
  "Out of Order": "border-rose-300 bg-rose-50 text-rose-900",
}

export default function HkApp() {
  const [auth, setAuth] = useState<"loading" | "anon" | "ok">("loading")
  const [data, setData] = useState<{ tasks: HkTask[]; rooms: HkRoom[] } | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [view, setView] = useState<"queue" | "rooms">("queue")

  const checkAuth = () =>
    whoami()
      .then((w) => setAuth(w.user === "Guest" ? "anon" : "ok"))
      .catch((e) => setAuth(isAuthError(e) ? "anon" : "anon"))

  useEffect(() => {
    checkAuth()
  }, [])

  const load = useCallback(() => {
    call<{ tasks: HkTask[]; rooms: HkRoom[] }>("kamra.api.hk_queue", {
      property: getCurrentProperty(),
    }).then(setData)
  }, [])

  useEffect(() => {
    if (auth !== "ok") return
    load()
    const t = setInterval(load, 20_000)
    return () => clearInterval(t)
  }, [auth, load])

  async function update(task: string, status: string) {
    setBusy(task)
    try {
      await call("kamra.api.hk_update_task", { task, status })
      load()
    } finally {
      setBusy(null)
    }
  }

  if (auth === "loading")
    return <p className="py-20 text-center text-zinc-400">Loading…</p>
  if (auth === "anon") return <Login onSuccess={checkAuth} />

  return (
    <div className="min-h-screen bg-zinc-50 pb-20">
      <header className="sticky top-0 z-40 flex items-center gap-2 border-b border-zinc-200 bg-white px-4 py-3">
        <img src={asset("kamra-mark.svg")} alt="" className="size-6" aria-hidden />
        <span className="font-semibold">Housekeeping</span>
        <span className="ml-auto flex items-center gap-3">
          <button onClick={load} aria-label="Refresh">
            <RefreshCw className="size-5 text-zinc-400" />
          </button>
          <button
            onClick={() => logout().then(() => setAuth("anon"))}
            aria-label="Sign out"
          >
            <LogOut className="size-5 text-zinc-400" />
          </button>
        </span>
      </header>

      <main className="mx-auto max-w-lg px-3 py-4">
        {view === "queue" && (
          <>
            <p className="mb-3 px-1 text-sm text-zinc-500">
              {data?.tasks.length ?? "…"} task
              {data?.tasks.length === 1 ? "" : "s"} - arrivals first
            </p>
            <ul className="space-y-3">
              {(data?.tasks ?? []).map((t) => (
                <li
                  key={t.name}
                  className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-3xl font-bold tabular-nums">
                      {t.room_number}
                    </span>
                    <div className="min-w-0">
                      <p className="font-medium">{t.task_type}</p>
                      <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                        <Badge
                          tone={
                            t.priority === "Urgent"
                              ? "rose"
                              : t.priority === "High"
                                ? "amber"
                                : "zinc"
                          }
                        >
                          {t.priority}
                        </Badge>
                        {t.arrival_today && (
                          <Badge tone="brand">
                            <Plane className="mr-1 size-3" aria-hidden />
                            arrival today
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  {t.notes && (
                    <p className="mt-2 text-sm text-zinc-500">{t.notes}</p>
                  )}
                  <div className="mt-3 flex gap-2">
                    {t.status === "Pending" ? (
                      <button
                        disabled={busy === t.name}
                        onClick={() => update(t.name, "In Progress")}
                        className="flex-1 rounded-xl border border-zinc-300 py-3 text-base font-semibold text-zinc-700 active:bg-zinc-100"
                      >
                        Start
                      </button>
                    ) : (
                      <span className="flex flex-1 items-center justify-center rounded-xl bg-sky-50 py-3 text-base font-medium text-sky-700">
                        In progress…
                      </span>
                    )}
                    <button
                      disabled={busy === t.name}
                      onClick={() => update(t.name, "Done")}
                      className="flex-1 rounded-xl bg-brand-600 py-3 text-base font-semibold text-white active:bg-brand-700"
                    >
                      Done ✓
                    </button>
                  </div>
                </li>
              ))}
              {data && data.tasks.length === 0 && (
                <li className="rounded-2xl border border-dashed border-zinc-300 p-8 text-center text-zinc-400">
                  All caught up - nothing in the queue.
                </li>
              )}
            </ul>
          </>
        )}

        {view === "rooms" && (
          <div className="grid grid-cols-3 gap-2">
            {(data?.rooms ?? []).map((r) => (
              <div
                key={r.name}
                className={cn(
                  "rounded-xl border p-3 text-center",
                  hkTone[r.housekeeping_status],
                )}
              >
                <div className="flex items-center justify-center gap-1 text-xl font-bold">
                  {r.room_number}
                  {r.occupancy_status === "Occupied" && (
                    <BedDouble className="size-4" aria-hidden />
                  )}
                </div>
                <div className="mt-0.5 text-[10px] font-medium uppercase tracking-wide opacity-70">
                  {r.housekeeping_status}
                </div>
                {r.arrival_today && (
                  <Plane className="mx-auto mt-1 size-3.5" aria-label="Arrival today" />
                )}
              </div>
            ))}
          </div>
        )}
      </main>

      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-2 border-t border-zinc-200 bg-white">
        {(
          [
            ["queue", "My Queue"],
            ["rooms", "Rooms"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setView(key)}
            className={cn(
              "py-3.5 text-sm font-semibold",
              view === key ? "text-brand-700" : "text-zinc-400",
            )}
          >
            {label}
          </button>
        ))}
      </nav>
    </div>
  )
}
