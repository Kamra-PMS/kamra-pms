/*  The guest profile's Documents card: the ID type, number, place of issue,
    dates, the scan, and the address proof, with whether the papers are
    already on file, still valid, and have been used on earlier stays, so
    the desk reuses them instead of asking again. Edits go to the Guest
    record. Everything here is a warning or a record: it never blocks a
    check-in. Data from kamra.api.guest_journey (documents). */

import { useEffect, useRef, useState } from "react"
import { Camera, FileX2, ImageOff, ShieldCheck, Trash2, Upload, UserRound } from "lucide-react"
import { guestFile, idDocumentImage, removeGuestFile, saveGuestFile, type GuestFileKind } from "../lib/api"
import { serverError, updateResource } from "../lib/resource"
import { useT, t as translate } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"
import CameraCapture from "./CameraCapture"


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
    /** an image kept on the profile itself */
    file: boolean
  }
  address_proof: { on_file: boolean }
  photo: boolean
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

  // a property on Verify & Discard keeps no ID images on the profile
  const keepsIds = docs.retention !== "Verify & Discard"

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
          <Badge tone={status.tone}>{translate(status.text)}</Badge>
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

        {/* the photo and the proofs themselves, or the plain "none" the desk can act on */}
        <div className="flex flex-wrap gap-3">
          <ImageTile guestId={guestId} kind="photo" has={docs.photo} facing="user"
            label={t("Photo")} empty={<><UserRound className="size-6" aria-hidden />{t("No photo (optional)")}</>}
            onChanged={onSaved} />
          {!docs.id.file && id.scan_reservation ? (
            scan ? (
              <img src={scan} alt={t("ID scan")} className="h-28 rounded-lg border border-zinc-200 object-cover" />
            ) : (
              <button type="button" onClick={viewScan} disabled={scanBusy}
                className="flex h-28 w-44 flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-brand-400 bg-brand-50/40 text-xs font-medium text-brand-700 hover:bg-brand-50">
                <ShieldCheck className="size-6" aria-hidden />
                {scanBusy ? t("Opening…") : t("View ID scan")}
                {id.scan_on ? <span className="font-normal text-zinc-500">{id.scan_on.slice(0, 10)}</span> : null}
              </button>
            )
          ) : (
            <ImageTile guestId={guestId} kind="id" has={docs.id.file} facing="environment" canStore={keepsIds}
              label={t("ID proof")} empty={<><ImageOff className="size-6" aria-hidden />{t("No ID proof")}</>}
              onChanged={onSaved} />
          )}
          <ImageTile guestId={guestId} kind="address" has={docs.address_proof.on_file} facing="environment" canStore={keepsIds}
            label={t("Address proof")} empty={<><FileX2 className="size-6" aria-hidden />{t("No address proof")}</>}
            onChanged={onSaved} />
        </div>

        {docs.retention === "Verify & Discard" && (
          <p className="rounded-lg bg-zinc-50 px-3 py-2 text-xs text-zinc-600">
            {t("This property deletes ID scans at checkout and keeps only the last 4 digits. The profile keeps the type, dates and that the ID was verified. Ask for the ID again on a new stay.")}
          </p>
        )}
        {err && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{translate(err)}</p>}
        <Button variant="outline" disabled={busy || !dirty} onClick={save}>
          {busy ? t("Saving…") : t("Save documents")}
        </Button>
      </CardContent>
    </Card>
  )
}

/** One picture slot on the card: shows what is on file, and lets the desk
 *  take a new one with the camera, upload one, or remove it. */
