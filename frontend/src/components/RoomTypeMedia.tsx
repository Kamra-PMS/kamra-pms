import { useEffect, useState } from "react"
import ImageField from "./ImageField"
import { Plus, Trash2 } from "lucide-react"

import { frappeFetch } from "../lib/api"
import { serverError, updateResource, type Row } from "../lib/resource"
import { Button } from "./ui/button"

interface MediaRow {
  media_type: string
  url: string
  caption: string | null
}
interface RTDoc {
  amenities?: string | null
  description?: string | null
  media?: MediaRow[]
}

/** Room-type photos, amenities and description - what the public booking page
 *  shows. Photos are image URLs (the app is URL-based throughout). */
export default function RoomTypeMedia({
  row,
  reload,
}: {
  row: Row
  reload: () => void
}) {
  const name = String(row.name)
  const [doc, setDoc] = useState<RTDoc | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    frappeFetch<{ data: RTDoc }>(
      `/api/resource/Room%20Type/${encodeURIComponent(name)}`,
    )
      .then((r) =>
        setDoc({
          amenities: r.data.amenities,
          description: r.data.description,
          media: r.data.media || [],
        }),
      )
      .catch((e) => setError(serverError(e)))
  }, [name])

  if (!doc)
    return (
      <p className="border-t border-zinc-200 pt-4 text-sm text-zinc-400">
        {error ?? "Loading photos…"}
      </p>
    )

  const media = doc.media ?? []
  const setMedia = (i: number, k: keyof MediaRow, v: string) =>
    setDoc((d) => ({
      ...d!,
      media: (d!.media ?? []).map((m, j) => (j === i ? { ...m, [k]: v } : m)),
    }))
  const addMedia = () =>
    setDoc((d) => ({
      ...d!,
      media: [...(d!.media ?? []), { media_type: "Image", url: "", caption: "" }],
    }))
  const rmMedia = (i: number) =>
    setDoc((d) => ({ ...d!, media: (d!.media ?? []).filter((_, j) => j !== i) }))

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await updateResource("Room Type", name, {
        amenities: doc!.amenities || null,
        description: doc!.description || null,
        media: media
          .filter((m) => m.url.trim())
          .map((m) => ({
            media_type: m.media_type || "Image",
            url: m.url.trim(),
            caption: m.caption || null,
          })),
      })
      reload()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4 border-t border-zinc-200 pt-4">
      <div>
        <div className="mb-1 text-sm font-medium text-zinc-600">
          Photos
        </div>
        <p className="mb-2 text-xs text-zinc-400">
          Shown in the public booking engine. Upload or paste a URL —
          1600×900px (16:9), JPG/WebP; videos as MP4/embed URLs.
        </p>
        <div className="space-y-2">
          {media.map((m, i) => (
            <div key={i} className="flex gap-2">
              <div className="min-w-0 flex-1">
                <ImageField
                  hint=""
                  placeholder="Upload, or paste an image/video URL"
                  value={m.url}
                  onChange={(v) => setMedia(i, "url", v)}
                />
              </div>
              <input
                className="w-28 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                placeholder="Caption"
                value={m.caption ?? ""}
                onChange={(e) => setMedia(i, "caption", e.target.value)}
              />
              <button
                onClick={() => rmMedia(i)}
                aria-label="Remove photo"
                className="rounded-lg px-2 text-rose-500 hover:bg-rose-50"
              >
                <Trash2 className="size-4" />
              </button>
            </div>
          ))}
        </div>
        <Button variant="outline" className="mt-2" onClick={addMedia}>
          <Plus className="size-4" /> Add photo
        </Button>
        {media.filter((m) => m.url.trim()).length > 0 && (
          <div className="mt-3 flex gap-2 overflow-x-auto">
            {media
              .filter((m) => m.url.trim())
              .map((m, i) => (
                <img
                  key={i}
                  src={m.url}
                  alt=""
                  className="h-16 w-24 shrink-0 rounded-lg object-cover"
                  onError={(e) => {
                    ;(e.target as HTMLImageElement).style.opacity = "0.2"
                  }}
                />
              ))}
          </div>
        )}
      </div>

      <label className="block">
        <span className="mb-1 block text-sm font-medium text-zinc-600">
          Amenities (one per line)
        </span>
        <textarea
          rows={3}
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
          placeholder={"King bed\nLake view\nFree Wi-Fi"}
          value={doc.amenities ?? ""}
          onChange={(e) => setDoc((d) => ({ ...d!, amenities: e.target.value }))}
        />
      </label>

      <label className="block">
        <span className="mb-1 block text-sm font-medium text-zinc-600">
          Description
        </span>
        <textarea
          rows={2}
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
          value={doc.description ?? ""}
          onChange={(e) =>
            setDoc((d) => ({ ...d!, description: e.target.value }))
          }
        />
      </label>

      {error && <p className="text-xs text-rose-600">{error}</p>}
      <Button disabled={busy} onClick={save}>
        {busy ? "Saving…" : "Save photos & details"}
      </Button>
    </div>
  )
}
