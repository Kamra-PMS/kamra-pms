import { useRef, useState } from "react"
import { Upload } from "lucide-react"
import { uploadFile } from "../lib/api"

/** An image input that accepts an upload OR a pasted URL, with the
 * recommended size/format spelled out so galleries stay tidy. */
export default function ImageField(props: {
  label?: string
  hint: string
  value: string
  onChange: (url: string) => void
  accept?: string
  placeholder?: string
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const pick = async (f: File | undefined) => {
    if (!f) return
    setBusy(true)
    setErr(null)
    try {
      props.onChange(await uploadFile(f))
    } catch {
      setErr("Upload failed — try a smaller file (under 2 MB).")
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ""
    }
  }

  return (
    <div className="block">
      {props.label && (
        <span className="mb-1 block text-sm font-medium text-zinc-600">
          {props.label}
        </span>
      )}
      <div className="flex items-center gap-2">
        {props.value ? (
          <img
            src={props.value}
            alt=""
            className="size-9 shrink-0 rounded-md border border-zinc-200 bg-zinc-50 object-cover"
          />
        ) : null}
        <input
          className="min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
          placeholder={props.placeholder ?? "Upload, or paste an image URL"}
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
        />
        <button
          type="button"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-700 hover:border-brand-400 disabled:opacity-50"
          disabled={busy}
          onClick={() => fileRef.current?.click()}
        >
          <Upload className="size-3.5" aria-hidden />
          {busy ? "Uploading…" : "Upload"}
        </button>
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          accept={props.accept ?? "image/png,image/jpeg,image/webp"}
          onChange={(e) => pick(e.target.files?.[0])}
        />
      </div>
      {props.hint && (
        <p className="mt-1 text-xs text-zinc-400">{props.hint}</p>
      )}
      {err && <p className="mt-1 text-xs text-rose-600">{err}</p>}
    </div>
  )
}
