/*  The guest profile's Documents card: the ID type, number, place of issue,
    dates, the scan, and the address proof, with whether the papers are
    already on file, still valid, and have been used on earlier stays, so
    the desk reuses them instead of asking again. Edits go to the Guest
    record. Everything here is a warning or a record: it never blocks a
    check-in. Data from kamra.api.guest_journey (documents). */

import { useState } from "react"
import { FileX2, ImageOff, ShieldCheck } from "lucide-react"
import { idDocumentImage } from "../lib/api"
import { serverError, updateResource } from "../lib/resource"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"

export interface GuestDocs {
  id: {
    type: string | null
    number: string | null
    place_of_issue: string | null
    issue_date: string | null
    expiry_date: string | null
    status: "none" | "valid" | "expiring" | "expired"
    on_file: boolean
    scan_reservation: string | null
    scan_on: string | null
  }
  address_proof: { on_file: boolean }
  used: { count: number; last_on: string | null; last_reservation: string | null }
  retention: "Store" | "Verify & Discard" | null
}

const ID_TYPES = ["Aadhaar", "Passport", "Driving License", "Voter ID", "PAN", "Other"]

const label = "mb-1 block text-xs font-medium uppercase tracking-wider text-zinc-400"
const input =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function GuestDocuments({ guestId, docs, onSaved }: {
  guestId: string
  docs: GuestDocs
  onSaved: () => void
}) {
  const { t } = useT()
  const id = docs.id
  const [type, setType] = useState(id.type ?? "")
  const [number, setNumber] = useState(id.number ?? "")
  const [place, setPlace] = useState(id.place_of_issue ?? "")
  const [issued, setIssued] = useState(id.issue_date ?? "")
  const [expires, setExpires] = useState(id.expiry_date ?? "")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [scan, setScan] = useState<string | null>(null)
  const [scanBusy, setScanBusy] = useState(false)

  const dirty =
    type !== (id.type ?? "") || number !== (id.number ?? "") || place !== (id.place_of_issue ?? "") ||
    issued !== (id.issue_date ?? "") || expires !== (id.expiry_date ?? "")

  async function save() {
    setBusy(true)
    try {
      await updateResource("Guest", guestId, {
        id_type: type, id_number: number, id_place_of_issue: place,
        id_issue_date: issued || null, id_expiry_date: expires || null,
      })
      setErr(null)
      onSaved()
    } catch (e) { setErr(serverError(e)) } finally { setBusy(false) }
  }

  async function viewScan() {
    if (!id.scan_reservation) return
    setScanBusy(true)
    try {
      setScan((await idDocumentImage(id.scan_reservation)).data)
      setErr(null)
    } catch (e) { setErr(serverError(e)) } finally { setScanBusy(false) }
  }

  const status = {
    none: { tone: "zinc", text: t("No ID on file") },
    valid: { tone: "green", text: t("ID on file") },
    expiring: { tone: "amber", text: t("Expires {date}", { date: id.expiry_date ?? "" }) },
    expired: { tone: "rose", text: t("Expired {date}", { date: id.expiry_date ?? "" }) },
  }[id.status] as { tone: "zinc" | "green" | "amber" | "rose"; text: string }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("Documents")}</CardTitle>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={status.tone}>{status.text}</Badge>
          {docs.used.count > 0 && (
            <Badge tone="brand">
              {docs.used.count === 1
                ? t("Used on 1 earlier stay")
                : t("Used on {n} earlier stays", { n: docs.used.count })}
              {docs.used.last_on ? ` · ${t("last {date}", { date: docs.used.last_on.slice(0, 10) })}` : ""}
            </Badge>
          )}
          <Badge tone={docs.address_proof.on_file ? "green" : "zinc"}>
            {docs.address_proof.on_file ? t("Address proof on file") : t("No address proof")}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className={label}>{t("Document type")}</span>
            <input list="guest-id-types" className={input} value={type}
              onChange={(e) => setType(e.target.value)} />
            <datalist id="guest-id-types">
              {ID_TYPES.map((x) => <option key={x} value={x} />)}
            </datalist>
          </label>
          <label className="block text-sm">
            <span className={label}>{t("ID number")}</span>
            <input className={input} value={number} onChange={(e) => setNumber(e.target.value)} />
          </label>
          <label className="block text-sm">
            <span className={label}>{t("Place of issue")}</span>
            <input className={input} value={place} onChange={(e) => setPlace(e.target.value)} />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className={label}>{t("Date of issue")}</span>
              <input type="date" className={input} value={issued} onChange={(e) => setIssued(e.target.value)} />
            </label>
            <label className="block text-sm">
              <span className={label}>{t("Date of expiry")}</span>
              <input type="date" className={cn(input, id.status === "expired" && "border-rose-300")}
                value={expires} min={issued || undefined} onChange={(e) => setExpires(e.target.value)} />
            </label>
          </div>
        </div>

        {/* the proofs themselves, or the plain "none" the desk can act on */}
        <div className="flex flex-wrap gap-3">
          {scan ? (
            <img src={scan} alt={t("ID scan")} className="h-28 rounded-lg border border-zinc-200 object-cover" />
          ) : id.scan_reservation ? (
            <button type="button" onClick={viewScan} disabled={scanBusy}
              className="flex h-28 w-44 flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-brand-400 bg-brand-50/40 text-xs font-medium text-brand-700 hover:bg-brand-50">
              <ShieldCheck className="size-6" aria-hidden />
              {scanBusy ? t("Opening…") : t("View ID scan")}
              {id.scan_on ? <span className="font-normal text-zinc-500">{id.scan_on.slice(0, 10)}</span> : null}
            </button>
          ) : (
            <div className="flex h-28 w-44 flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-zinc-300 bg-zinc-50 text-xs text-zinc-400">
              <ImageOff className="size-6" aria-hidden />{t("No ID proof")}
            </div>
          )}
          <div className={cn("flex h-28 w-44 flex-col items-center justify-center gap-1 rounded-lg border border-dashed text-xs",
            docs.address_proof.on_file ? "border-emerald-300 bg-emerald-50/50 text-emerald-700" : "border-zinc-300 bg-zinc-50 text-zinc-400")}>
            {docs.address_proof.on_file
              ? <><ShieldCheck className="size-6" aria-hidden />{t("Address proof on file")}</>
              : <><FileX2 className="size-6" aria-hidden />{t("No address proof")}</>}
          </div>
        </div>

        {docs.retention === "Verify & Discard" && (
          <p className="rounded-lg bg-zinc-50 px-3 py-2 text-xs text-zinc-600">
            {t("This property deletes ID scans at checkout and keeps only the last 4 digits. The profile keeps the type, dates and that the ID was verified. Ask for the ID again on a new stay.")}
          </p>
        )}
        {err && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}
        <Button variant="outline" disabled={busy || !dirty} onClick={save}>
          {busy ? t("Saving…") : t("Save documents")}
        </Button>
      </CardContent>
    </Card>
  )
}
