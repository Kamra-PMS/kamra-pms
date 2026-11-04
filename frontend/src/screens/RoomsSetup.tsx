import { useRef, useState } from "react"
import { Check, Download, Plus, Upload } from "lucide-react"
import { ResourceScreen } from "../components/ResourceScreen"
import { Sheet } from "../components/ui/sheet"
import { Button } from "../components/ui/button"
import { Badge } from "../components/ui/badge"
import { call, getCurrentProperty } from "../lib/api"
import { useAuth } from "../lib/auth"
import { serverError } from "../lib/resource"
import { t as translate, useUILanguage } from "../lib/i18n"
import { roomsConfig } from "./configs"
import { AddRooms } from "./AdminRooms"

/** Admin → Rooms: the generic room list, a numbered run on one floor
 *  (kamra.floors.add_rooms), and a spreadsheet import for a property that
 *  already has its rooms in a file (kamra.golive.*_rooms). Room types come
 *  first: they carry rates and capacity. */

interface Issue { row: number; room: string; error: string }
interface Preview {
  ok: number; skipped: number; new: number; existing: number
  issues: Issue[]
  sample: { room_number: string; room_type: string; floor: string; existing: string | null }[]
}
interface Report { created: number; updated: number; skipped: number; issues: Issue[] }

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function RoomsSetup() {
  useUILanguage()
  const { roles } = useAuth()
  const canImport = roles.some((r) => ["Hotel Admin", "System Manager", "Administrator"].includes(r))
  const [importing, setImporting] = useState(false)
  const [adding, setAdding] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const reload = () => setReloadKey((k) => k + 1)
  return (
    <>
      <ResourceScreen
        key={reloadKey}
        config={roomsConfig}
        headerAction={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setAdding(true)}>
              <Plus className="mr-1 size-4" aria-hidden />{translate("Add rooms")}
            </Button>
            {canImport && (
              <Button variant="outline" onClick={() => setImporting(true)}>
                <Upload className="mr-1 size-4" aria-hidden />{translate("Import rooms")}
              </Button>
            )}
          </div>
        }
      />
      {adding && (
        <AddRooms onClose={() => setAdding(false)} onDone={() => { setAdding(false); reload() }} />
      )}
      {importing && (
        <RoomImport onClose={() => setImporting(false)} onDone={() => setReloadKey((k) => k + 1)} />
      )}
    </>
  )
}

function RoomImport({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const property = getCurrentProperty()
  const fileRef = useRef<HTMLInputElement>(null)
  const [csv, setCsv] = useState("")
  const [preview, setPreview] = useState<Preview | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run<T>(method: string, then: (r: T) => void) {
    setBusy(true)
    setError(null)
    try {
      then(await call<T>(method, { property, csv_text: csv }))
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  function downloadTemplate() {
    const text = "Room Number,Room Type,Floor,Notes\n101,DLX,1,Sea view\n102,DLX,1,\n201,STD,2,\n"
    const a = document.createElement("a")
    a.href = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" }))
    a.download = "kamra-rooms.csv"
    a.click()
    URL.revokeObjectURL(a.href)
  }

  function onFile(f: File | undefined) {
    if (!f) return
    const reader = new FileReader()
    reader.onload = () => { setCsv(String(reader.result || "")); setPreview(null) }
    reader.readAsText(f)
  }

  return (
    <Sheet
      title={translate("Import rooms")}
      description={translate("One row per room: room number, room type (code or name), floor and notes. Set up the room types first. Rooms that already exist are updated, never duplicated.")}
      onClose={onClose}
      wide
      footer={
        report ? (
          <Button className="w-full" onClick={onClose}>{translate("Done")}</Button>
        ) : preview ? (
          <div className="flex gap-2">
            <Button className="flex-1" disabled={busy || preview.ok === 0}
              onClick={() => run<Report>("kamra.golive.run_rooms", (r) => { setReport(r); setPreview(null); onDone() })}>
              {translate("Import {n} rooms ({a} new, {b} updated)", { n: preview.ok, a: preview.new, b: preview.existing })}
            </Button>
            <Button variant="outline" onClick={() => setPreview(null)}>{translate("Back")}</Button>
          </div>
        ) : (
          <Button className="w-full" disabled={busy || !csv.trim()}
            onClick={() => run<Preview>("kamra.golive.preview_rooms", setPreview)}>
            {translate("Preview changes")}
          </Button>
        )
      }
    >
      <div className="space-y-4">
        {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        {report ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-800">
            <p className="flex items-center gap-2 font-semibold">
              <Check className="size-5" aria-hidden />{translate("Rooms imported")}</p>
            <p className="mt-1 text-sm">
              {translate("{a} new · {b} updated · {c} skipped", { a: report.created, b: report.updated, c: report.skipped })}
            </p>
            <Issues issues={report.issues} />
          </div>
        ) : preview ? (
          <>
            <table className="w-full text-sm">
              <thead className="text-start text-xs text-zinc-500">
                <tr>
                  <th className="py-1 text-start">{translate("Room")}</th>
                  <th className="py-1 text-start">{translate("Room type")}</th>
                  <th className="py-1 text-start">{translate("Floor")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {preview.sample.map((r) => (
                  <tr key={r.room_number} className="border-t border-zinc-100">
                    <td className="py-1.5 font-medium">{r.room_number}</td>
                    <td className="py-1.5">{r.room_type}</td>
                    <td className="py-1.5">{r.floor}</td>
                    <td className="py-1.5 text-end">
                      {r.existing ? <Badge tone="sky">{translate("update")}</Badge> : <Badge tone="green">{translate("new")}</Badge>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {preview.ok > preview.sample.length && (
              <p className="text-xs text-zinc-500">{translate("…and {n} more", { n: preview.ok - preview.sample.length })}</p>
            )}
            <Issues issues={preview.issues} />
          </>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={downloadTemplate}>
                <Download className="mr-1 size-4" aria-hidden />{translate("Download template")}</Button>
              <Button variant="outline" onClick={() => fileRef.current?.click()}>
                <Upload className="mr-1 size-4" aria-hidden />{translate("Upload .csv")}</Button>
              <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden"
                onChange={(e) => onFile(e.target.files?.[0])} />
            </div>
            <textarea className={`${inputCls} h-56 font-mono text-xs`}
              placeholder={"Room Number,Room Type,Floor,Notes\n101,DLX,1,Sea view"}
              value={csv} onChange={(e) => { setCsv(e.target.value); setPreview(null) }} />
          </>
        )}
      </div>
    </Sheet>
  )
}

function Issues({ issues }: { issues: Issue[] }) {
  if (!issues.length) return null
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
      <p className="mb-1 font-medium">{translate("{n} row(s) skipped", { n: issues.length })}</p>
      <ul className="space-y-0.5 text-xs">
        {issues.map((i) => (
          <li key={i.row}>{translate("Row {row}", { row: i.row })}{i.room ? ` (${i.room})` : ""}: {i.error}</li>
        ))}
      </ul>
    </div>
  )
}
