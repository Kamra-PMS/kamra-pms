import { useCallback, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Mail, Plus, Printer, Trash2 } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { cur, moneyLocale } from "../lib/money"
import { useT, t as translate } from "../lib/i18n"
import { useAuth } from "../lib/auth"

const VOID_REPORT_ROLES = ["Finance", "Hotel Admin", "System Manager", "Administrator"]
const EDIT_ROLES = ["Finance", "Hotel Admin", "System Manager", "Administrator"]

type Tab = "saved" | "builder" | "packs" | "flash"

interface DatasetCol {
  id: string
  label: string
  type: string
}

interface Dataset {
  id: string
  label: string
  description: string
  needs_range: boolean
  columns: DatasetCol[]
  filter_ops: string[]
}

interface SavedReport {
  name: string
  title: string
  dataset: string
  dataset_label: string
  is_shared: boolean
  owner: string
  can_edit: boolean
  schedule_frequency: string
  schedule_time: string
  recipients: string
  last_sent_on: string | null
  modified: string
}

interface Pack {
  id: string
  label: string
  description: string
  sections: string[]
}

interface FilterRow {
  field: string
  op: string
  value: string
}

interface RunPayload {
  title: string
  dataset: string
  from_date: string
  to_date: string
  columns: DatasetCol[]
  rows: Record<string, unknown>[]
  row_count: number
  truncated?: boolean
}

interface Day {
  date: string
  rooms_sold: number
  pax: number
  occupancy_pct: number
  room_revenue: number
  fnb_revenue: number
  other_revenue: number
  total_revenue: number
  adr: number
  revpar: number
  revpax: number
}

interface Flash {
  date: string
  from_date: string
  total_rooms: number
  today: Day | null
  mtd: Day & { occupancy_pct: number }
  movement: { arrivals: number; departures: number; in_house: number; no_shows: number }
  collections: { modes: { mode: string; txns: number; total: number }[]; grand_total: number }
  trend: Day[]
  outlook: { date: string; booked: number; occupancy_pct: number }[]
}

const inr = (n: number) =>
  Number(n).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

