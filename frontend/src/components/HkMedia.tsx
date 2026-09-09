/* Housekeeping proof media — shared viewers.
 *
 *  Photos/videos a housekeeper attaches to a task (proof of clean) are stored on
 *  the Housekeeping Task. These viewers surface them for the people who review
 *  the work: the supervisor (task panel on the desktop Housekeeping screen) and
 *  the front desk (per-room, to confirm a room is guest-ready). */

import { useCallback, useEffect, useState } from "react"
import { Camera, X } from "lucide-react"
import { call } from "../lib/api"
import { serverError, type Row } from "../lib/resource"

const isVideo = (url: string) => /\.(mp4|mov|webm|m4v|3gp|avi)$/i.test(url)

/** Thumbnail grid with a click-to-enlarge lightbox; optional per-item delete. */
export function HkMediaView({
  urls,
  onDelete,
  empty = "No photos or videos yet.",
}: {
  urls: string[]
  onDelete?: (url: string) => void
  empty?: string
}) {
  const [lightbox, setLightbox] = useState<string | null>(null)
  if (!urls.length) return <p className="text-sm text-zinc-400">{empty}</p>
  return (
    <>
      <div className="flex flex-wrap gap-2">
        {urls.map((url) => (
          <div key={url} className="relative">
            <button
              type="button"
              onClick={() => setLightbox(url)}
              className="block overflow-hidden rounded-lg focus:outline-2 focus:outline-brand-600"
            >
              {isVideo(url) ? (
                <video src={url} muted className="size-20 bg-zinc-100 object-cover" />
              ) : (
                <img src={url} alt="Room clean" className="size-20 object-cover" />
              )}
            </button>
            {onDelete && (
              <button
                type="button"
                aria-label="Remove"
                onClick={() => onDelete(url)}
                className="absolute -right-1.5 -top-1.5 flex size-5 items-center justify-center rounded-full bg-rose-600 text-white shadow active:bg-rose-700"
              >
                <X className="size-3" />
              </button>
            )}
          </div>
        ))}
      </div>
      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => setLightbox(null)}
        >
          <button
            type="button"
            aria-label="Close"
            className="absolute right-4 top-4 text-white"
            onClick={() => setLightbox(null)}
          >
            <X className="size-7" />
          </button>
          {isVideo(lightbox) ? (
            <video
              src={lightbox}
              controls
              autoPlay
              className="max-h-[85vh] max-w-full rounded-lg"
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <img
              src={lightbox}
              alt="Room clean"
              className="max-h-[85vh] max-w-full rounded-lg"
              onClick={(e) => e.stopPropagation()}
            />
          )}
        </div>
      )}
    </>
  )
}

/** Desktop Housekeeping screen — `extra` panel shown when a supervisor opens a
 *  task. Lists that task's proof photos/videos, with delete. */
export function HkTaskMediaPanel({ row }: { row: Row; reload: () => void }) {
  const [urls, setUrls] = useState<string[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const loadMedia = useCallback(() => {
    call<string[]>("kamra.api.hk_task_media", { task: row.name })
      .then(setUrls)
      .catch((e) => setErr(serverError(e)))
  }, [row.name])
  useEffect(loadMedia, [loadMedia])

  async function del(url: string) {
    if (!confirm("Remove this photo/video?")) return
    try {
      await call("kamra.api.hk_delete_media", { task: row.name, file_url: url })
      loadMedia()
    } catch (e) {
      setErr(serverError(e))
    }
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-zinc-700">Cleaning photos &amp; videos</h3>
      {err && <p className="text-sm text-rose-600">{err}</p>}
      {urls === null ? (
        <p className="text-sm text-zinc-400">Loading…</p>
      ) : (
        <HkMediaView
          urls={urls}
          onDelete={del}
          empty="No proof photos were uploaded for this task."
        />
      )}
    </div>
  )
}

/** Front desk — a small camera button for a room. On click it fetches that
 *  room's recent cleaning media and opens the viewer, so reception can confirm
 *  the room is genuinely guest-ready. */
export function RoomMediaButton({ room }: { room: string }) {
  const [open, setOpen] = useState(false)
  const [urls, setUrls] = useState<string[] | null>(null)

  async function show(e: React.MouseEvent) {
    e.stopPropagation() // don't trigger the tile's status-cycle click
    setOpen(true)
    if (urls === null) {
      try {
        setUrls(await call<string[]>("kamra.api.hk_room_media", { room }))
      } catch {
        setUrls([])
      }
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Cleaning photos"
        onClick={show}
        className="absolute bottom-1 right-1 rounded-full bg-white/80 p-1 text-zinc-600 shadow-sm hover:text-brand-700"
      >
        <Camera className="size-3.5" />
      </button>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={(e) => {
            e.stopPropagation()
            setOpen(false)
          }}
        >
          <div
            className="max-h-[85vh] w-full max-w-md overflow-auto rounded-2xl bg-white p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-zinc-700">
                Cleaning proof — room {room.split("-").pop()}
              </h3>
              <button
                type="button"
                aria-label="Close"
                onClick={() => setOpen(false)}
                className="text-zinc-400 hover:text-zinc-700"
              >
                <X className="size-5" />
              </button>
            </div>
            {urls === null ? (
              <p className="text-sm text-zinc-400">Loading…</p>
            ) : (
              <HkMediaView
                urls={urls}
                empty="No cleaning photos for this room yet."
              />
            )}
          </div>
        </div>
      )}
    </>
  )
}
