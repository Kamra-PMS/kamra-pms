import { useCallback, useEffect, useState } from "react"
import { BedDouble, Camera, LogOut, Plane, RefreshCw, Star, Clock, PackageSearch, X } from "lucide-react"
import {
  call,
  getCurrentProperty,
  isNetworkError,
  logout,
  uploadTo,
  whoami,
} from "../lib/api"
import { subscribeRealtime } from "../lib/realtime"
import { Badge } from "../components/ui/badge"
import { cn } from "../lib/utils"
import { asset } from "../lib/asset"
import Login from "./Login"
import HkLaundry from "./HkLaundry"
import { serverError } from "../lib/resource"
import { cur } from "../lib/money"
import { useT } from "../lib/i18n"

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
  assigned_to_user: string | null
  assignment_status: "Unassigned" | "Assigned" | "Accepted"
  mine: boolean
  claimable: boolean
  vip: number
  special_requests: string | null
  eta: string | null
  overdue: boolean
  media: string[]
}

const isVideo = (url: string) => /\.(mp4|mov|webm|m4v|3gp|avi)$/i.test(url)

interface HkRoom {
  name: string
  room_number: string
  housekeeping_status: "Clean" | "Dirty" | "Inspected" | "Ready" | "Out of Order"
  occupancy_status: "Vacant" | "Occupied"
  arrival_today: boolean
  vip?: number
  in_house_guest?: string
  arriving_guest?: string
  special_requests?: string
  eta?: string
  departure_today?: number
}

const hkTone: Record<HkRoom["housekeeping_status"], string> = {
  Clean: "border-emerald-300 bg-emerald-50 text-emerald-900",
  Ready: "border-emerald-400 bg-emerald-100 text-emerald-950",
  Inspected: "border-sky-300 bg-sky-50 text-sky-900",
  Dirty: "border-amber-300 bg-amber-50 text-amber-900",
  "Out of Order": "border-rose-300 bg-rose-50 text-rose-900",
}

