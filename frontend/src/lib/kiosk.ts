/** Till / kitchen pass: hide PMS chrome and fill the viewport. */

import { useEffect, useState } from "react"

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
