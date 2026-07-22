import { useEffect, useRef, useState } from "react"
import { Check, Download, Upload, Table2 } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { listResource, serverError } from "../lib/resource"
import { Sheet } from "../components/ui/sheet"
import { Button } from "../components/ui/button"
import { Badge } from "../components/ui/badge"
import { cn } from "../lib/utils"
import { cur } from "../lib/money"

/** Bulk menu upload: paste or drop a spreadsheet export, see exactly how the
 * columns map and what would be created vs updated, then import. Mirrors the
 * booking importer's preview-then-run contract (kamra.menu_import.*). */

interface Outlet {
  name: string
  outlet_name: string
}
interface SampleRow {
  row: number
  item_name: string
  category: string | null
  price: number
  is_veg: number
  is_alcohol: number
  available: number
  prep_station: string
  existing: string | null
}
interface Preview {
  headers: string[]
  mapping: Record<string, string>
  unmapped: string[]
  ok: number
  skipped: number
  new_count: number
  update_count: number
  issues: { row: number; item: string; error: string }[]
  sample: SampleRow[]
  outlets: Outlet[]
}
interface RunReport {
  created: number
  updated: number
  skipped: number
  errors: { row: number; item: string; error: string }[]
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function MenuImport({
  onClose,
  onDone,
}: {
  onClose: () => void
  onDone: () => void
}) {
  const property = getCurrentProperty()
  const [outlets, setOutlets] = useState<Outlet[]>([])
  const [outlet, setOutlet] = useState("")
  const [csv, setCsv] = useState("")
  const [preview, setPreview] = useState<Preview | null>(null)
  const [report, setReport] = useState<RunReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // the picker needs outlets before the first preview runs
  useEffect(() => {
    listResource("POS Outlet", {
      fields: ["name", "outlet_name"],
      filters: [
        ["property", "=", property],
        ["disabled", "=", 0],
      ],
      orderBy: "outlet_name asc",
    })
      .then((r) => {
        const rows = r as unknown as Outlet[]
        setOutlets(rows)
        if (rows.length === 1) setOutlet(rows[0].name)
      })
      .catch(() => {})
  }, [property])

  function downloadTemplate() {
    const headers = [
      "item_name",
      "category",
      "price",
      "veg",
      "alcohol",
      "available",
      "station",
      "description",
    ]
    const rows = [
      ["Paneer Tikka", "Starters", "320", "veg", "no", "yes", "Kitchen", "Char-grilled cottage cheese"],
      ["Chicken Biryani", "Mains", "380", "non-veg", "no", "yes", "Kitchen", ""],
      ["Kingfisher Draught", "Beverages", "250", "", "yes", "yes", "Bar", ""],
    ]
    const text = [headers, ...rows]
      .map((r) => r.map((c) => (/[",]/.test(c) ? `"${c}"` : c)).join(","))
      .join("\n")
    const blob = new Blob(["﻿" + text], {
      type: "text/csv;charset=utf-8",
    })
    const a = document.createElement("a")
    a.href = URL.createObjectURL(blob)
    a.download = "kamra-menu-template.csv"
    a.click()
    URL.revokeObjectURL(a.href)
  }

  function onFile(f: File | undefined) {
    if (!f) return
    const reader = new FileReader()
    reader.onload = () => {
      setCsv(String(reader.result || ""))
      setPreview(null)
      setReport(null)
    }
    reader.readAsText(f)
  }

  async function doPreview() {
    setBusy(true)
    setError(null)
    setReport(null)
    try {
      const p = await call<Preview>("kamra.menu_import.preview_menu_import", {
        property,
        csv_text: csv,
        outlet: outlet || null,
      })
      setPreview(p)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function doImport() {
    setBusy(true)
    setError(null)
    try {
      const r = await call<RunReport>("kamra.menu_import.run_menu_import", {
        property,
        csv_text: csv,
        outlet: outlet || null,
        update_existing: 1,
      })
      setReport(r)
      setPreview(null)
      onDone()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet
      title="Bulk upload menu"
      description="Paste or upload a spreadsheet export — we'll map the columns and show you what changes before anything is saved."
      onClose={onClose}
      wide
      footer={
        report ? (
          <Button className="w-full" onClick={onClose}>
            Done
          </Button>
        ) : preview ? (
          <div className="flex gap-2">
            <Button
              className="flex-1"
              disabled={busy || preview.ok === 0}
              onClick={doImport}
            >
              Import {preview.ok} item{preview.ok === 1 ? "" : "s"}
              {preview.update_count > 0 &&
                ` (${preview.new_count} new, ${preview.update_count} updated)`}
            </Button>
            <Button variant="outline" onClick={() => setPreview(null)}>
              Back
            </Button>
          </div>
        ) : (
          <Button
            className="w-full"
            disabled={busy || !csv.trim()}
            onClick={doPreview}
          >
            Preview changes
          </Button>
        )
      }
    >
      <div className="space-y-4">
        {error && (
          <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </p>
        )}

        {/* ---------- result ---------- */}
        {report ? (
          <div className="space-y-3">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-800">
              <p className="flex items-center gap-2 font-semibold">
                <Check className="size-5" aria-hidden />
                Menu imported
              </p>
              <p className="mt-1 text-sm">
                {report.created} new item{report.created === 1 ? "" : "s"} ·{" "}
                {report.updated} updated
                {report.skipped ? ` · ${report.skipped} skipped` : ""}
              </p>
            </div>
            {report.errors.length > 0 && (
              <IssueList
                title={`${report.errors.length} row(s) couldn't be imported`}
                issues={report.errors}
              />
            )}
          </div>
        ) : preview ? (
          /* ---------- preview ---------- */
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge tone="green">{preview.new_count} new</Badge>
              <Badge tone="sky">{preview.update_count} to update</Badge>
              {preview.skipped > 0 && (
                <Badge tone="rose">{preview.skipped} skipped</Badge>
              )}
            </div>

            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
                Column mapping
              </p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(preview.mapping).map(([canon, header]) => (
                  <span
                    key={canon}
                    className="rounded-lg bg-zinc-100 px-2 py-1 text-xs"
                  >
                    <span className="text-zinc-500">{header}</span>
                    <span className="mx-1 text-zinc-300">→</span>
                    <span className="font-medium">{canon}</span>
                  </span>
                ))}
              </div>
              {preview.unmapped.length > 0 && (
                <p className="mt-1.5 text-xs text-zinc-400">
                  Ignored: {preview.unmapped.join(", ")}
                </p>
              )}
            </div>

            {preview.sample.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
                  First {preview.sample.length} row(s)
                </p>
                <div className="overflow-x-auto rounded-lg border border-zinc-200">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-50">
                      <tr className="text-left text-xs text-zinc-500">
                        <th className="px-2 py-1.5">Item</th>
                        <th className="px-2">Category</th>
                        <th className="px-2 text-right">Price</th>
                        <th className="px-2">Type</th>
                        <th className="px-2">Station</th>
                        <th className="px-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {preview.sample.map((s) => (
                        <tr key={s.row} className="border-t border-zinc-100">
                          <td className="px-2 py-1.5 font-medium">
                            {s.item_name}
                          </td>
                          <td className="px-2 text-zinc-500">
                            {s.category || "—"}
                          </td>
                          <td className="px-2 text-right tabular-nums">
                            {cur()}{s.price}
                          </td>
                          <td className="px-2">
                            <span
                              className={cn(
                                "text-xs font-medium",
                                s.is_veg ? "text-emerald-700" : "text-rose-600",
                              )}
                            >
                              {s.is_alcohol
                                ? "alcohol"
                                : s.is_veg
                                  ? "veg"
                                  : "non-veg"}
                            </span>
                          </td>
                          <td className="px-2 text-zinc-500">
                            {s.prep_station}
                          </td>
                          <td className="px-2">
                            {s.existing ? (
                              <Badge tone="sky">update</Badge>
                            ) : (
                              <Badge tone="green">new</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {preview.issues.length > 0 && (
              <IssueList
                title={`${preview.skipped} row(s) will be skipped`}
                issues={preview.issues}
              />
            )}
          </div>
        ) : (
          /* ---------- input ---------- */
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                Outlet
              </span>
              <select
                className={inputCls}
                value={outlet}
                onChange={(e) => setOutlet(e.target.value)}
              >
                <option value="">Choose an outlet…</option>
                {outlets.map((o) => (
                  <option key={o.name} value={o.name}>
                    {o.outlet_name}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-xs text-zinc-400">
                Used for every row — unless your file has its own{" "}
                <code>outlet</code> column.
              </span>
            </label>

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={downloadTemplate}>
                <Download className="mr-1 size-4" aria-hidden />
                Download template
              </Button>
              <Button variant="outline" onClick={() => fileRef.current?.click()}>
                <Upload className="mr-1 size-4" aria-hidden />
                Upload .csv
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(e) => onFile(e.target.files?.[0])}
              />
            </div>

            <label className="block">
              <span className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-zinc-600">
                <Table2 className="size-4" aria-hidden />
                …or paste the rows here
              </span>
              <textarea
                className={cn(inputCls, "h-56 font-mono text-xs")}
                placeholder={
                  "item_name,category,price,veg,alcohol,available,station\n" +
                  "Paneer Tikka,Starters,320,veg,no,yes,Kitchen"
                }
                value={csv}
                onChange={(e) => {
                  setCsv(e.target.value)
                  setPreview(null)
                }}
              />
            </label>
            <p className="text-xs text-zinc-400">
              Headers are matched loosely — <em>Dish / Item / Product</em>,{" "}
              <em>Rate / Price / MRP</em>, <em>Veg / Non-Veg</em> all work.
              Only <strong>item name</strong> and <strong>price</strong> are
              required. Re-importing updates existing dishes instead of
              duplicating them.
            </p>
          </div>
        )}
      </div>
    </Sheet>
  )
}

function IssueList({
  title,
  issues,
}: {
  title: string
  issues: { row: number; item: string; error: string }[]
}) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-rose-500">
        {title}
      </p>
      <ul className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-rose-100 bg-rose-50/50 p-2">
        {issues.map((i) => (
          <li key={`${i.row}-${i.item}`} className="text-xs text-zinc-600">
            <span className="font-medium">
              Row {i.row}
              {i.item ? ` · ${i.item}` : ""}
            </span>{" "}
            — {i.error}
          </li>
        ))}
      </ul>
    </div>
  )
}
