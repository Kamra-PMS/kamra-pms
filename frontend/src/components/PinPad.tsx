import { useCallback, useEffect, useState } from "react"
import { Delete, X } from "lucide-react"
import { cn } from "../lib/utils"
import { Button } from "./ui/button"

type PinPadProps = {
  open: boolean
  title?: string
  subtitle?: string
  mode?: "unlock" | "enroll" | "confirm"
  error?: string | null
  busy?: boolean
  onSubmit: (pin: string) => void | Promise<void>
  onClose?: () => void
  maxLength?: number
}

/** Touch-first numeric PIN pad for front-desk terminals. */
export function PinPad({
  open,
  title = "Cashier PIN",
  subtitle = "Enter your PIN to continue",
  mode = "unlock",
  error,
  busy,
  onSubmit,
  onClose,
  maxLength = 8,
}: PinPadProps) {
  const [pin, setPin] = useState("")
  const [shake, setShake] = useState(false)

  useEffect(() => {
    if (!open) setPin("")
  }, [open])

  useEffect(() => {
    if (error) {
      setShake(true)
      setPin("")
      const t = setTimeout(() => setShake(false), 400)
      return () => clearTimeout(t)
    }
  }, [error])

  const push = useCallback(
    (d: string) => {
      setPin((p) => (p.length >= maxLength ? p : p + d))
    },
    [maxLength],
  )

  const submit = useCallback(async () => {
    if (pin.length < 4 || busy) return
    await onSubmit(pin)
  }, [pin, busy, onSubmit])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key >= "0" && e.key <= "9") push(e.key)
      else if (e.key === "Backspace") setPin((p) => p.slice(0, -1))
      else if (e.key === "Enter") void submit()
      else if (e.key === "Escape") onClose?.()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, push, submit, onClose])

  if (!open) return null

  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"]

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-zinc-950/55 p-4 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-2xl border border-zinc-200 bg-white p-5 shadow-xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900">{title}</h2>
            <p className="mt-0.5 text-sm text-zinc-500">{subtitle}</p>
          </div>
          {onClose ? (
            <button
              type="button"
              aria-label="Close"
              className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
              onClick={onClose}
            >
              <X className="size-4" />
            </button>
          ) : null}
        </div>

        <div
          className={cn(
            "mb-4 flex h-12 items-center justify-center gap-2 rounded-xl bg-zinc-50",
            shake && "animate-pulse",
          )}
        >
          {Array.from({ length: Math.max(4, pin.length || 4) }).map((_, i) => (
            <span
              key={i}
              className={cn(
                "size-2.5 rounded-full",
                i < pin.length ? "bg-zinc-800" : "bg-zinc-300",
              )}
            />
          ))}
        </div>

        {error ? (
          <p className="mb-3 text-center text-sm text-rose-600">{error}</p>
        ) : null}

        <div className="grid grid-cols-3 gap-2">
          {keys.map((k, i) =>
            k === "" ? (
              <div key={`empty-${i}`} />
            ) : (
              <button
                key={k + i}
                type="button"
                disabled={busy}
                className="flex h-14 items-center justify-center rounded-xl bg-zinc-100 text-xl font-semibold text-zinc-800 hover:bg-zinc-200 active:bg-zinc-300 disabled:opacity-50"
                onClick={() =>
                  k === "⌫" ? setPin((p) => p.slice(0, -1)) : push(k)
                }
              >
                {k === "⌫" ? <Delete className="size-5" /> : k}
              </button>
            ),
          )}
        </div>

        <Button
          className="mt-4 w-full"
          disabled={busy || pin.length < 4}
          onClick={() => void submit()}
        >
          {busy
            ? "Checking…"
            : mode === "enroll"
              ? "Set PIN"
              : mode === "confirm"
                ? "Confirm"
                : "Unlock"}
        </Button>
      </div>
    </div>
  )
}
