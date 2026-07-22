import { useCallback, useEffect, useState } from "react"
import { Download, FileSpreadsheet } from "lucide-react"

import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader } from "../components/ui/card"
import { cur, moneyLocale } from "../lib/money"

interface ExportData {
  rows: Record<string, string | number>[]
  components: string[]
  tax_label: string
  tax_id_label: string
  currency: string
  totals: { invoices: number; taxable: number; total_tax: number; grand_total: number }
}

/** A column in a tool's import file: label shown, and how to pull the value. */
type Col = { header: string; pick: (r: Record<string, string | number>, d: ExportData) => string }

const money = (v: unknown) => String(Number(v ?? 0).toFixed(2))
const compHeader = (c: string) => c.toUpperCase()

/** Per-tool column layouts over the same rows. Tax columns come from the
 *  localization pack (CGST/SGST for India, TAX elsewhere). */
function columnsFor(format: string, d: ExportData): Col[] {
  const taxCols: Col[] = d.components.map((c) => ({
    header: compHeader(c),
    pick: (r) => money(r[c]),
  }))
  if (format === "zoho")
    return [
      { header: "Invoice Number", pick: (r) => String(r.invoice_number) },
      { header: "Invoice Date", pick: (r) => String(r.date) },
      { header: "Customer Name", pick: (r) => String(r.party) },
      { header: "GST Identification Number (GSTIN)", pick: (r) => String(r.party_tax_id) },
      { header: "Place of Supply", pick: (r) => String(r.place_of_supply) },
      { header: "HSN/SAC", pick: (r) => String(r.service_code) },
      { header: "Item Total", pick: (r) => money(r.taxable) },
      ...taxCols,
      { header: "Total", pick: (r) => money(r.grand_total) },
    ]
  if (format === "erpnext")
    return [
      { header: "Invoice No (name)", pick: (r) => String(r.invoice_number) },
      { header: "Date (posting_date)", pick: (r) => String(r.date) },
      { header: "Customer (customer)", pick: (r) => String(r.party) },
      { header: "Tax Id", pick: (r) => String(r.party_tax_id) },
      { header: "Place of Supply", pick: (r) => String(r.place_of_supply) },
      { header: "Net Total (net_total)", pick: (r) => money(r.taxable) },
      { header: "Total Taxes (total_taxes_and_charges)", pick: (r) => money(r.total_tax) },
      { header: "Grand Total (grand_total)", pick: (r) => money(r.grand_total) },
    ]
  if (format === "tally")
    return [
      { header: "Voucher Type", pick: () => "Sales" },
      { header: "Voucher No", pick: (r) => String(r.invoice_number) },
      { header: "Date", pick: (r) => String(r.date) },
      { header: "Party Ledger", pick: (r) => String(r.party) },
      { header: "GSTIN", pick: (r) => String(r.party_tax_id) },
      { header: "Sales Ledger Amount", pick: (r) => money(r.taxable) },
      ...taxCols.map((c) => ({ header: c.header + " Ledger", pick: c.pick })),
      { header: "Invoice Amount", pick: (r) => money(r.grand_total) },
    ]
  // generic
  return [
    { header: "Invoice", pick: (r) => String(r.invoice_number) },
    { header: "Date", pick: (r) => String(r.date) },
    { header: "Party", pick: (r) => String(r.party) },
    { header: d.tax_id_label, pick: (r) => String(r.party_tax_id) },
    { header: "Place of Supply", pick: (r) => String(r.place_of_supply) },
    { header: "SAC/HSN", pick: (r) => String(r.service_code) },
    { header: "Taxable", pick: (r) => money(r.taxable) },
    ...taxCols,
    { header: `${d.tax_label} Total`, pick: (r) => money(r.total_tax) },
    { header: "Grand Total", pick: (r) => money(r.grand_total) },
  ]
}

const FORMATS = [
  { key: "generic", label: "Generic CSV" },
  { key: "tally", label: "Tally" },
  { key: "zoho", label: "Zoho Books" },
  { key: "erpnext", label: "ERPNext" },
]

export default function AccountingExport() {
  const property = getCurrentProperty()
  const today = new Date().toISOString().slice(0, 10)
  const monthAgo = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10)
  const [from, setFrom] = useState(monthAgo)
  const [to, setTo] = useState(today)
  const [format, setFormat] = useState("generic")
  const [data, setData] = useState<ExportData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    call<ExportData>("kamra.accounting.export_invoices", {
      property,
      from_date: from,
      to_date: to,
    })
      .then(setData)
      .catch((e) => setError(serverError(e)))
  }, [property, from, to])
  useEffect(load, [load])

  const esc = (t: string) =>
    /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t

  function download() {
    if (!data) return
    const cols = columnsFor(format, data)
    const csv = [
      cols.map((c) => esc(c.header)).join(","),
      ...data.rows.map((r) => cols.map((c) => esc(c.pick(r, data))).join(",")),
    ].join("\n")
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" })
    const a = document.createElement("a")
    a.href = URL.createObjectURL(blob)
    a.download = `invoices-${format}-${from}-to-${to}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const cols = data ? columnsFor(format, data) : []

  return (
    <div className="space-y-5">
      <header className="flex items-center gap-2">
        <FileSpreadsheet className="size-5 text-brand-600" aria-hidden />
        <h1 className="text-xl font-semibold tracking-tight">
          Accounting Export
        </h1>
        <p className="ml-2 text-sm text-zinc-500">
          Closed invoices, ready to import into your books.
        </p>
      </header>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="date"
              className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              aria-label="From"
            />
            <span className="text-xs text-zinc-400">to</span>
            <input
              type="date"
              className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              aria-label="To"
            />
            <select
              className="rounded-lg border border-zinc-300 px-2.5 py-1.5 text-sm"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              aria-label="Format"
            >
              {FORMATS.map((f) => (
                <option key={f.key} value={f.key}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
          <Button disabled={!data || data.rows.length === 0} onClick={download}>
            <Download className="size-4" aria-hidden />
            Download CSV
          </Button>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          )}
          {data && (
            <>
              <p className="mb-3 text-sm text-zinc-500">
                {data.totals.invoices} invoice
                {data.totals.invoices === 1 ? "" : "s"} · taxable {cur()}
                {data.totals.taxable.toLocaleString(moneyLocale())} · {data.tax_label} {cur()}
                {data.totals.total_tax.toLocaleString(moneyLocale())} · total {cur()}
                {data.totals.grand_total.toLocaleString(moneyLocale())}
              </p>
              {data.rows.length === 0 ? (
                <p className="py-6 text-center text-sm text-zinc-400">
                  No closed invoices in this window.
                </p>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-zinc-200">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-200 bg-zinc-50 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                        {cols.map((c) => (
                          <th key={c.header} className="whitespace-nowrap px-3 py-2">
                            {c.header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {data.rows.slice(0, 12).map((r, i) => (
                        <tr key={i}>
                          {cols.map((c) => (
                            <td
                              key={c.header}
                              className="whitespace-nowrap px-3 py-2"
                            >
                              {c.pick(r, data)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {data.rows.length > 12 && (
                    <p className="px-3 py-2 text-xs text-zinc-400">
                      Showing 12 of {data.rows.length} - download for all.
                    </p>
                  )}
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
