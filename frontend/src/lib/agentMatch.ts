/** Matching typed or spoken words to a guided Kamra Agent step.
 *  Pure: no React, no network. The food-order basket uses this so
 *  "complete the order" finishes the basket instead of throwing it away
 *  and asking the AI. */

const CLOSE = [
  "done",
  "complete",
  "complete the order",
  "complete order",
  "finish",
  "finish the order",
  "finish order",
  "send",
  "send it",
  "send the order",
  "send to the kitchen",
  "thats all",
  "that is all",
  "that's all",
  "اكمل",
  "اكمل الطلب",
  "اكملي الطلب",
  "اكملي",
  "تم",
  "خلاص",
  "ارسل",
  "أرسل",
  "ارسل للمطبخ",
  "أرسل للمطبخ",
  "أرسل إلى المطبخ",
]

const CLEAR = [
  "clear",
  "clear the order",
  "clear order",
  "cancel the order",
  "امسح الطلب",
  "الغ الطلب",
  "ألغ الطلب",
]

/** Lower-case, fold Arabic letter variants, drop punctuation. */
export function fold(s: string): string {
  return s
    .toLowerCase()
    .replace(/[أإآ]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/ة/g, "ه")
    .replace(/[\u064B-\u0652]/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
}

function listed(q: string, phrases: string[]): boolean {
  const said = fold(q)
  if (!said) return false
  return phrases.some((p) => fold(p) === said)
}

/** Typed "done" / "complete the order" / "اكمل الطلب", plus the labels the
 *  screen is showing in the current language. */
export function isBasketClose(q: string, extra: string[] = []): boolean {
  return listed(q, [...CLOSE, ...extra])
}

export function isBasketClear(q: string, extra: string[] = []): boolean {
  return listed(q, [...CLEAR, ...extra])
}

/** A spoken or typed dish. Exact, or a long enough piece of the label.
 *  A room number in the hint still counts ("101"). */
export function spokenHitsChoice(said: string, label: string, hint?: string): boolean {
  const a = fold(said)
  const b = fold(label)
  if (!a || !b) return false
  if (a === b) return true
  if (a.length >= 3 && (b.includes(a) || a.includes(b))) return true
  if (/\d/.test(a) && hint && ` ${fold(hint)} `.includes(` ${a} `)) return true
  const aw = a.split(" ").filter((w) => w.length > 2)
  const bw = b.split(" ").filter((w) => w.length > 2)
  return aw.length > 0 && bw.length > 0 && aw.every((w) => bw.some((x) => x.includes(w) || w.includes(x)))
}

/** What the chat should say when the AI call fails. "Check the AI key"
 *  only for a rejected key. Anything else keeps the server's own sentence. */
export function agentFailureText(message: string): { text: string; credit: boolean } {
  const msg = (message || "").trim()
  if (/out of credit/i.test(msg)) return { text: msg, credit: true }
  if (/AI provider error \((401|403)\)/i.test(msg) || /no api key/i.test(msg)) {
    return {
      text: "The agent couldn't finish - check the AI key in Settings.",
      credit: false,
    }
  }
  if (msg) return { text: msg, credit: false }
  return { text: "The agent couldn't finish. Try again in a moment.", credit: false }
}