function ImageTile({ guestId, kind, has, label, empty, facing, canStore = true, onChanged }: {
  guestId: string
  kind: GuestFileKind
  has: boolean
  label: string
  empty: React.ReactNode
  facing: "user" | "environment"
  canStore?: boolean
  onChanged: () => void
}) {
  const { t } = useT()
  const [src, setSrc] = useState<string | null>(null)
  const [camera, setCamera] = useState(false)
  const [big, setBig] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!has) { setSrc(null); return }
    let live = true
    guestFile(guestId, kind).then((r) => { if (live) setSrc(r.is_image ? r.data : null) }).catch(() => {})
    return () => { live = false }
  }, [guestId, kind, has])

  async function save(data: string) {
    setBusy(true)
    try {
      await saveGuestFile(guestId, kind, data)
      setSrc(data); setErr(null); setCamera(false)
      onChanged()
    } catch (e) { setErr(serverError(e)) } finally { setBusy(false) }
  }

  function pick(f: File | undefined) {
    if (!f) return
    const r = new FileReader()
    r.onload = () => void save(String(r.result))
    r.readAsDataURL(f)
  }

  async function remove() {
    setBusy(true)
    try {
      await removeGuestFile(guestId, kind)
      setSrc(null); setErr(null)
      onChanged()
    } catch (e) { setErr(serverError(e)) } finally { setBusy(false) }
  }

  return (
    <div className="w-44">
      <div className="mb-1 text-xs font-medium uppercase tracking-wider text-zinc-400">{translate(label)}</div>
      {src ? (
        <button type="button" onClick={() => setBig(true)} title={t("Open full size")} className="block">
          <img src={src} alt={translate(label)} className="h-28 w-44 rounded-lg border border-zinc-200 object-cover" />
        </button>
      ) : (
        <div className={cn("flex h-28 w-44 flex-col items-center justify-center gap-1 rounded-lg border border-dashed text-xs",
          has ? "border-emerald-300 bg-emerald-50/50 text-emerald-700" : "border-zinc-300 bg-zinc-50 text-zinc-400")}>
          {has ? <><ShieldCheck className="size-6" aria-hidden />{t("On file")}</> : translate(empty)}
        </div>
      )}
      {canStore && (
        <div className="mt-1.5 flex items-center gap-1">
          <button type="button" disabled={busy} onClick={() => setCamera(true)}
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-40">
            <Camera className="size-3.5" />{t("Take photo")}
          </button>
          <button type="button" disabled={busy} onClick={() => fileRef.current?.click()}
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-40">
            <Upload className="size-3.5" />{t("Upload")}
          </button>
          {has && (
            <button type="button" disabled={busy} onClick={remove} aria-label={t("Remove")} title={t("Remove")}
              className="ms-auto rounded-md p-1 text-zinc-400 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40">
              <Trash2 className="size-3.5" />
            </button>
          )}
          <input ref={fileRef} type="file" accept="image/jpeg,image/png" className="hidden"
            onChange={(e) => { pick(e.target.files?.[0]); e.target.value = "" }} />
        </div>
      )}
      {err && <p className="mt-1 text-xs text-rose-700">{translate(err)}</p>}
      {big && src && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true"
          aria-label={translate(label)} onClick={() => setBig(false)}>
          <img src={src} alt={translate(label)} className="max-h-full max-w-full rounded-lg object-contain" />
        </div>
      )}
      {camera && (
        <CameraCapture title={translate(label)} facing={facing} onUse={(d) => void save(d)} onClose={() => setCamera(false)} />
      )}
    </div>
  )
}

/** The guest's photo for the profile header, or their initial. */
export function GuestAvatar({ guestId, has, initial }: { guestId: string; has: boolean; initial: string }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    if (!has) { setSrc(null); return }
    let live = true
    guestFile(guestId, "photo").then((r) => { if (live) setSrc(r.data) }).catch(() => {})
    return () => { live = false }
  }, [guestId, has])
  return src ? (
    <img src={src} alt="" className="size-14 rounded-2xl object-cover" />
  ) : (
    <div className="flex size-14 items-center justify-center rounded-2xl bg-brand-50 text-xl font-semibold text-brand-700">
      {initial}
    </div>
  )
}
