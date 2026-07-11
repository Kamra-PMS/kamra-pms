/** Interface direction / language. Arabic runs right-to-left; everything
 * else left-to-right. Stored per device (like the theme) and applied to the
 * document so the whole UI - staff app, phone apps and the booking page -
 * flips together. */

export type Lang = "en" | "ar"

const KEY = "kamra-lang"

export const getLang = (): Lang =>
  localStorage.getItem(KEY) === "ar" ? "ar" : "en"

export function applyLang(l: Lang) {
  const el = document.documentElement
  el.setAttribute("lang", l)
  el.setAttribute("dir", l === "ar" ? "rtl" : "ltr")
}

export function setLang(l: Lang) {
  localStorage.setItem(KEY, l)
  applyLang(l)
  // let listeners (React trees) re-render with the new direction/strings
  window.dispatchEvent(new Event("kamra:lang"))
}

/** Call once at boot. */
export function initLang() {
  applyLang(getLang())
}
