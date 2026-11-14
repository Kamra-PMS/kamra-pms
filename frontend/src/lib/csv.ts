// One CSV writer for every export in the app. Excel opens it as UTF-8
// because of the BOM. Guest names and notes are typed by people, so a cell
// that would run as a spreadsheet formula (=, +, -, @) gets a leading quote;
// plain numbers, negative ones included, stay numbers.

type Cell = string | number | boolean | null | undefined

const NUMBER = /^-?\d+(\.\d+)?$/

export function csvCell(v: Cell): string {
  let s = v == null ? "" : String(v)
  if (typeof v === "string" && /^[=+\-@\t\r]/.test(s) && !NUMBER.test(s)) s = `'${s}`
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function toCsv(header: string[], rows: Cell[][]): string {
  return [header, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n")
}

export function downloadCsv(name: string, header: string[], rows: Cell[][]): void {
  const blob = new Blob(["﻿" + toCsv(header, rows)], { type: "text/csv;charset=utf-8" })
  const a = document.createElement("a")
  a.href = URL.createObjectURL(blob)
  a.download = name.endsWith(".csv") ? name : `${name}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}
