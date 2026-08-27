/** Till / kitchen pass: hide PMS chrome and fill the viewport. */

import { useCallback, useEffect, useRef, useState, type RefObject } from "react"

const EVENT = "kamra:kiosk"

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
 * Floor screens (POS / Kitchen): auto-hide PMS chrome, optional browser
 * fullscreen, and Escape restores chrome (and exits browser FS).
 *
 * Maximize toggles browser fullscreen only — it must not flip kiosk off,
 * which previously brought the sidebar/header back while still "on" the floor.
 */
export function useFloorFullscreen(
  rootRef: RefObject<HTMLElement | null>,
  options?: { blockEscape?: () => boolean },
) {
  const kiosk = useKiosk(true)
  const [browserFs, setBrowserFs] = useState(
    () => typeof document !== "undefined" && !!document.fullscreenElement,
  )
  // Keep the latest gate without re-binding Escape on every parent render.
  const blockEscapeRef = useRef(options?.blockEscape)
  blockEscapeRef.current = options?.blockEscape

  useEffect(() => {
    const onFs = () => setBrowserFs(!!document.fullscreenElement)
    document.addEventListener("fullscreenchange", onFs)
    return () => document.removeEventListener("fullscreenchange", onFs)
  }, [])

  const exitFloor = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen()
    setKiosk(false)
  }, [])

  const toggleBrowserFs = useCallback(() => {
    if (document.fullscreenElement) {
      void document.exitFullscreen()
      return
    }
    setKiosk(true)
    void rootRef.current?.requestFullscreen?.()
  }, [rootRef])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return
      if (blockEscapeRef.current?.()) return
      const el = e.target as HTMLElement | null
      if (el?.closest?.("input, textarea, select, [contenteditable=true]")) return
      // Clear kiosk so chrome returns in one keypress (without navigating away).
      // Also exit browser FS ourselves — preventDefault can stop the native exit.
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
    exitFloor,
  }
}
