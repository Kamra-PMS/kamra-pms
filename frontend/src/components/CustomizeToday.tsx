/*  Customize Today: show or hide each panel, move it up or down, or to the
    other column. Saved for this person on the server (it follows them to
    any device). A Hotel Admin can also make the layout the hotel default,
    which everyone sees until they customise their own. */

import { useState } from "react"
import { ArrowDown, ArrowLeftRight, ArrowUp, Eye, EyeOff } from "lucide-react"
import {
  resetTodayLayout,
  saveTodayLayout,
  saveTodayLayoutDefault,
  type TodayLayout,
  type TodayLayoutInfo,
  type WidgetId,
} from "../lib/rooms"
import { serverError } from "../lib/resource"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Sheet } from "./ui/sheet"
import { Button } from "./ui/button"

export const WIDGET_LABEL: Record<WidgetId, string> = {
  kpis: "Key numbers",
  booking_requests: "Booking requests",
  arrivals: "Arrivals",
  departures: "Departures",
  room_board: "Room board",
  in_house: "In-house guests",
  housekeeping: "Housekeeping",
  open_tasks: "Open tasks",
}

type Col = "top" | "left" | "right"

export default function CustomizeToday(props: {
  info: TodayLayoutInfo
  current: TodayLayout
  onClose: () => void
  onSaved: (info: TodayLayoutInfo) => void
}) {
  const { t } = useT()
  const [draft, setDraft] = useState<TodayLayout>(() => structuredClone(props.current))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  const hidden = new Set(draft.hidden)

  function toggle(id: WidgetId) {
    setDraft((d) => ({
      ...d,
      hidden: d.hidden.includes(id) ? d.hidden.filter((x) => x !== id) : [...d.hidden, id],
    }))
  }

  function move(col: Col, i: number, by: -1 | 1) {
    setDraft((d) => {
      const list = [...d[col]]
      const j = i + by
      if (j < 0 || j >= list.length) return d
      ;[list[i], list[j]] = [list[j], list[i]]
      return { ...d, [col]: list }
    })
  }

  function switchColumn(col: "left" | "right", i: number) {
    setDraft((d) => {
      const other = col === "left" ? "right" : "left"
      const id = d[col][i]
      return {
        ...d,
        [col]: d[col].filter((_, k) => k !== i),
        [other]: [...d[other], id],
      }
    })
  }

  async function run(fn: () => Promise<TodayLayoutInfo>, done: string, close = true) {
    setBusy(true)
    setError(null)
    setNote(null)
    try {
      const info = await fn()
      props.onSaved(info)
      if (close) props.onClose()
      else {
        setDraft(structuredClone(info.layout))
        setNote(done)
      }
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const sourceText =
    props.info.source === "user"
      ? t("You are using your own layout.")
      : props.info.source === "property"
        ? t("You are using the hotel's default layout.")
        : t("You are using the standard layout.")

  const column = (col: Col, title: string) => (
    <section className="mb-5">
      <h3 className="mb-2 text-sm font-semibold text-zinc-800">{title}</h3>
      <ul className="space-y-2">
        {draft[col].map((id, i) => {
          const off = hidden.has(id)
          return (
            <li
              key={id}
              className={cn(
                "flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2",
                off ? "border-dashed border-zinc-300 bg-zinc-50" : "border-zinc-200 bg-white",
              )}
            >
              <button
                type="button"
                onClick={() => toggle(id)}
                aria-pressed={!off}
                className={cn(
                  "inline-flex min-h-11 min-w-0 flex-1 items-center gap-2 text-start text-base font-medium",
                  off ? "text-zinc-400" : "text-zinc-800",
                )}
              >
                {off ? (
                  <EyeOff className="size-5 shrink-0" aria-hidden />
                ) : (
                  <Eye className="size-5 shrink-0 text-brand-700" aria-hidden />
                )}
                <span className="truncate">{t(WIDGET_LABEL[id])}</span>
                <span className="ms-auto hidden shrink-0 text-xs font-normal sm:inline">
                  {off ? t("Hidden") : t("Shown")}
                </span>
              </button>
              {col !== "top" && (
                <span className="flex shrink-0 items-center gap-1">
                  <IconBtn
                    label={t("Move up")}
                    disabled={i === 0}
                    onClick={() => move(col, i, -1)}
                  >
                    <ArrowUp className="size-4" />
                  </IconBtn>
                  <IconBtn
                    label={t("Move down")}
                    disabled={i === draft[col].length - 1}
                    onClick={() => move(col, i, 1)}
                  >
                    <ArrowDown className="size-4" />
                  </IconBtn>
                  <IconBtn
                    label={col === "left" ? t("Move to the wide column") : t("Move to the narrow column")}
                    onClick={() => switchColumn(col, i)}
                  >
                    <ArrowLeftRight className="size-4" />
                  </IconBtn>
                </span>
              )}
            </li>
          )
        })}
        {draft[col].length === 0 && (
          <li className="rounded-xl border border-dashed border-zinc-300 px-3 py-3 text-sm text-zinc-400">
            {t("Nothing in this column.")}
          </li>
        )}
      </ul>
    </section>
  )

  return (
    <Sheet
      title={t("Customize Today")}
      description={t("Tap a panel to show or hide it. Use the arrows to change the order.")}
      onClose={props.onClose}
      footer={
        <div className="flex flex-wrap items-center gap-2">
          <Button
            className="min-h-11 px-4"
            disabled={busy}
            onClick={() => run(() => saveTodayLayout(draft), t("Saved."))}
          >
            {t("Save for me")}
          </Button>
          <Button
            variant="outline"
            className="min-h-11"
            disabled={busy}
            onClick={() => run(() => resetTodayLayout(), t("Back to the hotel default."), false)}
          >
            {t("Use the hotel default")}
          </Button>
          <Button variant="ghost" className="min-h-11" onClick={props.onClose}>
            {t("Cancel")}
          </Button>
        </div>
      }
    >
      <p className="mb-4 rounded-lg bg-zinc-50 px-3 py-2 text-sm text-zinc-600">{sourceText}</p>
      {error && (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}
      {note && (
        <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {note}
        </div>
      )}
      {column("top", t("Top of the page"))}
      {column("left", t("Narrow column"))}
      {column("right", t("Wide column"))}
      {props.info.can_set_default && (
        <section className="rounded-xl border border-zinc-200 p-3">
          <h3 className="text-sm font-semibold text-zinc-800">{t("Hotel default")}</h3>
          <p className="mt-1 text-sm text-zinc-500">
            {t("What everyone at this hotel sees until they customise their own Today.")}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              variant="outline"
              className="min-h-11"
              disabled={busy}
              onClick={() =>
                run(() => saveTodayLayoutDefault(draft), t("Saved as the hotel default."), false)
              }
            >
              {t("Make this the hotel default")}
            </Button>
            <Button
              variant="ghost"
              className="min-h-11"
              disabled={busy}
              onClick={() =>
                run(() => saveTodayLayoutDefault(null), t("The hotel default is the standard layout again."), false)
              }
            >
              {t("Reset the hotel default")}
            </Button>
          </div>
        </section>
      )}
    </Sheet>
  )
}

function IconBtn(props: {
  label: string
  disabled?: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-label={props.label}
      title={props.label}
      disabled={props.disabled}
      onClick={props.onClick}
      className="inline-flex size-11 items-center justify-center rounded-lg border border-zinc-200 text-zinc-600 hover:bg-zinc-50 disabled:opacity-30"
    >
      {props.children}
    </button>
  )
}
