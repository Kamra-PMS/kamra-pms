/** Talk instead of type. Uses the browser's own speech recognition
 *  (Chrome, Edge, Safari) - no Kamra server, no AI cost. Hidden where the
 *  browser can't do it (Firefox). The words appear in the box as they are
 *  heard; when the speaker stops, they are handed on as if typed. */
import { useEffect, useRef, useState } from "react"
import { Mic, Square } from "lucide-react"

import { getLang } from "../lib/dir"
import { t as translate, useUILanguage } from "../lib/i18n"
import { cn } from "../lib/utils"

interface SpeechResult {
  isFinal: boolean
  0: { transcript: string }
}
interface Recognizer {
  lang: string
  interimResults: boolean
  continuous: boolean
  start(): void
  stop(): void
  abort(): void
  onresult: ((e: { resultIndex: number; results: ArrayLike<SpeechResult> }) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
}
type RecognizerCtor = new () => Recognizer

const Ctor: RecognizerCtor | undefined =
  typeof window === "undefined"
    ? undefined
    : ((window as unknown as { SpeechRecognition?: RecognizerCtor }).SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: RecognizerCtor }).webkitSpeechRecognition)

// the languages a front desk is most likely to speak; the browser hears each
export const VOICE_LANGS: [string, string][] = [
  ["en-IN", "English (India)"],
  ["hi-IN", "हिन्दी"],
  ["ta-IN", "தமிழ்"],
  ["kn-IN", "ಕನ್ನಡ"],
  ["te-IN", "తెలుగు"],
  ["ml-IN", "മലയാളം"],
  ["en-US", "English (US)"],
  ["en-GB", "English (UK)"],
  ["ar-SA", "العربية"],
  ["es-ES", "Español"],
  ["pt-BR", "Português (Brasil)"],
]

const KEY = "kamra_voice_lang"

function defaultLang(): string {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved && VOICE_LANGS.some(([c]) => c === saved)) return saved
  } catch {
    // private window: fall through to a guess
  }
  const known = (c: string) => VOICE_LANGS.find(([v]) => v.toLowerCase() === c.toLowerCase())?.[0]
  return known(navigator.language) ??
    VOICE_LANGS.find(([v]) => v.startsWith(`${getLang()}-`))?.[0] ??
    "en-IN"
}

export default function VoiceButton(props: {
  disabled?: boolean
  /** called as words arrive; final once the speaker stops */
  onText: (text: string, final: boolean) => void
  onError?: (message: string) => void
}) {
  useUILanguage()
  const [listening, setListening] = useState(false)
  const [lang, setLang] = useState(defaultLang)
  const rec = useRef<Recognizer | null>(null)
  // the newest handlers, so a recognizer started earlier never calls stale ones
  const handlers = useRef(props)
  useEffect(() => {
    handlers.current = props
  })

  useEffect(() => () => rec.current?.abort(), [])

  if (!Ctor) return null

  function start() {
    if (!Ctor || props.disabled) return
    const r = new Ctor()
    r.lang = lang
    r.interimResults = true
    r.continuous = false
    let heard = ""
    r.onresult = (e) => {
      let text = ""
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript
      heard = text.trim()
      handlers.current.onText(heard, false)
    }
    r.onerror = (e) => {
      if (e.error === "no-speech" || e.error === "aborted") return
      handlers.current.onError?.(
        e.error === "not-allowed" || e.error === "service-not-allowed"
          ? translate("Allow the microphone for this site to talk to the agent.")
          : translate("I couldn't hear that. Try again, or type it."),
      )
    }
    r.onend = () => {
      setListening(false)
      rec.current = null
      if (heard) handlers.current.onText(heard, true)
    }
    rec.current = r
    setListening(true)
    r.start()
  }

  function stop() {
    rec.current?.stop()
  }

  function pickLang(code: string) {
    setLang(code)
    try {
      localStorage.setItem(KEY, code)
    } catch {
      // not remembered in a private window; still used now
    }
  }

  return (
    <div className="flex shrink-0 items-center gap-1">
      <select
        value={lang}
        onChange={(e) => pickLang(e.target.value)}
        disabled={listening}
        aria-label={translate("Voice language")}
        title={translate("Voice language")}
        className="hidden max-w-[5.5rem] truncate rounded-md bg-transparent py-1 text-xs text-zinc-500 outline-none hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200 sm:block"
      >
        {VOICE_LANGS.map(([code, name]) => (
          <option key={code} value={code}>
            {name}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={listening ? stop : start}
        disabled={props.disabled && !listening}
        aria-label={listening ? translate("Stop listening") : translate("Speak")}
        title={listening ? translate("Stop listening") : translate("Speak")}
        className={cn(
          "flex size-9 items-center justify-center rounded-full transition disabled:opacity-40",
          listening
            ? "animate-pulse bg-rose-600 text-white"
            : "text-zinc-500 hover:bg-zinc-100 hover:text-brand-700 dark:text-zinc-400 dark:hover:bg-zinc-800",
        )}
      >
        {listening ? <Square className="size-3.5" /> : <Mic className="size-4" />}
      </button>
    </div>
  )
}
