/*  The notification sound: one short file, played for a new order or any
    other alert. A browser will not play audio until the page has been touched
    once, so `unlockSound` primes it on the first tap or key press; before
    that a play simply does nothing rather than throwing. Bursts are thinned
    (a channel sounds at most once per window) so fifty imported bookings do
    not ring for a minute. The switches live in lib/notifications.ts. */

import url from "../assets/sounds/notification.mp3"
import { getPref } from "./notifications"

export type Channel = "general" | "pos"

// the kitchen is a rush, the desk is a trickle: the window differs
const WINDOW_MS: Record<Channel, number> = { general: 4000, pos: 1200 }
const lastAt: Record<Channel, number> = { general: 0, pos: 0 }

let audio: HTMLAudioElement | null = null
function el(): HTMLAudioElement {
  if (!audio) {
    audio = new Audio(url)
    audio.preload = "auto"
    audio.volume = 0.85
  }
  return audio
}

function play() {
  try {
    const a = el()
    a.currentTime = 0
    void a.play().catch(() => { /* not unlocked yet, or the tab is muted: stay quiet */ })
  } catch { /* no audio support */ }
}

/** Sound the alert if this channel's switch is on. Returns whether it played. */
export function playAlert(channel: Channel): boolean {
  if (!getPref(channel === "pos" ? "pos" : "sound")) return false
  const now = Date.now()
  if (now - lastAt[channel] < WINDOW_MS[channel]) return false
  lastAt[channel] = now
  play()
  return true
}

/** For the "Test sound" button: plays regardless of the switches. */
export function previewSound() { play() }

let armed = false
/** Prime audio on the first touch of the page, then stop listening. */
export function unlockSound() {
  if (armed) return
  armed = true
  const prime = () => {
    try {
      const a = el()
      a.muted = true
      void a.play().then(() => { a.pause(); a.currentTime = 0; a.muted = false })
        .catch(() => { a.muted = false })
    } catch { /* ignore */ }
    window.removeEventListener("pointerdown", prime)
    window.removeEventListener("keydown", prime)
  }
  window.addEventListener("pointerdown", prime)
  window.addEventListener("keydown", prime)
}