export default function HkApp() {
  const { t } = useT()
  const [auth, setAuth] = useState<"loading" | "anon" | "ok">("loading")
  const [data, setData] = useState<{ tasks: HkTask[]; rooms: HkRoom[] } | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [view, setView] = useState<"mine" | "pool" | "rooms" | "laundry">("mine")
  const [rejecting, setRejecting] = useState<string | null>(null)
  const [reason, setReason] = useState("")
  const [logItem, setLogItem] = useState<{ desc: string; condition: string; room: string } | null>(null)
  const [logMsg, setLogMsg] = useState<string | null>(null)
  const [charge, setCharge] = useState<{ room: string; num: string; type: string; desc: string; amount: string } | null>(null)
  const [chargeMsg, setChargeMsg] = useState<string | null>(null)

  const checkAuth = () =>
    whoami()
      .then((w) => setAuth(w.user === "Guest" ? "anon" : "ok"))
      .catch((e) => {
        // an unreachable server is not a sign-out - keep trying quietly
        if (isNetworkError(e)) setTimeout(checkAuth, 4000)
        else setAuth("anon")
      })

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
    const unsub = subscribeRealtime(load) // live room/task updates
    const t = setInterval(load, 20_000) // safety net
    return () => { unsub(); clearInterval(t) }
  }, [auth, load])

  async function run(task: string, method: string, params: Record<string, unknown> = {}) {
    setBusy(task)
    try {
      await call(method, { task, ...params })
      load()
    } finally {
      setBusy(null)
    }
  }

  // proof-of-clean: attach photos/videos to the task from the phone camera/gallery
  async function addMedia(task: string, files: FileList | null) {
    if (!files || !files.length) return
    setBusy(task)
    try {
      for (const f of Array.from(files)) {
        await uploadTo("kamra.api.hk_upload_media", f, { task })
      }
      load()
    } catch (e) {
      alert(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  // remove a photo/video from the task
  async function removeMedia(task: string, url: string) {
    if (!confirm("Remove this photo/video?")) return
    setBusy(task)
    try {
      await call("kamra.api.hk_delete_media", { task, file_url: url })
      load()
    } catch (e) {
      alert(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  if (auth === "loading")
    return <p className="py-20 text-center text-zinc-400">{t("Loading…")}</p>
  if (auth === "anon") return <Login onSuccess={checkAuth} />

  const mine = (data?.tasks ?? []).filter((t) => t.mine)
  const pool = (data?.tasks ?? []).filter((t) => t.claimable)

  const TaskCard = ({ task }: { task: HkTask }) => (
    <li className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <span className="text-3xl font-bold tabular-nums">{task.room_number}</span>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 font-medium">
            {task.vip ? (
              <Star className="size-4 shrink-0 fill-amber-400 text-amber-400" aria-label={t("VIP")} />
            ) : null}
            {task.task_type}
          </p>
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
            <Badge tone={task.priority === "Urgent" ? "rose" : task.priority === "High" ? "amber" : "zinc"}>
              {t(task.priority)}
            </Badge>
            {task.arrival_today && (
              <Badge tone="brand">
                <Plane className="mr-1 size-3" aria-hidden />
                {task.eta ? t("arrival {eta}", { eta: task.eta }) : t("arrival today")}
              </Badge>
            )}
            {task.assignment_status === "Assigned" && task.mine && (
              <Badge tone="amber">{t("assigned to you")}</Badge>
            )}
            {task.overdue && <Badge tone="rose">{t("overdue")}</Badge>}
          </div>
        </div>
      </div>
      {task.special_requests && (
        <p className="mt-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-sm text-amber-800">
          {t("Guest request: {req}", { req: task.special_requests })}
        </p>
      )}
      {task.notes && <p className="mt-2 text-sm text-zinc-500">{task.notes}</p>}

      {task.claimable ? (
        <button
          disabled={busy === task.name}
          onClick={() => run(task.name, "kamra.api.hk_claim_task")}
          className="mt-3 w-full rounded-xl bg-brand-600 py-3 text-base font-semibold text-white active:bg-brand-700"
        >
          {t("Take this room")}
        </button>
      ) : task.assignment_status === "Assigned" ? (
        rejecting === task.name ? (
          <div className="mt-3 space-y-2">
            <input
              className="w-full rounded-xl border border-zinc-300 px-3 py-2.5 text-base"
              placeholder={t("Reason (optional)")}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                className="flex-1 rounded-xl border border-zinc-300 py-3 text-base font-semibold text-zinc-600"
                onClick={() => { setRejecting(null); setReason("") }}
              >
                {t("Keep")}
              </button>
              <button
                disabled={busy === task.name}
                onClick={() =>
                  run(task.name, "kamra.api.hk_reject_task", { reason }).then(() => {
                    setRejecting(null)
                    setReason("")
                  })
                }
                className="flex-1 rounded-xl bg-rose-600 py-3 text-base font-semibold text-white"
              >
                {t("Send back")}
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-3 flex gap-2">
            <button
              disabled={busy === task.name}
              onClick={() => setRejecting(task.name)}
              className="flex-1 rounded-xl border border-zinc-300 py-3 text-base font-semibold text-zinc-600 active:bg-zinc-100"
            >
              {t("Decline")}
            </button>
            <button
              disabled={busy === task.name}
              onClick={() => run(task.name, "kamra.api.hk_accept_task")}
              className="flex-1 rounded-xl bg-brand-600 py-3 text-base font-semibold text-white active:bg-brand-700"
            >
              {t("Accept")}
            </button>
          </div>
        )
      ) : (
        // accepted/mine: work it
        <>
          {/* proof of clean: capture photos/videos before marking Done */}
          <div className="mt-3">
            {(task.media ?? []).length > 0 && (
              <div className="mb-2 flex gap-2 overflow-x-auto">
                {(task.media ?? []).map((url) => (
                  <div key={url} className="relative shrink-0">
                    {isVideo(url) ? (
                      <video
                        src={url}
                        muted
                        playsInline
                        controls
                        className="size-16 rounded-lg bg-zinc-100 object-cover"
                      />
                    ) : (
                      <img
                        src={url}
                        alt={t("Room clean")}
                        className="size-16 rounded-lg object-cover"
                      />
                    )}
                    <button
                      type="button"
                      aria-label={t("Remove")}
                      disabled={busy === task.name}
                      onClick={() => removeMedia(task.name, url)}
                      className="absolute -right-1.5 -top-1.5 flex size-5 items-center justify-center rounded-full bg-rose-600 text-white shadow active:bg-rose-700"
                    >
                      <X className="size-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-zinc-300 py-2.5 text-sm font-medium text-zinc-600 active:bg-zinc-100">
              <Camera className="size-4" aria-hidden />
              {(task.media ?? []).length ? t("Add another photo / video") : t("Add photo / video")}
              <input
                type="file"
                accept="image/*,video/*"
                capture="environment"
                multiple
                hidden
                disabled={busy === task.name}
                onChange={(e) => {
                  addMedia(task.name, e.target.files)
                  e.target.value = ""
                }}
              />
            </label>
          </div>
          <div className="mt-2 flex gap-2">
            {task.status === "Pending" ? (
              <button
                disabled={busy === task.name}
                onClick={() => run(task.name, "kamra.api.hk_update_task", { status: "In Progress" })}
                className="flex-1 rounded-xl border border-zinc-300 py-3 text-base font-semibold text-zinc-700 active:bg-zinc-100"
              >
                {t("Start")}
              </button>
            ) : (
              <span className="flex flex-1 items-center justify-center rounded-xl bg-sky-50 py-3 text-base font-medium text-sky-700">
                {t("In progress…")}
              </span>
            )}
            <button
              disabled={busy === task.name}
              onClick={() => run(task.name, "kamra.api.hk_update_task", { status: "Done" })}
              className="flex-1 rounded-xl bg-brand-600 py-3 text-base font-semibold text-white active:bg-brand-700"
            >
              {t("Done ✓")}
            </button>
          </div>
        </>
      )}
    </li>
  )

  return (
    <div className="min-h-screen bg-zinc-50 pb-20">
      <header className="sticky top-0 z-40 flex items-center gap-2 border-b border-zinc-200 bg-white px-4 py-3">
        <img src={asset("kamra-mark.svg")} alt="" className="size-6" aria-hidden />
        <span className="font-semibold">{t("Housekeeping")}</span>
        <span className="ml-auto flex items-center gap-3">
          <button
            onClick={() => { setLogItem({ desc: "", condition: "Found", room: "" }); setLogMsg(null) }}
            aria-label={t("Log a lost or found item")}
          >
            <PackageSearch className="size-5 text-zinc-400" />
          </button>
          <button onClick={load} aria-label={t("Refresh")}>
            <RefreshCw className="size-5 text-zinc-400" />
          </button>
          <button
            onClick={() => logout().then(() => setAuth("anon"))}
            aria-label={t("Sign out")}
          >
            <LogOut className="size-5 text-zinc-400" />
          </button>
        </span>
      </header>

      <main className="mx-auto max-w-lg px-3 py-4">
        {view === "mine" && (
          <>
            <p className="mb-3 px-1 text-sm text-zinc-500">
              {t("{n} task{s} for you - arrivals first", {
                n: mine.length,
                s: mine.length === 1 ? "" : "s",
              })}
            </p>
            <ul className="space-y-3">
              {mine.map((task) => <TaskCard key={task.name} task={task} />)}
              {mine.length === 0 && (
                <li className="rounded-2xl border border-dashed border-zinc-300 p-8 text-center text-zinc-400">
                  {t("Nothing assigned to you. Check")}{" "}
                  <button className="font-semibold text-brand-700" onClick={() => setView("pool")}>
                    {t("Available")}
                  </button>{" "}
                  {t("to pick up a room.")}
                </li>
              )}
            </ul>
          </>
        )}

        {view === "pool" && (
          <>
            <p className="mb-3 px-1 text-sm text-zinc-500">
              {t("{n} unassigned - take one to add it to your list", { n: pool.length })}
            </p>
            <ul className="space-y-3">
              {pool.map((task) => <TaskCard key={task.name} task={task} />)}
              {pool.length === 0 && (
                <li className="rounded-2xl border border-dashed border-zinc-300 p-8 text-center text-zinc-400">
                  {t("No unassigned rooms right now.")}
                </li>
              )}
            </ul>
          </>
        )}

        {view === "rooms" && (
          <div className="grid grid-cols-3 gap-2">
            {(data?.rooms ?? []).map((r) => (
              <button
                key={r.name}
                disabled={r.occupancy_status !== "Occupied"}
                onClick={() => {
                  setCharge({ room: r.name, num: r.room_number, type: "Minibar", desc: "", amount: "" })
                  setChargeMsg(null)
                }}
                className={cn(
                  "relative rounded-xl border p-3 text-center",
                  hkTone[r.housekeeping_status],
                  r.occupancy_status === "Occupied" ? "active:brightness-95" : "cursor-default",
                )}
              >
                {r.vip ? (
                  <Star className="absolute right-1.5 top-1.5 size-3.5 fill-amber-400 text-amber-400" aria-label="VIP" />
                ) : null}
                <div className="flex items-center justify-center gap-1 text-xl font-bold">
                  {r.room_number}
                  {r.occupancy_status === "Occupied" && (
                    <BedDouble className="size-4" aria-hidden />
                  )}
                </div>
                <div className="mt-0.5 text-[10px] font-medium uppercase tracking-wide opacity-70">
                  {t(r.housekeeping_status)}
                </div>
                <div className="mt-1 flex items-center justify-center gap-1">
                  {r.arrival_today && (
                    <span className="inline-flex items-center gap-0.5 text-[9px] font-medium">
                      <Plane className="size-3" aria-label="Arrival today" />
                      {r.eta || ""}
                    </span>
                  )}
                  {r.departure_today ? (
                    <Clock className="size-3" aria-label="Departure today" />
                  ) : null}
                </div>
              </button>
            ))}
          </div>
        )}
        {view === "rooms" && (
          <p className="mt-3 text-center text-xs text-zinc-400">
            {t("Tap an occupied room to post minibar or laundry.")}
          </p>
        )}

        {view === "laundry" && <HkLaundry rooms={data?.rooms ?? []} />}
      </main>

      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-zinc-200 bg-white">
        {(
          [
            ["mine", t("My Tasks{n}", { n: mine.length ? ` (${mine.length})` : "" })],
            ["pool", t("Available{n}", { n: pool.length ? ` (${pool.length})` : "" })],
            ["rooms", t("Rooms")],
            ["laundry", t("Laundry")],
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

      {logItem && (
        <div
          className="fixed inset-0 z-50 flex items-end bg-black/40"
          onClick={() => setLogItem(null)}
        >
          <div
            className="w-full rounded-t-2xl bg-white p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="mb-3 text-lg font-semibold">{t("Log an item")}</h2>
            {logMsg ? (
              <div className="space-y-3">
                <p className="rounded-xl bg-emerald-50 px-3 py-3 text-emerald-800">
                  {logMsg}
                </p>
                <button
                  className="w-full rounded-xl bg-brand-600 py-3 text-base font-semibold text-white"
                  onClick={() => setLogItem(null)}
                >
                  {t("Done")}
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  {["Found", "Missing", "Damaged"].map((c) => (
                    <button
                      key={c}
                      onClick={() => setLogItem({ ...logItem, condition: c })}
                      className={cn(
                        "rounded-xl border py-2.5 text-sm font-semibold",
                        logItem.condition === c
                          ? "border-brand-500 bg-brand-50 text-brand-700"
                          : "border-zinc-300 text-zinc-600",
                      )}
                    >
                      {t(c)}
                    </button>
                  ))}
                </div>
                <input
                  className="w-full rounded-xl border border-zinc-300 px-3 py-3 text-base"
                  placeholder={t("What is it? (e.g. black umbrella)")}
                  value={logItem.desc}
                  autoFocus
                  onChange={(e) => setLogItem({ ...logItem, desc: e.target.value })}
                />
                <select
                  className="w-full rounded-xl border border-zinc-300 px-3 py-3 text-base"
                  value={logItem.room}
                  onChange={(e) => setLogItem({ ...logItem, room: e.target.value })}
                >
                  <option value="">{t("Room (optional)")}</option>
                  {(data?.rooms ?? []).map((r) => (
                    <option key={r.name} value={r.name}>{r.room_number}</option>
                  ))}
                </select>
                <div className="flex gap-2">
                  <button
                    className="flex-1 rounded-xl border border-zinc-300 py-3 text-base font-semibold text-zinc-600"
                    onClick={() => setLogItem(null)}
                  >
                    {t("Cancel")}
                  </button>
                  <button
                    disabled={!logItem.desc.trim() || busy === "log"}
                    className="flex-1 rounded-xl bg-brand-600 py-3 text-base font-semibold text-white disabled:opacity-50"
                    onClick={async () => {
                      setBusy("log")
                      try {
                        await call("kamra.api.hk_log_item", {
                          property: getCurrentProperty(),
                          item_description: logItem.desc.trim(),
                          condition: logItem.condition,
                          room: logItem.room || null,
                        })
                        setLogMsg(t("Logged {condition}: {desc}", {
                          condition: logItem.condition.toLowerCase(),
                          desc: logItem.desc.trim(),
                        }))
                      } finally {
                        setBusy(null)
                      }
                    }}
                  >
                    {t("Log it")}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {charge && (
        <div
          className="fixed inset-0 z-50 flex items-end bg-black/40"
          onClick={() => setCharge(null)}
        >
          <div
            className="w-full rounded-t-2xl bg-white p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="mb-3 text-lg font-semibold">
              {t("Post to room {num}", { num: charge.num })}
            </h2>
            {chargeMsg ? (
              <div className="space-y-3">
                <p className="rounded-xl bg-emerald-50 px-3 py-3 text-emerald-800">
                  {chargeMsg}
                </p>
                <button
                  className="w-full rounded-xl bg-brand-600 py-3 text-base font-semibold text-white"
                  onClick={() => setCharge(null)}
                >
                  Done
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  {["Minibar", "Laundry"].map((type) => (
                    <button
                      key={type}
                      onClick={() => setCharge({ ...charge, type: type })}
                      className={cn(
                        "rounded-xl border py-2.5 text-sm font-semibold",
                        charge.type === type
                          ? "border-brand-500 bg-brand-50 text-brand-700"
                          : "border-zinc-300 text-zinc-600",
                      )}
                    >
                      {t(type)}
                    </button>
                  ))}
                </div>
                <input
                  className="w-full rounded-xl border border-zinc-300 px-3 py-3 text-base"
                  placeholder={charge.type === "Minibar" ? t("e.g. 2 cola, 1 water") : t("e.g. 3 shirts pressed")}
                  value={charge.desc}
                  autoFocus
                  onChange={(e) => setCharge({ ...charge, desc: e.target.value })}
                />
                <input
                  className="w-full rounded-xl border border-zinc-300 px-3 py-3 text-base"
                  placeholder={t("Amount {cur}", { cur: cur() })}
                  inputMode="numeric"
                  value={charge.amount}
                  onChange={(e) => setCharge({ ...charge, amount: e.target.value })}
                />
                <div className="flex gap-2">
                  <button
                    className="flex-1 rounded-xl border border-zinc-300 py-3 text-base font-semibold text-zinc-600"
                    onClick={() => setCharge(null)}
                  >
                    {t("Cancel")}
                  </button>
                  <button
                    disabled={!charge.desc.trim() || !Number(charge.amount) || busy === "charge"}
                    className="flex-1 rounded-xl bg-brand-600 py-3 text-base font-semibold text-white disabled:opacity-50"
                    onClick={async () => {
                      setBusy("charge")
                      try {
                        await call("kamra.api.hk_post_consumable", {
                          room: charge.room,
                          charge_type: charge.type,
                          description: charge.desc.trim(),
                          amount: Number(charge.amount),
                        })
                        setChargeMsg(t("Posted {amount} {type} to room {num}.", {
                          amount: `${cur()}${charge.amount}`,
                          type: charge.type.toLowerCase(),
                          num: charge.num,
                        }))
                        load()
                      } catch (e) {
                        setChargeMsg(serverError(e))
                      } finally {
                        setBusy(null)
                      }
                    }}
                  >
                    {t("Post {amount}", { amount: `${cur()}${charge.amount || "0"}` })}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
