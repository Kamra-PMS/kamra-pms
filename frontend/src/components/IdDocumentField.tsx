import { useCallback, useRef, useState } from "react"
import { Camera, Check, Loader2, RefreshCw, TriangleAlert } from "lucide-react"
import { call } from "../lib/api"
import { Button } from "./ui/button"
import { cn } from "../lib/utils"

/* Capture a photo of a guest's ID.
 *
 * Deliberately does NOT use lib/api.ts `uploadFile()`. That helper hardcodes
 * is_private="0" and sends no doctype/docname, so whatever it uploads lands on
 * a public, guessable /files/ URL attached to nothing. That is fine for a menu
 * photo and catastrophic for an Aadhaar card. This posts a data URL to a
 * token- or role-gated Kamra endpoint that forces is_private=1 instead.
 *
 * One component, two callers: the guest's check-in page passes
 * kamra.public_api.precheckin_upload_id + a token, the desk passes
 * kamra.api.upload_id_document + a reservation. Mirrors the backend, where
 * both gates land in the same storage helper.
 */

const MAX_EDGE = 1600
const QUALITY = 0.8

/** Downscale before upload. This is a UX measure, not a security one - a 12MB
 *  phone photo over hotel wifi is a failed check-in. The server re-encodes and
 *  trusts nothing that arrives from here. */
async function toDownscaledDataUrl(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement("canvas")
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  const ctx = canvas.getContext("2d")
  if (!ctx) throw new Error("Couldn't read that photo. Please try again.")
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close?.()
  return canvas.toDataURL("image/jpeg", QUALITY)
}

export function IdDocumentField({
  method, params, uploaded, onUploaded, label = "Add a photo of your ID", hint,
}: {
  /** Whitelisted method: the guest's token endpoint or the desk's. */
  method: string
  /** Everything but `data` - a token, or a reservation. */
  params: Record<string, unknown>
  /** Server-side truth: has this booking already got one? */
  uploaded: boolean
  onUploaded: () => void
  label?: string
  hint?: string
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const pick = useCallback(async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    setErr(null)
    try {
      const data = await toDownscaledDataUrl(file)
      await call(method, { ...params, data })
      // Kept only for this session: Frappe refuses a Guest session any private
      // file, so after a reload the guest sees "received", never the image.
      setPreview(data)
      onUploaded()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ""
    }
  }, [method, params, onUploaded])

  const have = uploaded || !!preview

  return (
    <div>
      <input
        ref={fileRef}
        type="file"
        accept="image/jpeg,image/png"
        capture="environment"
        className="hidden"
        onChange={(e) => void pick(e.target.files?.[0])}
      />

      {preview && (
        <img src={preview} alt="Your ID"
          className="mb-2 max-h-44 w-auto rounded-lg border border-zinc-200" />
      )}

      <div className={cn("flex items-center gap-3 rounded-lg border p-3",
        have ? "border-emerald-300 bg-emerald-50/60" : "border-zinc-300 bg-white")}>
        {have ? (
          <Check className="size-5 shrink-0 text-emerald-600" />
        ) : (
          <Camera className="size-5 shrink-0 text-zinc-400" />
        )}
        <div className="min-w-0 flex-1">
          <div className={cn("text-sm font-semibold",
            have ? "text-emerald-800" : "text-zinc-700")}>
            {have ? "ID photo received" : label}
          </div>
          {hint && !have && <div className="mt-0.5 text-xs text-zinc-500">{hint}</div>}
        </div>
        <Button type="button" variant="outline" disabled={busy}
          onClick={() => fileRef.current?.click()} className="shrink-0">
          {busy ? <Loader2 className="size-4 animate-spin" />
            : have ? <RefreshCw className="size-4" />
              : <Camera className="size-4" />}
          {busy ? "Uploading" : have ? "Replace" : "Add photo"}
        </Button>
      </div>

      {err && (
        <div className="mt-2 flex items-start gap-1.5 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">
          <TriangleAlert className="mt-px size-3.5 shrink-0" />{err}
        </div>
      )}
    </div>
  )
}
