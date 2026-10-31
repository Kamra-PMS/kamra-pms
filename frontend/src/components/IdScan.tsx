/*  Read an ID with a scanner or the camera.

    A desk scanner in keyboard mode types the passport lines or the QR's
    text into the box; we read it once the typing stops. Where the browser
    can read codes itself (Chrome on Android and Mac, Safari), "Use camera"
    reads the QR on the card instead. The server turns the text into guest
    fields (kamra.id_scan.read_id_scan); nothing is saved from here. */

import { useEffect, useRef, useState } from "react"
import { Camera, Loader2, ScanLine, X } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"

export interface IdRead {
  id_type: string
  id_number: string
  full_name: string
  date_of_birth: string | null
  age: number | null
  gender: string | null
  nationality: string | null
  id_expiry_date?: string | null
  address?: string
  city?: string
  source: string
}

/* the browser's own barcode reader, where it has one */
type Detector = { detect: (v: HTMLVideoElement) => Promise<{ rawValue: string }[]> }
const Native = (window as unknown as {
  BarcodeDetector?: new (o: { formats: string[] }) => Detector
}).BarcodeDetector

export default function IdScan({ onRead, onClose }: {
  onRead: (r: IdRead) => void
  onClose: () => void
}) {
  const { t } = useT()
  const box = useRef<HTMLTextAreaElement>(null)
  const video = useRef<HTMLVideoElement>(null)
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [camera, setCamera] = useState(false)

  useEffect(() => { box.current?.focus() }, [])

  async function read(raw: string) {
    if (!raw.trim() || busy) return
    setBusy(true)
    setErr(null)
    try {
      onRead(await call<IdRead>("kamra.id_scan.read_id_scan", { property: getCurrentProperty(), text: raw }))
    } catch (e) {
      setErr(serverError(e))
      setText("")
      box.current?.focus()
    } finally {
      setBusy(false)
    }
  }

  // a scanner types fast and then stops: read once nothing new has come in
  useEffect(() => {
    if (!text.trim()) return
    const id = window.setTimeout(() => void read(text), 450)
    return () => window.clearTimeout(id)
  }, [text]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!camera || !Native) return
    let stream: MediaStream | null = null
    let timer = 0
    let gone = false
    const detector = new Native({ formats: ["qr_code", "pdf417"] })
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false })
      .then((s) => {
        if (gone) { s.getTracks().forEach((tr) => tr.stop()); return }
        stream = s
        if (!video.current) return
        video.current.srcObject = s
        void video.current.play()
        timer = window.setInterval(async () => {
          if (!video.current?.videoWidth) return
          const [hit] = await detector.detect(video.current).catch(() => [])
          if (hit?.rawValue) { setCamera(false); void read(hit.rawValue) }
        }, 300)
      })
      .catch(() => { setErr(t("No camera, or the browser blocked it. Use the scanner instead.")); setCamera(false) })
    return () => { gone = true; window.clearInterval(timer); stream?.getTracks().forEach((tr) => tr.stop()) }
  }, [camera]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="rounded-xl border border-brand-200 bg-brand-50/40 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-zinc-800">
          <ScanLine className="size-4" aria-hidden />{t("Scan the ID")}
        </p>
        <button type="button" onClick={onClose} aria-label={t("Close")}
          className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700">
          <X className="size-4" />
        </button>
      </div>
      {camera ? (
        <video ref={video} playsInline muted className="max-h-56 w-full rounded-lg bg-zinc-900 object-contain" />
      ) : (
        <textarea
          ref={box}
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t("Scan the passport strip or the QR on the card now. Or paste what the scanner read.")}
          className="w-full resize-none rounded-lg border border-zinc-300 bg-white px-3 py-2 font-mono text-xs focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
          autoComplete="off"
          spellCheck={false}
        />
      )}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {busy && <span className="flex items-center gap-1 text-xs text-zinc-500"><Loader2 className="size-3.5 animate-spin" />{t("Reading")}</span>}
        {Native && (
          <Button type="button" variant="outline" onClick={() => setCamera((c) => !c)}>
            <Camera className="size-4" />{camera ? t("Use the scanner") : t("Use camera")}
          </Button>
        )}
      </div>
      {err && <p className="mt-2 text-xs font-medium text-rose-700">{err}</p>}
    </div>
  )
}
