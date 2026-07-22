import {
  useCallback,
  useEffect,
  useState,
  type ComponentType,
  type ReactNode,
} from "react"
import { Columns3, Download, Plus, Search, Trash2 } from "lucide-react"
import { Sheet } from "./ui/sheet"
import { getCurrentProperty } from "../lib/api"
import {
  createResource,
  deleteResource,
  listResource,
  serverError,
  updateResource,
  type Row,
} from "../lib/resource"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"
import ImageField from "./ImageField"
import { moneyLocale } from "../lib/money"

export interface FieldSpec {
  field: string
  label: string
  type: "data" | "int" | "float" | "currency" | "select" | "check" | "date" | "link" | "readonly" | "image"
  options?: string[] // for select
  linkDoctype?: string // for link
  required?: boolean
  hint?: string // for image: recommended size/format
}

export interface ScreenConfig {
  doctype: string
  title: string
  description?: string
  columns: { field: string; label: string; badge?: boolean }[]
  form: FieldSpec[]
  propertyScoped?: boolean
  allowCreate?: boolean
  allowDelete?: boolean
  orderBy?: string
  /** Fields searched (LIKE) by the search box. Adds a search input when set. */
  searchFields?: string[]
  /** Dropdown filters shown in the toolbar (e.g. status). */
  filters?: { field: string; label: string; options: string[] }[]
  /** Rows per page (adds pagination when set). */
  pageSize?: number
  /** Date-range filter on this date field (adds From/To pickers). */
  dateFilter?: { field: string; label: string }
  /** Custom section rendered in the drawer below the form (existing rows only). */
  extra?: ComponentType<{ row: Row; reload: () => void }>
  /** Replace the generic edit form with a bespoke detail panel (existing rows).
   *  When set, the drawer opens wide and the panel owns its own actions. */
  detailPanel?: ComponentType<{
    row: Row
    reload: () => void
    onClose: () => void
  }>
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600 " +
  "disabled:bg-zinc-50 disabled:text-zinc-400"

function FieldInput(props: {
  spec: FieldSpec
  value: unknown
  onChange: (v: unknown) => void
  linkOptions: Record<string, string[]>
}) {
  const { spec, value, onChange } = props
  switch (spec.type) {
    case "select":
      return (
        <select
          className={inputCls}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">-</option>
          {spec.options?.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      )
    case "link":
      return (
        <select
          className={inputCls}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">-</option>
          {(props.linkOptions[spec.linkDoctype ?? ""] ?? []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      )
    case "check":
      return (
        <input
          type="checkbox"
          className="size-4 accent-brand-600"
          checked={Boolean(Number(value ?? 0))}
          onChange={(e) => onChange(e.target.checked ? 1 : 0)}
        />
      )
    case "date":
      return (
        <input
          type="date"
          className={inputCls}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        />
      )
    case "int":
    case "float":
    case "currency":
      return (
        <input
          type="number"
          className={inputCls}
          value={value === null || value === undefined ? "" : Number(value)}
          onChange={(e) =>
            onChange(e.target.value === "" ? null : Number(e.target.value))
          }
        />
      )
    case "readonly":
      return (
        <input className={inputCls} disabled value={String(value ?? "")} />
      )
    case "image":
      return (
        <ImageField
          hint={spec.hint || "JPG/PNG/WebP · under 1 MB"}
          value={String(value ?? "")}
          onChange={(url) => onChange(url)}
        />
      )
    default:
      return (
        <input
          className={inputCls}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        />
      )
  }
}

const BADGE_TONES: Record<string, "green" | "sky" | "amber" | "rose" | "zinc"> = {
  Confirmed: "green", "Checked In": "sky", "Checked Out": "zinc",
  Cancelled: "rose", "No Show": "rose", Waitlist: "amber",
  Open: "amber", Closed: "zinc", Enquiry: "amber", Completed: "zinc",
  Clean: "green", Dirty: "amber", Inspected: "sky", "Out of Order": "rose",
  "In Progress": "sky", Done: "green",
}

const cellValue = (v: unknown) =>
  typeof v === "number"
    ? v.toLocaleString(moneyLocale(), { maximumFractionDigits: 2 })
    : String(v ?? "-")

export function ResourceScreen({
  config,
  headerAction,
}: {
  config: ScreenConfig
  /** Extra control rendered in the header next to New (e.g. a bulk import). */
  headerAction?: ReactNode
}) {
  const [rows, setRows] = useState<Row[]>([])
  const [editing, setEditing] = useState<Row | "new" | null>(null)
  const [draft, setDraft] = useState<Record<string, unknown>>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [linkOptions, setLinkOptions] = useState<Record<string, string[]>>({})
  const [search, setSearch] = useState("")
  // Frappe-style list settings: choose which columns this table shows,
  // remembered per user per doctype.
  const colsKey = `kamra:cols:${config.doctype}`
  const [hiddenCols, setHiddenCols] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(colsKey) || "[]"))
    } catch {
      return new Set()
    }
  })
  const [colsOpen, setColsOpen] = useState(false)
  const toggleCol = (field: string) => {
    setHiddenCols((prev) => {
      const next = new Set(prev)
      if (next.has(field)) next.delete(field)
      else if (next.size < config.columns.length - 1) next.add(field)
      localStorage.setItem(colsKey, JSON.stringify([...next]))
      return next
    })
  }
  const visibleCols = config.columns.filter((c) => !hiddenCols.has(c.field))
  const [debounced, setDebounced] = useState("")
  const [filterVals, setFilterVals] = useState<Record<string, string>>({})
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [page, setPage] = useState(0)

  const pageSize = config.pageSize ?? 0

  const fields = Array.from(
    new Set(["name", ...config.columns.map((c) => c.field)]),
  )

  // debounce the search box
  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search])

  // any search/filter change resets to the first page
  useEffect(() => setPage(0), [debounced, filterVals, dateFrom, dateTo])

  const load = useCallback(() => {
    const filters: (string | number)[][] = []
    if (config.propertyScoped)
      filters.push(["property", "=", getCurrentProperty()])
    for (const [field, val] of Object.entries(filterVals))
      if (val) filters.push([field, "=", val])
    if (config.dateFilter?.field) {
      if (dateFrom) filters.push([config.dateFilter.field, ">=", dateFrom])
      if (dateTo) filters.push([config.dateFilter.field, "<=", dateTo])
    }
    const orFilters =
      debounced && config.searchFields?.length
        ? config.searchFields.map((f) => [f, "like", `%${debounced}%`])
        : undefined
    listResource(config.doctype, {
      fields,
      filters: filters.length ? filters : undefined,
      orFilters,
      orderBy: config.orderBy,
      limit: pageSize || 100,
      start: pageSize ? page * pageSize : 0,
    })
      .then((r) => {
        setRows(r)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.doctype, debounced, filterVals, page, dateFrom, dateTo])

  useEffect(load, [load])

  async function exportCsv() {
    const filters: (string | number)[][] = []
    if (config.propertyScoped)
      filters.push(["property", "=", getCurrentProperty()])
    for (const [field, val] of Object.entries(filterVals))
      if (val) filters.push([field, "=", val])
    if (config.dateFilter?.field) {
      if (dateFrom) filters.push([config.dateFilter.field, ">=", dateFrom])
      if (dateTo) filters.push([config.dateFilter.field, "<=", dateTo])
    }
    const orFilters =
      debounced && config.searchFields?.length
        ? config.searchFields.map((f) => [f, "like", `%${debounced}%`])
        : undefined
    const all = await listResource(config.doctype, {
      fields,
      filters: filters.length ? filters : undefined,
      orFilters,
      orderBy: config.orderBy,
      limit: 2000,
    })
    const cols = visibleCols
    const esc = (v: unknown) => {
      const t = String(v ?? "")
      return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t
    }
    const csv = [
      cols.map((c) => esc(c.label)).join(","),
      ...all.map((r) => cols.map((c) => esc(r[c.field])).join(",")),
    ].join("\n")
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" })
    const a = document.createElement("a")
    a.href = URL.createObjectURL(blob)
    a.download = `${config.doctype.toLowerCase().replace(/ /g, "-")}-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  // load link options once per screen
  useEffect(() => {
    const links = config.form.filter((f) => f.type === "link" && f.linkDoctype)
    links.forEach((f) => {
      listResource(f.linkDoctype!, {
        fields: ["name"],
        filters: undefined,
        limit: 100,
        orderBy: "name asc",
      }).then((r) =>
        setLinkOptions((prev) => ({
          ...prev,
          [f.linkDoctype!]: r.map((x) => x.name),
        })),
      )
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.doctype])

  function openEdit(row: Row | "new") {
    setEditing(row)
    setDraft(row === "new" ? {} : { ...row })
    setError(null)
  }

  async function save() {
    setBusy(true)
    try {
      const payload = { ...draft }
      delete payload.name
      if (config.propertyScoped) payload.property = getCurrentProperty()
      if (editing === "new") {
        await createResource(config.doctype, payload)
      } else if (editing) {
        await updateResource(config.doctype, editing.name, payload)
      }
      setEditing(null)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (editing === "new" || !editing) return
    setBusy(true)
    try {
      await deleteResource(config.doctype, editing.name)
      setEditing(null)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{config.title}</CardTitle>
          {config.description && (
            <p className="mt-0.5 text-xs text-zinc-400">
              {config.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {headerAction}
          {config.allowCreate !== false && (
            <Button onClick={() => openEdit("new")}>
              <Plus className="size-4" aria-hidden />
              New
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {error && !editing && (
          <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}
        <div className="mb-4 flex flex-wrap items-center gap-2">
            {config.searchFields?.length ? (
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-zinc-400" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search…"
                  className="w-56 rounded-lg border border-zinc-300 bg-white py-1.5 pl-8 pr-3 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
                />
              </div>
            ) : null}
            {config.filters?.map((f) => (
              <select
                key={f.field}
                value={filterVals[f.field] ?? ""}
                onChange={(e) =>
                  setFilterVals((v) => ({ ...v, [f.field]: e.target.value }))
                }
                className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
              >
                <option value="">{f.label}: all</option>
                {f.options.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            ))}
            {config.dateFilter && (
              <div className="flex items-center gap-1.5 text-sm text-zinc-500">
                <span className="text-xs">{config.dateFilter.label}</span>
                <input
                  type="date"
                  aria-label={`${config.dateFilter.label} from`}
                  className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                />
                <span className="text-xs">to</span>
                <input
                  type="date"
                  aria-label={`${config.dateFilter.label} to`}
                  className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                />
                {(dateFrom || dateTo) && (
                  <button
                    className="text-xs text-zinc-400 hover:text-zinc-600"
                    onClick={() => {
                      setDateFrom("")
                      setDateTo("")
                    }}
                  >
                    Clear
                  </button>
                )}
              </div>
            )}
            <div className="relative ml-auto flex items-center gap-2">
              <button
                onClick={exportCsv}
                title="Download the current view as CSV (Excel-ready)"
                aria-label="Export as CSV"
                className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-sm text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700"
              >
                <Download className="size-4" aria-hidden />
                Export
              </button>
              <button
                onClick={() => setColsOpen((o) => !o)}
                title="Choose which columns this table shows"
                aria-label="Configure table columns"
                className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-sm text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700"
              >
                <Columns3 className="size-4" aria-hidden />
                Columns
              </button>
              {colsOpen && (
                <div className="absolute right-0 z-30 mt-1 w-56 rounded-xl border border-zinc-200 bg-white p-2 shadow-xl">
                  {config.columns.map((c) => (
                    <label
                      key={c.field}
                      className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-zinc-50"
                    >
                      <input
                        type="checkbox"
                        className="size-4 accent-brand-600"
                        checked={!hiddenCols.has(c.field)}
                        onChange={() => toggleCol(c.field)}
                      />
                      {c.label}
                    </label>
                  ))}
                  <button
                    className="mt-1 w-full rounded-lg px-2 py-1 text-left text-xs text-zinc-400 hover:text-zinc-600"
                    onClick={() => setColsOpen(false)}
                  >
                    Done
                  </button>
                </div>
              )}
            </div>
          </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                {visibleCols.map((c) => (
                  <th key={c.field} className="py-2 pr-4">
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map((row) => (
                <tr
                  key={row.name}
                  className="cursor-pointer hover:bg-zinc-50"
                  onClick={() => openEdit(row)}
                >
                  {visibleCols.map((c) => (
                    <td
                      key={c.field}
                      className={
                        "py-2.5 pr-4" +
                        (typeof row[c.field] === "number"
                          ? " text-right tabular-nums"
                          : "")
                      }
                    >
                      {c.badge && row[c.field] ? (
                        <Badge
                          tone={BADGE_TONES[String(row[c.field])] ?? "zinc"}
                        >
                          {String(row[c.field])}
                        </Badge>
                      ) : (
                        cellValue(row[c.field])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={config.columns.length}
                    className="py-6 text-center text-sm text-zinc-400"
                  >
                    Nothing here yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {pageSize > 0 && (page > 0 || rows.length >= pageSize) && (
          <div className="mt-3 flex items-center justify-between text-sm text-zinc-500">
            <span>Page {page + 1}</span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Prev
              </Button>
              <Button
                variant="outline"
                disabled={rows.length < pageSize}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </CardContent>

      {editing && (() => {
        const useDetail = editing !== "new" && !!config.detailPanel
        return (
        <Sheet
          wide
          title={
            editing === "new"
              ? `New ${config.title.replace(/s$/, "")}`
              : String(editing.name)
          }
          description={useDetail ? undefined : config.description}
          onClose={() => setEditing(null)}
          footer={
            useDetail ? undefined : (
            <div className="flex items-center justify-between">
              {editing !== "new" && config.allowDelete !== false ? (
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={remove}
                  aria-label="Delete"
                >
                  <Trash2 className="size-4 text-rose-500" aria-hidden />
                  Delete
                </Button>
              ) : (
                <span />
              )}
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setEditing(null)}>
                  Cancel
                </Button>
                <Button disabled={busy} onClick={save}>
                  {busy ? "Saving…" : "Save"}
                </Button>
              </div>
            </div>
            )
          }
        >
          {useDetail && config.detailPanel ? (
            <config.detailPanel
              row={editing}
              reload={load}
              onClose={() => setEditing(null)}
            />
          ) : (
            <div className="space-y-4">
              <div className="grid gap-x-5 gap-y-4 sm:grid-cols-2">
                {config.form.map((spec) => (
                  <label
                    key={spec.field}
                    className={
                      "block" +
                      (spec.type === "check" ? " sm:col-span-2" : "")
                    }
                  >
                    <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                      {spec.label}
                      {spec.required && <span className="text-rose-500"> *</span>}
                    </span>
                    <FieldInput
                      spec={spec}
                      value={draft[spec.field]}
                      onChange={(v) =>
                        setDraft((d) => ({ ...d, [spec.field]: v }))
                      }
                      linkOptions={linkOptions}
                    />
                  </label>
                ))}
              </div>
              {editing !== "new" && config.extra && (
                <config.extra row={editing} reload={load} />
              )}
              {error && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  {error}
                </div>
              )}
            </div>
          )}
        </Sheet>
        )
      })()}
    </Card>
  )
}
