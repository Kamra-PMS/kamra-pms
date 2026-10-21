/*  Take a picture with the device camera: the guest's photo at the desk, or
    a quick shot of an ID card. Opens the camera only while this is on
    screen and stops it on close. When there is no camera, or the browser
    refuses it, it says so plainly and the desk can upload a file instead.
    Hands back a JPEG data URL. */

import { useEffect, useRef, useState } from "react"
import { Camera, RefreshCw, SwitchCamera, X } from "lucide-react"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"

export default function CameraCapture({ title, facing = "user", onUse, onClose }: {
  title: string
  /** "user" for a face, "environment" for a document on a tablet or phone */
  facing?: "user" | "environment"
  onUse: (dataUrl: string) => void
  onClose: () => void
}) {
  const { t } = useT()
  const video = useRef<HTMLVideoElement>(null)
  const [mode, setMode] = useState(facing)
  const [shot, setShot] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (shot) return
    let stream: MediaStream | null = null
    let gone = false
    if (!navigator.mediaDevices?.getUserMedia) {
      setErr(t("This browser cannot use a camera here. Upload a picture instead."))
      return
    }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: mode, width: { ideal: 1280 } }, audio: false })
      .then((s) => {
        if (gone) { s.getTracks().forEach((tr) => tr.stop()); return }
        stream = s
        setErr(null)
        if (video.current) { video.current.srcObject = s; void video.current.play() }
      })
      .catch(() => setErr(t("No camera, or the browser blocked it. Allow the camera, or upload a picture instead.")))
    return () => { gone = true; stream?.getTracks().forEach((tr) => tr.stop()) }
  }, [mode, shot, t])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  function capture() {
    const v = video.current
    if (!v || !v.videoWidth) return
    const c = document.createElement("canvas")
    c.width = v.videoWidth
    c.height = v.videoHeight
    c.getContext("2d")?.drawImage(v, 0, 0)
    setShot(c.toDataURL("image/jpeg", 0.9))
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center p-3 sm:items-center" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-black/50" onClick={onClose} aria-hidden />
      <div className="relative z-10 w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-zinc-800">{title}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700">
            <X className="size-5" />
          </button>
        </div>
        <div className="bg-zinc-900">
          {shot ? (
            <img src={shot} alt={t("Captured picture")} className="mx-auto max-h-[60vh] w-full object-contain" />
          ) : err ? (
            <p className="px-4 py-16 text-center text-sm text-zinc-200">{err}</p>
          ) : (
            <video ref={video} playsInline muted className="mx-auto max-h-[60vh] w-full object-contain" />
          )}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
          {shot ? (
            <>
              <Button variant="outline" onClick={() => setShot(null)}>
                <RefreshCw className="size-4" />{t("Retake")}
              </Button>
              <Button onClick={() => onUse(shot)}>{t("Use this picture")}</Button>
            </>
          ) : (
            <>
              <Button variant="outline" disabled={!!err}
                onClick={() => setMode((m) => (m === "user" ? "environment" : "user"))}
                title={t("Switch between the front and back camera")}>
                <SwitchCamera className="size-4" />{t("Switch camera")}
              </Button>
              <Button disabled={!!err} onClick={capture}>
                <Camera className="size-4" />{t("Take picture")}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
