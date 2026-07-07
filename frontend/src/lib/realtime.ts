/*  Live updates. Prefer Frappe's socket (nginx proxies /socket.io to the
    websocket service; the namespace is the site name = hostname). If the
    socket can't connect (e.g. the dev server), fall back to gentle polling
    while the tab is visible. Either way the caller just gets "something
    changed - re-fetch". */

import { io } from "socket.io-client"

export function subscribeRealtime(onChange: () => void): () => void {
  let timer: ReturnType<typeof setInterval> | null = null
  let last = 0
  const fire = () => {
    const now = Date.now()
    if (now - last < 1000) return // collapse bursts
    last = now
    onChange()
  }

  const startPolling = () => {
    if (timer) return
    timer = setInterval(() => {
      if (document.visibilityState === "visible") fire()
    }, 25000)
  }

  const socket = io(`${location.origin}/${location.hostname}`, {
    path: "/socket.io",
    withCredentials: true,
    reconnectionAttempts: 2,
    timeout: 4000,
  })
  socket.on("kamra_changed", fire)
  socket.on("connect_error", startPolling)
  socket.on("connect", () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  })

  return () => {
    socket.close()
    if (timer) clearInterval(timer)
  }
}