function daysAgo(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

function downloadText(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function Stat(props: { label: string; value: string; sub?: string }) {
  useT()
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-4 py-3">
      <div className="text-xl font-semibold">{props.value}</div>
      <div className="text-[10px] font-medium uppercase tracking-widest text-zinc-400">
        {translate(props.label)}
      </div>
      {props.sub && <div className="mt-0.5 text-xs text-zinc-500">{translate(props.sub)}</div>}
    </div>
  )
}

export default function Reports({ initialTab = "saved" }: { initialTab?: Tab }) {
  const { t, lang: language } = useT()
  const { roles, allowed } = useAuth()
  const canSeeVoids = allowed("Folio", "audit_voids", VOID_REPORT_ROLES)
  const canShare = roles.some((r) => EDIT_ROLES.includes(r))

  const [tab, setTab] = useState<Tab>(initialTab)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [saved, setSaved] = useState<SavedReport[]>([])
  const [packs, setPacks] = useState<Pack[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [fromDate, setFromDate] = useState(() => daysAgo(6))
  const [toDate, setToDate] = useState(todayISO)
  const [editName, setEditName] = useState<string | null>(null)
  const [title, setTitle] = useState("")
  const [datasetId, setDatasetId] = useState("")
  const [selectedCols, setSelectedCols] = useState<string[]>([])
  const [filters, setFilters] = useState<FilterRow[]>([])
  const [isShared, setIsShared] = useState(false)
  const [scheduleFrequency, setScheduleFrequency] = useState("Off")
  const [scheduleTime, setScheduleTime] = useState("07:00")
  const [scheduleWeekday, setScheduleWeekday] = useState("Mon")
  const [recipients, setRecipients] = useState("")
  const [groupBy, setGroupBy] = useState("")
  const [preview, setPreview] = useState<RunPayload | null>(null)
  // the grouped preview we drilled down from; null when not drilled in
  const [summary, setSummary] = useState<RunPayload | null>(null)
  const [busy, setBusy] = useState(false)

  // Manager flash
  const [flashDate, setFlashDate] = useState(todayISO)
  const [flashFrom, setFlashFrom] = useState("") // "" = the one day
  const [flash, setFlash] = useState<Flash | null>(null)

  const property = getCurrentProperty()
  const activeDataset = useMemo(
    () => datasets.find((d) => d.id === datasetId) || null,
    [datasets, datasetId],
  )

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ds, list, pk] = await Promise.all([
        call<Dataset[]>("kamra.custom_reports.list_report_datasets", { property }),
        call<SavedReport[]>("kamra.custom_reports.list_custom_reports", { property }),
        call<Pack[]>("kamra.custom_reports.list_report_packs", { property }),
      ])
      setDatasets(ds)
      setSaved(list)
      setPacks(pk)
      if (!datasetId && ds[0]) {
        setDatasetId(ds[0].id)
        setSelectedCols(ds[0].columns.map((c) => c.id))
        setTitle(ds[0].label)
      }
    } catch (e) {
      setError((e as Error).message || t("Could not load reports."))
    } finally {
      setLoading(false)
    }
  }, [property, datasetId, t])

  useEffect(() => {
    reload()
  }, [reload])

  useEffect(() => {
    if (tab !== "flash") return
    call<Flash>("kamra.reports.manager_flash", {
      property,
      date: flashDate,
      from_date: flashFrom && flashFrom < flashDate ? flashFrom : undefined,
    })
      .then(setFlash)
      .catch((e) => setError((e as Error).message))
  }, [tab, flashDate, flashFrom, property])

  function resetBuilder(ds?: Dataset) {
    const d = ds || datasets[0]
    setEditName(null)
    setTitle(d?.label || "")
    setDatasetId(d?.id || "")
    setSelectedCols(d?.columns.map((c) => c.id) || [])
    setFilters([])
    setGroupBy("")
    setIsShared(false)
    setScheduleFrequency("Off")
    setScheduleTime("07:00")
    setScheduleWeekday("Mon")
    setRecipients("")
    setPreview(null)
    setSummary(null)
  }

  async function openSaved(row: SavedReport) {
    if (row.dataset.startsWith("pack:")) return openPack(row.dataset, row.name)
    setBusy(true)
    setError(null)
    try {
      const def = await call<{
        name: string
        title: string
        dataset: string
        columns: string[]
        filters: FilterRow[]
        group_by: string[]
        is_shared: boolean
        schedule_frequency: string
        schedule_time: string
        schedule_weekday: string
        recipients: string
      }>("kamra.custom_reports.get_custom_report", { name: row.name, property })
      setEditName(def.name)
      setTitle(def.title)
      setDatasetId(def.dataset)
      setSelectedCols(def.columns)
      setFilters(def.filters || [])
      setGroupBy(def.group_by?.[0] || "")
      setIsShared(def.is_shared)
      setScheduleFrequency(def.schedule_frequency || "Off")
      setScheduleTime(def.schedule_time || "07:00")
      setScheduleWeekday(def.schedule_weekday || "Mon")
      setRecipients(def.recipients || "")
      setPreview(null)
      setSummary(null)
      setTab("builder")
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function onDatasetChange(id: string) {
    const d = datasets.find((x) => x.id === id)
    setDatasetId(id)
    if (d) {
      setSelectedCols(d.columns.map((c) => c.id))
      if (!editName) setTitle(d.label)
    }
    setGroupBy("")
    setPreview(null)
    setSummary(null)
  }

  function toggleCol(id: string) {
    setSelectedCols((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id],
    )
  }

  async function runPreview(
    format: "json" | "csv" | "html" = "json",
    drill?: { field: string; value: string },
  ) {
    if (!datasetId) return
    setBusy(true)
    setError(null)
    try {
      // Always send the builder's current state (no saved `name`): the
      // server would otherwise run the saved definition and ignore edits.
      const active = filters.filter((f) => f.field && f.value !== "")
      const res = await call<RunPayload & { format?: string; content?: string; filename?: string }>(
        "kamra.custom_reports.run_custom_report",
        {
          property,
          dataset: datasetId,
          from_date: fromDate,
          to_date: toDate,
          columns: JSON.stringify(
            groupBy && !selectedCols.includes(groupBy) ? [groupBy, ...selectedCols] : selectedCols,
          ),
          filters: JSON.stringify(drill ? [...active, { ...drill, op: "=" }] : active),
          group_by: JSON.stringify(groupBy && !drill ? [groupBy] : []),
          format,
          lang: language,
        },
      )
      if (title.trim()) res.title = title.trim()
      if (drill) {
        res.title = `${res.title} · ${drill.value}`
        setSummary(preview)
      } else if (format === "json") {
        setSummary(null)
      }
      if (format === "csv" && res.content) {
        downloadText(res.filename || "report.csv", res.content, "text/csv")
      } else if (format === "html" && res.content) {
        const w = window.open("", "_blank")
        if (w) {
          w.document.write(res.content)
          w.document.close()
        }
      } else {
        setPreview(res as RunPayload)
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function openPack(pack: string, name?: string) {
    setBusy(true)
    setError(null)
    try {
      const res = await call<{ content: string }>(
        name ? "kamra.custom_reports.run_custom_report" : "kamra.custom_reports.run_report_pack",
        { property, pack, name, from_date: fromDate, to_date: toDate, format: "html", lang: language },
      )
      const w = window.open("", "_blank")
      if (w) {
        w.document.write(res.content)
        w.document.close()
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function emailPack(pack: Pack) {
    const to = window.prompt(t("Email addresses (comma-separated)"), "")
    if (!to) return
    setBusy(true)
    setError(null)
    try {
      await call("kamra.custom_reports.email_custom_report", {
        property, recipients: to, dataset: pack.id,
        from_date: fromDate, to_date: toDate, lang: language,
      })
      window.alert(t("Report emailed."))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function schedulePack(pack: Pack) {
    const to = window.prompt(t("Email this pack every Monday at 07:00 to (comma-separated)"), "")
    if (!to) return
    setBusy(true)
    setError(null)
    try {
      await call("kamra.custom_reports.save_custom_report", {
        property, title: translate(pack.label), dataset: pack.id, is_shared: 1,
        schedule_frequency: "Weekly", schedule_weekday: "Mon", schedule_time: "07:00",
        recipients: to,
        lang: language,
      })
      await reload()
      setTab("saved")
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function saveReport() {
    if (!datasetId || !title.trim()) return
    setBusy(true)
    setError(null)
    try {
      const savedDef = await call<{ name: string }>("kamra.custom_reports.save_custom_report", {
        property,
        name: editName || undefined,
        title: title.trim(),
        dataset: datasetId,
        columns: JSON.stringify(selectedCols),
        filters: JSON.stringify(filters.filter((f) => f.field && f.value !== "")),
        group_by: JSON.stringify(groupBy ? [groupBy] : []),
        is_shared: isShared ? 1 : 0,
        schedule_frequency: scheduleFrequency,
        schedule_time: scheduleTime,
        schedule_weekday: scheduleWeekday,
        recipients,
        lang: language,
      })
      setEditName(savedDef.name)
      await reload()
      setTab("saved")
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function removeReport(name: string) {
    if (!window.confirm(t("Delete this saved report?"))) return
    setBusy(true)
    try {
      await call("kamra.custom_reports.delete_custom_report", { name, property })
      await reload()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function emailNow(name?: string) {
    const to = window.prompt(t("Email addresses (comma-separated)"), recipients || "")
    if (!to) return
    setBusy(true)
    setError(null)
    try {
      await call("kamra.custom_reports.email_custom_report", {
        property,
        recipients: to,
        name: name || editName || undefined,
        dataset: name || editName ? undefined : datasetId,
        from_date: fromDate,
        to_date: toDate,
        columns: name || editName ? undefined : JSON.stringify(selectedCols),
        filters: name || editName
          ? undefined
          : JSON.stringify(filters.filter((f) => f.field && f.value !== "")),
        group_by: name || editName ? undefined : JSON.stringify(groupBy ? [groupBy] : []),
        lang: language,
        attach_format: "csv",
      })
      await reload()
      window.alert(t("Report emailed."))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "saved", label: t("My reports") },
    { id: "builder", label: t("New report") },
    { id: "packs", label: t("Department packs") },
    { id: "flash", label: t("Manager flash") },
  ]

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 print:hidden">
        <h1 className="text-lg font-semibold">{t("Reports")}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/revenue-reports"
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50"
          >
            {t("Revenue Reports")}
          </Link>
          <Link
            to="/cashier/shift-report"
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50"
          >
            {t("Cashier shift report")}
          </Link>
          <Link
            to="/ledgers"
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50"
          >
            {t("Ledgers")}
          </Link>
          {canSeeVoids && (
            <Link
              to="/voids-allowances"
              className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50"
            >
              {t("Voids & Allowances")}
            </Link>
          )}
          <Link
            to="/accounting-export"
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50"
          >
            {t("Accounting export")}
          </Link>
        </div>
      </div>

      <div className="mb-4 flex gap-1 border-b border-zinc-200 print:hidden">
        {tabs.map((x) => (
          <button
            key={x.id}
            type="button"
            onClick={() => {
              if (x.id === "builder" && tab !== "builder") resetBuilder(activeDataset || undefined)
              setTab(x.id)
            }}
            className={`px-3 py-2 text-sm font-medium ${
              tab === x.id
                ? "border-b-2 border-brand-600 text-brand-700"
                : "text-zinc-500 hover:text-zinc-800"
            }`}
          >
            {x.label}
          </button>
        ))}
      </div>

      {error && (
        <p className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {tab === "saved" && (
        <div>
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm text-zinc-500">
              {t("Build a report, save it, run it again, or have Kamra email it on a schedule.")}
            </p>
            <Button
              onClick={() => {
                resetBuilder()
                setTab("builder")
              }}
            >
              <Plus className="size-4" aria-hidden /> {t("New report")}
            </Button>
          </div>
          {loading ? (
            <p className="py-10 text-center text-zinc-400">{t("Loading…")}</p>
          ) : saved.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-zinc-500">
                {t("No saved reports yet. Create one from a dataset.")}
              </CardContent>
            </Card>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-500">
                    <th className="px-3 py-2">{t("Title")}</th>
                    <th className="px-3 py-2">{t("Dataset")}</th>
                    <th className="px-3 py-2">{t("Schedule")}</th>
                    <th className="px-3 py-2">{t("Shared")}</th>
                    <th className="px-3 py-2 text-right">{t("Actions")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {saved.map((r) => (
                    <tr key={r.name}>
                      <td className="px-3 py-2 font-medium">{r.title}</td>
                      <td className="px-3 py-2 text-zinc-600">{translate(r.dataset_label)}</td>
                      <td className="px-3 py-2 text-zinc-600">
                        {r.schedule_frequency === "Off"
                          ? t("Off")
                          : `${translate(r.schedule_frequency)} · ${r.schedule_time}`}
                      </td>
                      <td className="px-3 py-2">{r.is_shared ? t("Yes") : t("No")}</td>
                      <td className="px-3 py-2">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="outline"
                            className="px-2 py-1 text-xs"
                            disabled={busy}
                            onClick={() => openSaved(r)}
                          >
                            {t("action|Open")}
                          </Button>
                          <Button
                            variant="outline"
                            className="px-2 py-1 text-xs"
                            disabled={busy}
                            onClick={() => emailNow(r.name)}
                          >
                            <Mail className="size-3.5" aria-hidden />
                          </Button>
                          {r.can_edit && (
                            <Button
                              variant="outline"
                              className="px-2 py-1 text-xs"
                              disabled={busy}
                              onClick={() => removeReport(r.name)}
                            >
                              <Trash2 className="size-3.5" aria-hidden />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "packs" && (
        <div>
          <div className="mb-3 flex flex-wrap items-end gap-2">
            <p className="mr-auto text-sm text-zinc-500">
              {t("One page per department. You see the parts your role can open.")}
            </p>
            <label className="text-xs text-zinc-500">
              {t("From")}
              <input
                type="date"
                className="ms-1 rounded-lg border border-zinc-300 px-2 py-1"
                value={fromDate}
                onChange={(e) => e.target.value && setFromDate(e.target.value)}
              />
            </label>
            <label className="text-xs text-zinc-500">
              {t("To")}
              <input
                type="date"
                className="ms-1 rounded-lg border border-zinc-300 px-2 py-1"
                value={toDate}
                onChange={(e) => e.target.value && setToDate(e.target.value)}
              />
            </label>
          </div>
          {!loading && packs.length === 0 && (
            <p className="text-sm text-zinc-500">{t("Your role has no reports.")}</p>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            {packs.map((p) => (
              <Card key={p.id}>
                <CardHeader>
                  <CardTitle>{translate(p.label)}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <p className="text-zinc-500">{translate(p.description)}</p>
                  <ul className="list-disc ps-5 text-zinc-600">
                    {p.sections.map((x) => (
                      <li key={x}>{translate(x)}</li>
                    ))}
                  </ul>
                  <div className="flex flex-wrap gap-2">
                    <Button disabled={busy} onClick={() => openPack(p.id)}>
                      <Printer className="size-4" aria-hidden /> {t("action|Open")}
                    </Button>
                    <Button variant="outline" disabled={busy} onClick={() => emailPack(p)}>
                      <Mail className="size-4" aria-hidden /> {t("Email now")}
                    </Button>
                    {canShare && (
                      <Button variant="outline" disabled={busy} onClick={() => schedulePack(p)}>
                        {t("Email every Monday")}
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {tab === "builder" && (
        <div className="grid gap-4 lg:grid-cols-5">
          <Card className="lg:col-span-2 print:hidden">
            <CardHeader>
              <CardTitle>{editName ? t("Edit report") : t("New report")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <label className="block">
                <span className="text-xs uppercase tracking-wider text-zinc-500">{t("Title")}</span>
                <input
                  className="mt-1 w-full rounded-lg border border-zinc-300 px-2 py-1.5"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </label>
              <label className="block">
                <span className="text-xs uppercase tracking-wider text-zinc-500">{t("Dataset")}</span>
                <select
                  className="mt-1 w-full rounded-lg border border-zinc-300 px-2 py-1.5"
                  value={datasetId}
                  onChange={(e) => onDatasetChange(e.target.value)}
                >
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {translate(d.label)}
                    </option>
                  ))}
                </select>
                {activeDataset && (
                  <p className="mt-1 text-xs text-zinc-500">{translate(activeDataset.description)}</p>
                )}
              </label>
              <div className="flex gap-2">
                <label className="flex-1">
                  <span className="text-xs uppercase tracking-wider text-zinc-500">{t("From")}</span>
                  <input
                    type="date"
                    className="mt-1 w-full rounded-lg border border-zinc-300 px-2 py-1.5"
                    value={fromDate}
                    onChange={(e) => e.target.value && setFromDate(e.target.value)}
                  />
                </label>
                <label className="flex-1">
                  <span className="text-xs uppercase tracking-wider text-zinc-500">{t("To")}</span>
                  <input
                    type="date"
                    className="mt-1 w-full rounded-lg border border-zinc-300 px-2 py-1.5"
                    value={toDate}
                    onChange={(e) => e.target.value && setToDate(e.target.value)}
                  />
                </label>
              </div>

              {activeDataset && (
                <fieldset>
                  <legend className="text-xs uppercase tracking-wider text-zinc-500">
                    {t("Columns")}
                  </legend>
                  <div className="mt-1 max-h-40 space-y-1 overflow-y-auto rounded-lg border border-zinc-200 p-2">
                    {activeDataset.columns.map((c) => (
                      <label key={c.id} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={selectedCols.includes(c.id)}
                          onChange={() => toggleCol(c.id)}
                        />
                        <span>{translate(c.label)}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              )}

              <fieldset>
                <legend className="text-xs uppercase tracking-wider text-zinc-500">
                  {t("Filters")}
                </legend>
                <div className="mt-1 space-y-2">
                  {filters.map((f, i) => (
                    <div key={i} className="flex gap-1">
                      <select
                        className="w-1/3 rounded border border-zinc-300 px-1 py-1"
                        value={f.field}
                        onChange={(e) => {
                          const next = [...filters]
                          next[i] = { ...f, field: e.target.value }
                          setFilters(next)
                        }}
                      >
                        <option value="">{t("Field")}</option>
                        {activeDataset?.columns.map((c) => (
                          <option key={c.id} value={c.id}>
                            {translate(c.label)}
                          </option>
                        ))}
                      </select>
                      <select
                        className="w-1/4 rounded border border-zinc-300 px-1 py-1"
                        value={f.op}
                        onChange={(e) => {
                          const next = [...filters]
                          next[i] = { ...f, op: e.target.value }
                          setFilters(next)
                        }}
                      >
                        {(activeDataset?.filter_ops || ["=", "contains"]).map((op) => (
                          <option key={op} value={op}>
                            {op}
                          </option>
                        ))}
                      </select>
                      <input
                        className="flex-1 rounded border border-zinc-300 px-1 py-1"
                        value={f.value}
                        onChange={(e) => {
                          const next = [...filters]
                          next[i] = { ...f, value: e.target.value }
                          setFilters(next)
                        }}
                      />
                      <button
                        type="button"
                        className="px-1 text-zinc-400 hover:text-red-600"
                        onClick={() => setFilters(filters.filter((_, j) => j !== i))}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    className="px-2 py-1 text-xs"
                    type="button"
                    onClick={() =>
                      setFilters([...filters, { field: "", op: "contains", value: "" }])
                    }
                  >
                    {t("Add filter")}
                  </Button>
                </div>
              </fieldset>

              <label className="block">
                <span className="text-xs uppercase tracking-wider text-zinc-500">
                  {t("Group by")}
                </span>
                <select
                  className="mt-1 w-full rounded-lg border border-zinc-300 px-2 py-1.5"
                  value={groupBy}
                  onChange={(e) => setGroupBy(e.target.value)}
                >
                  <option value="">{t("None")}</option>
                  {activeDataset?.columns
                    .filter((c) => c.type !== "number")
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {translate(c.label)}
                      </option>
                    ))}
                </select>
              </label>

              {canShare && (
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={isShared}
                    onChange={(e) => setIsShared(e.target.checked)}
                  />
                  <span>{t("Share with property")}</span>
                </label>
              )}

              {canShare && (
                <div className="space-y-2 rounded-lg border border-zinc-200 p-2">
                  <p className="text-xs uppercase tracking-wider text-zinc-500">
                    {t("Email schedule")}
                  </p>
                  <select
                    className="w-full rounded border border-zinc-300 px-2 py-1.5"
                    value={scheduleFrequency}
                    onChange={(e) => setScheduleFrequency(e.target.value)}
                  >
                    <option value="Off">{t("Off")}</option>
                    <option value="Daily">{t("Daily")}</option>
                    <option value="Weekly">{t("Weekly")}</option>
                  </select>
                  {scheduleFrequency !== "Off" && (
                    <>
                      <input
                        type="time"
                        className="w-full rounded border border-zinc-300 px-2 py-1.5"
                        value={scheduleTime}
                        onChange={(e) => setScheduleTime(e.target.value)}
                      />
                      {scheduleFrequency === "Weekly" && (
                        <select
                          className="w-full rounded border border-zinc-300 px-2 py-1.5"
                          value={scheduleWeekday}
                          onChange={(e) => setScheduleWeekday(e.target.value)}
                        >
                          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                            <option key={d} value={d}>
                              {translate(d)}
                            </option>
                          ))}
                        </select>
                      )}
                      <input
                        className="w-full rounded border border-zinc-300 px-2 py-1.5"
                        placeholder={t("Recipients (comma-separated emails)")}
                        value={recipients}
                        onChange={(e) => setRecipients(e.target.value)}
                      />
                    </>
                  )}
                </div>
              )}

              <div className="flex flex-wrap gap-2 pt-1">
                <Button disabled={busy} onClick={() => runPreview("json")}>
                  {t("Preview")}
                </Button>
                <Button variant="outline" disabled={busy} onClick={() => runPreview("csv")}>
                  {t("CSV")}
                </Button>
                <Button variant="outline" disabled={busy} onClick={() => runPreview("html")}>
                  <Printer className="size-4" aria-hidden /> {t("Print")}
                </Button>
                <Button variant="outline" disabled={busy} onClick={() => emailNow()}>
                  <Mail className="size-4" aria-hidden /> {t("Email")}
                </Button>
                <Button disabled={busy || !title.trim()} onClick={saveReport}>
                  {t("Save")}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-3">
            <CardHeader>
              <CardTitle>
                {preview
                  ? `${preview.title} · ${preview.row_count} ${t("rows")}`
                  : t("Preview")}
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {summary && (
                <Button
                  variant="outline"
                  className="mb-2 px-2 py-1 text-xs"
                  onClick={() => {
                    setPreview(summary)
                    setSummary(null)
                  }}
                >
                  ← {t("Back to summary")}
                </Button>
              )}
              {preview && groupBy && !summary && (
                <p className="mb-2 text-xs text-zinc-500">
                  {t("Click a row to see the rows behind it.")}
                </p>
              )}
              {!preview && (
                <p className="py-8 text-center text-sm text-zinc-400">
                  {t("Choose columns and press Preview.")}
                </p>
              )}
              {preview && (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-500">
                      {preview.columns.map((c) => (
                        <th key={c.id} className="px-2 py-1.5 whitespace-nowrap">
                          {translate(c.label)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {preview.rows.slice(0, 200).map((row, i) => {
                      const key = groupBy && !summary ? row[groupBy] : null
                      // ponytail: null group keys aren't drillable; "=" can't match an empty value
                      const drill = key == null || busy ? undefined : () =>
                        runPreview("json", { field: groupBy, value: String(key) })
                      return (
                      <tr
                        key={i}
                        onClick={drill}
                        className={drill ? "cursor-pointer hover:bg-zinc-50" : undefined}
                      >
                        {preview.columns.map((c) => (
                          <td key={c.id} className="px-2 py-1.5 whitespace-nowrap">
                            {row[c.id] == null ? "" : String(row[c.id])}
                          </td>
                        ))}
                      </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
              {preview?.truncated && (
                <p className="mt-2 text-xs text-amber-700">
                  {t("Showing the first {n} rows.", { n: preview.row_count })}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "flash" && (
        <FlashPanel
          d={flash}
          date={flashDate}
          setDate={setFlashDate}
          from={flashFrom}
          setFrom={setFlashFrom}
          t={t}
        />
      )}
    </div>
  )
}

function FlashPanel(props: {
  d: Flash | null
  date: string
  setDate: (v: string) => void
  from: string
  setFrom: (v: string) => void
  t: (k: string, vars?: Record<string, string | number>) => string
}) {
  const { d, date, setDate, from, setFrom, t } = props
  if (!d) return <p className="py-10 text-center text-zinc-400">{t("Loading…")}</p>
  const todayData = d.today
  const ranged = d.from_date !== d.date

  return (
    <div>
      <div className="mb-4 flex justify-end gap-2 print:hidden">
        <input
          type="date"
          aria-label={t("From")}
          className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm"
          value={from || date}
          max={date}
          onChange={(e) => setFrom(e.target.value === date ? "" : e.target.value)}
        />
        <span className="self-center text-sm text-zinc-400">→</span>
        <input
          type="date"
          aria-label={t("Report date")}
          className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm"
          value={date}
          onChange={(e) => e.target.value && setDate(e.target.value)}
        />
        <Button variant="outline" onClick={() => window.print()}>
          <Printer className="size-4" aria-hidden /> {t("Print")}
        </Button>
      </div>
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Stat
          label={t("Occupancy")}
          value={`${todayData?.occupancy_pct ?? 0}%`}
          sub={t("{sold} of {total} rooms", {
            sold: todayData?.rooms_sold ?? 0,
            total: d.total_rooms,
          })}
        />
        <Stat label={t("ADR")} value={`${cur()}${inr(todayData?.adr ?? 0)}`} sub={t("room rate / room sold")} />
        <Stat label={t("RevPAR")} value={`${cur()}${inr(todayData?.revpar ?? 0)}`} sub={t("room rev / room")} />
        <Stat
          label={t("RevPAX")}
          value={`${cur()}${inr(todayData?.revpax ?? 0)}`}
          sub={t("total spend / guest · {pax} pax", { pax: todayData?.pax ?? 0 })}
        />
        <Stat
          label={ranged ? t("Revenue") : t("Revenue (day)")}
          value={`${cur()}${inr(todayData?.total_revenue ?? 0)}`}
          sub={t("room {room} · F&B {fnb} · other {other}", {
            room: `${cur()}${inr(todayData?.room_revenue ?? 0)}`,
            fnb: `${cur()}${inr(todayData?.fnb_revenue ?? 0)}`,
            other: `${cur()}${inr(todayData?.other_revenue ?? 0)}`,
          })}
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{ranged ? `${d.from_date} → ${d.date}` : t("Last 14 days")}</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-500">
                  <th className="py-1.5 pr-3">{t("Date")}</th>
                  <th className="py-1.5 pr-3 text-right">{t("Occ %")}</th>
                  <th className="py-1.5 pr-3 text-right">{t("ADR {cur}", { cur: cur() })}</th>
                  <th className="py-1.5 pr-3 text-right">{t("RevPAR {cur}", { cur: cur() })}</th>
                  <th className="py-1.5 text-right">{t("Revenue {cur}", { cur: cur() })}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {d.trend.map((r) => (
                  <tr key={r.date}>
                    <td className="py-1.5 pr-3 text-zinc-500">{r.date}</td>
                    <td className="py-1.5 pr-3 text-right">{r.occupancy_pct}</td>
                    <td className="py-1.5 pr-3 text-right">{inr(r.adr)}</td>
                    <td className="py-1.5 pr-3 text-right">{inr(r.revpar)}</td>
                    <td className="py-1.5 text-right">
                      {inr(r.room_revenue + r.fnb_revenue + r.other_revenue)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("Movement")}</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-2 text-sm">
              <div>
                {t("Arrivals")}{" "}
                <span className="float-right font-medium">{d.movement.arrivals}</span>
              </div>
              <div>
                {t("Departures")}{" "}
                <span className="float-right font-medium">{d.movement.departures}</span>
              </div>
              <div>
                {t("In-house")}{" "}
                <span className="float-right font-medium">{d.movement.in_house}</span>
              </div>
              <div>
                {t("No-shows")}{" "}
                <span className="float-right font-medium">{d.movement.no_shows}</span>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("Collections")}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              {d.collections.modes.length === 0 && (
                <p className="text-zinc-400">{t("Nothing collected yet.")}</p>
              )}
              {d.collections.modes.map((m) => (
                <div key={m.mode} className="flex justify-between py-0.5">
                  <span>
                    {translate(m.mode)} · {m.txns}
                  </span>
                  <span>
                    {cur()}
                    {inr(m.total)}
                  </span>
                </div>
              ))}
              <div className="mt-1 flex justify-between border-t border-zinc-200 pt-1 font-medium">
                <span>{t("Total")}</span>
                <span>
                  {cur()}
                  {inr(d.collections.grand_total)}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
