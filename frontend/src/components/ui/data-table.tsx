import { useEffect, useMemo, useState, type ReactNode } from "react"
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Columns3, Download } from "lucide-react"
import { Button } from "./button"
import { t as translate, useUILanguage } from "../../lib/i18n"
import { downloadCsv } from "../../lib/csv"

export type Column<R> = {
  key: string
  /** Header text, already translated. */
  label: string
  /** What the cell shows; defaults to row[key]. */
  render?: (row: R) => ReactNode
  /** What sorting and the CSV use; defaults to row[key]. */
  value?: (row: R) => string | number | null | undefined
  align?: "left" | "right" | "center"
  /** Hidden until the user turns it on from Columns. */
  hidden?: boolean
  /** Not sortable (an action column). */
  noSort?: boolean
}

type Props<R> = {
  /** Remembers the column choice per table (localStorage). */
  id: string
  columns: Column<R>[]
  rows: R[]
  rowKey: (row: R) => string
  onRowClick?: (row: R) => void
  /** CSV file name, without .csv. */
  exportName?: string
  empty?: ReactNode
  pageSize?: number
}

const PAGE_SIZES = [10, 25, 50, 100]

function load(id: string): string[] | null {
  try {
    const v = localStorage.getItem(`kamra.table.${id}`)
    return v ? JSON.parse(v) : null
  } catch {
    return null
  }
}

function save(id: string, hidden: string[]) {
  try {
    localStorage.setItem(`kamra.table.${id}`, JSON.stringify(hidden))
  } catch {
    // private window or blocked storage: the choice lasts this visit
  }
}

function raw<R>(c: Column<R>, row: R): string | number | null | undefined {
  if (c.value) return c.value(row)
  const v = (row as Record<string, unknown>)[c.key]
  return typeof v === "number" || typeof v === "string" ? v : v == null ? null : String(v)
}

/** A table every list in Kamra can share: centred headers, click a header
 *  to sort, choose the columns, export what is shown to CSV, and page
 *  through long lists. */
export function DataTable<R>({ id, columns, rows, rowKey, onRowClick, exportName, empty, pageSize = 25 }: Props<R>) {
  useUILanguage()
  const [hidden, setHidden] = useState<string[]>(
    () => load(id) ?? columns.filter((c) => c.hidden).map((c) => c.key))
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null)
  const [page, setPage] = useState(0)
  const [size, setSize] = useState(pageSize)
  const [picking, setPicking] = useState(false)

  const shown = columns.filter((c) => !hidden.includes(c.key))
  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    if (!col) return rows
    return [...rows].sort((a, b) => {
      const x = raw(col, a), y = raw(col, b)
      if (x == null && y == null) return 0
      if (x == null) return 1
      if (y == null) return -1
      const n = typeof x === "number" && typeof y === "number"
        ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true })
      return n * sort.dir
    })
  }, [rows, sort, columns])
  const pages = Math.max(1, Math.ceil(sorted.length / size))
  useEffect(() => { if (page > pages - 1) setPage(0) }, [page, pages])
  const view = sorted.slice(page * size, page * size + size)

  const toggle = (key: string) => {
    const next = hidden.includes(key) ? hidden.filter((k) => k !== key) : [...hidden, key]
    setHidden(next)
    save(id, next)
  }
  const exportCsv = () =>
    downloadCsv(exportName || id, shown.map((c) => c.label), sorted.map((r) => shown.map((c) => raw(c, r))))
  const alignCls = (c: Column<R>) =>
    c.align === "right" ? "text-right tabular-nums" : c.align === "center" ? "text-center" : "text-left"

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <div className="relative">
          <Button variant="outline" onClick={() => setPicking((v) => !v)} aria-expanded={picking}>
            <Columns3 className="size-4" />{translate("Columns")}
          </Button>
          {picking ? (
            <div className="absolute end-0 z-20 mt-1 w-56 rounded-lg border border-zinc-200 bg-white p-2 shadow-lg">
              {columns.filter((c) => c.label).map((c) => (
                <label key={c.key} className="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-zinc-50">
                  <input type="checkbox" checked={!hidden.includes(c.key)} onChange={() => toggle(c.key)} />
                  {c.label}
                </label>
              ))}
            </div>
          ) : null}
        </div>
        <Button variant="outline" onClick={exportCsv} disabled={!rows.length}>
          <Download className="size-4" />{translate("Export CSV")}
        </Button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-xs uppercase text-zinc-400">
            <tr>
              {shown.map((c) => (
                <th key={c.key} className="px-2 py-2 text-center font-medium">
                  {c.noSort || !c.label ? c.label : (
                    <button type="button" className="inline-flex items-center gap-1 uppercase hover:text-zinc-700"
                      onClick={() => setSort((s) => s?.key === c.key
                        ? (s.dir === 1 ? { key: c.key, dir: -1 } : null) : { key: c.key, dir: 1 })}>
                      {c.label}
                      {sort?.key === c.key ? (sort.dir === 1
                        ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />) : null}
                    </button>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view.map((r) => (
              <tr key={rowKey(r)}
                className={`border-t border-zinc-100 align-top ${onRowClick ? "cursor-pointer hover:bg-zinc-50" : ""}`}
                onClick={onRowClick ? () => onRowClick(r) : undefined}>
                {shown.map((c) => (
                  <td key={c.key} className={`px-2 py-2 ${alignCls(c)}`}>
                    {c.render ? c.render(r) : String(raw(c, r) ?? "")}
                  </td>
                ))}
              </tr>
            ))}
            {!rows.length ? (
              <tr><td colSpan={shown.length || 1} className="py-8 text-center text-zinc-400">
                {empty ?? translate("Nothing to show.")}</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
      {sorted.length > PAGE_SIZES[0] ? (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-zinc-500">
          <label className="flex items-center gap-1.5">
            {translate("Rows per page")}
            <select className="rounded border border-zinc-300 px-1.5 py-0.5" value={size}
              onChange={(e) => { setSize(Number(e.target.value)); setPage(0) }}>
              {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <span>{translate("{a}-{b} of {n}", {
            a: page * size + 1, b: Math.min(sorted.length, page * size + size), n: sorted.length })}</span>
          <div className="flex gap-1">
            <Button variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)}
              aria-label={translate("Previous page")}><ChevronLeft className="size-4" /></Button>
            <Button variant="outline" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}
              aria-label={translate("Next page")}><ChevronRight className="size-4" /></Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
