/*  Notification settings and the little alert queue behind them.

    Three switches, kept on this device (localStorage), each on by default:
      notify  the on-screen alert for something new (booking, ticket, laundry)
              and its sound. Off means nothing is shown or played for these.
      sound   the sound for those alerts. Off keeps the on-screen alert quiet.
      pos     the POS and kitchen sound (a new order, a new ticket). Separate
              on purpose: a kitchen can stay loud while the desk is quiet.
    The POS switch keeps the key the kitchen screen already used, so nobody's
    existing choice resets. */

import { useSyncExternalStore } from "react"

export type Pref = "notify" | "sound" | "pos"

const KEYS: Record<Pref, string> = {
  notify: "kamra.notify",
  sound: "kamra.sound",
  pos: "kamra.kds.chime",
}

const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())

/** on unless it was switched off */
export function getPref(p: Pref): boolean {
  try { return localStorage.getItem(KEYS[p]) !== "off" } catch { return true }
}

export function setPref(p: Pref, on: boolean) {
  try { localStorage.setItem(KEYS[p], on ? "on" : "off") } catch { /* private mode: lasts until reload */ }
  emit()
}

function subscribe(cb: () => void) {
  listeners.add(cb)
  // another tab changing a switch is picked up too
  const onStorage = (e: StorageEvent) => { if (Object.values(KEYS).includes(e.key ?? "")) cb() }
  window.addEventListener("storage", onStorage)
  return () => { listeners.delete(cb); window.removeEventListener("storage", onStorage) }
}

export function usePref(p: Pref): [boolean, (on: boolean) => void] {
  const on = useSyncExternalStore(subscribe, () => getPref(p), () => true)
  return [on, (v) => setPref(p, v)]
}

/** The same 32 bit djb2 hash as kamra/realtime.py `who()`, so a live-update
 *  event can be recognised as this user's own change. Keep the two identical. */
export function who(user: string | null | undefined): string {
  let h = 5381
  for (const ch of user ?? "") h = ((Math.imul(h, 33) ^ ch.codePointAt(0)!) >>> 0)
  return h.toString(16)
}

/* ── on-screen alerts ───────────────────────────────────────────────── */

export interface Alert {
  id: number
  text: string
}

let alerts: Alert[] = []
let seq = 0
const alertListeners = new Set<() => void>()
const MAX = 3
const SHOW_MS = 7000

export function pushAlert(text: string) {
  const id = ++seq
  alerts = [...alerts, { id, text }].slice(-MAX)
  alertListeners.forEach((l) => l())
  setTimeout(() => dismissAlert(id), SHOW_MS)
}

export function dismissAlert(id: number) {
  alerts = alerts.filter((a) => a.id !== id)
  alertListeners.forEach((l) => l())
}

export function useAlerts(): Alert[] {
  return useSyncExternalStore(
    (cb) => { alertListeners.add(cb); return () => { alertListeners.delete(cb) } },
    () => alerts,
    () => alerts,
  )
}
