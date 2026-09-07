/** Till / kitchen pass: hide PMS chrome and fill the viewport. */

import { useCallback, useEffect, useRef, useState, type RefObject } from "react"

const EVENT = "kamra:kiosk"
/** Focus mode (chrome hidden) is an explicit choice, remembered per device. */
const PREF_KEY = "pos_kiosk"

export function setKiosk(on: boolean) {
  if (on) document.documentElement.dataset.kiosk = "1"
  else delete document.documentElement.dataset.kiosk
  window.dispatchEvent(new CustomEvent(EVENT, { detail: on }))
}

export function useKiosk(auto = false) {
  const [on, setOn] = useState(
    () => typeof document !== "undefined" && document.documentElement.dataset.kiosk === "1",
  )

  useEffect(() => {
    const fn = (e: Event) => setOn(Boolean((e as CustomEvent).detail))
    window.addEventListener(EVENT, fn)
    return () => window.removeEventListener(EVENT, fn)
  }, [])

  useEffect(() => {
    if (!auto) return
    setKiosk(true)
    return () => setKiosk(false)
  }, [auto])

  return {
    on,
    enter: () => setKiosk(true),
    exit: () => setKiosk(false),
    toggle: () => setKiosk(!on),
  }
}

/**
 * Floor screens (POS / Kitchen): focus mode (PMS chrome hidden) is opt-in and
 * remembered per device — the screen never traps staff. Browser fullscreen is
 * a separate, also optional, layer. Escape unwinds: browser FS + focus off in
 * one keypress, without navigating away.
 *
 * Maximize toggles browser fullscreen only — it must not flip focus mode off,
 * which previously brought the sidebar/header back while still "on" the floor.
 */
export function useFloorFullscreen(
  rootRef: RefObject<HTMLElement | null>,
  options?: { blockEscape?: () => boolean },
) {
  const kiosk = useKiosk(false)
  const [browserFs, setBrowserFs] = useState(
    () => typeof document !== "undefined" && !!document.fullscreenElement,
  )
  // Keep the latest gate without re-binding Escape on every parent render.
  const blockEscapeRef = useRef(options?.blockEscape)
  blockEscapeRef.current = options?.blockEscape

  // Enter focus mode on mount only when this device opted in before; always
  // restore the chrome when leaving the floor route.
  useEffect(() => {
    if (localStorage.getItem(PREF_KEY) === "1") setKiosk(true)
    return () => setKiosk(false)
  }, [])

  useEffect(() => {
    const onFs = () => setBrowserFs(!!document.fullscreenElement)
    document.addEventListener("fullscreenchange", onFs)
    return () => document.removeEventListener("fullscreenchange", onFs)
  }, [])

  const exitFloor = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen()
    setKiosk(false)
    localStorage.setItem(PREF_KEY, "0")
  }, [])

  /** Focus mode: hide/show the PMS sidebar and header, remembered per device. */
  const toggleFocus = useCallback(() => {
    const next = document.documentElement.dataset.kiosk !== "1"
    setKiosk(next)
    localStorage.setItem(PREF_KEY, next ? "1" : "0")
  }, [])

  const toggleBrowserFs = useCallback(() => {
    if (document.fullscreenElement) {
      void document.exitFullscreen()
      return
    }
    void rootRef.current?.requestFullscreen?.()
  }, [rootRef])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return
      if (blockEscapeRef.current?.()) {
        // Overlay owns this Escape (e.g. ticket drawer). Stop the browser from
        // also leaving fullscreen so layers unwind one at a time.
        if (document.fullscreenElement) e.preventDefault()
        return
      }
      const el = e.target as HTMLElement | null
      if (el?.closest?.("input, textarea, select, [contenteditable=true]")) return
      // Clear focus mode so chrome returns in one keypress (without navigating
      // away). Also exit browser FS ourselves — preventDefault can stop the
      // native exit.
      if (!document.fullscreenElement && !kiosk.on) return
      e.preventDefault()
      exitFloor()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [exitFloor, kiosk.on])

  return {
    kioskOn: kiosk.on,
    browserFs,
    /** Chrome hidden or browser fullscreen — layout fills the viewport. */
    floorOn: kiosk.on || browserFs,
    toggleBrowserFs,
    toggleFocus,
    exitFloor,
  }
}
