import { useEffect } from "react"
import { X } from "lucide-react"
import { Button } from "./button"

/**
 * Right-side drawer for create/edit forms — Kamra's standard form surface.
 * Content scrolls; header and footer stay pinned.
 */
export function Sheet(props: {
  title: string
  description?: string
  onClose: () => void
  footer?: React.ReactNode
  children: React.ReactNode
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") props.onClose()
    }
    document.addEventListener("keydown", onKey)
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = ""
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true">
      <div
        className="absolute inset-0 bg-zinc-900/40 animate-fade-in"
        onClick={props.onClose}
        aria-hidden
      />
      <div className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col bg-white shadow-2xl animate-sheet-in">
        <div className="flex items-start justify-between border-b border-zinc-100 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold">{props.title}</h2>
            {props.description && (
              <p className="mt-0.5 text-sm text-zinc-400">
                {props.description}
              </p>
            )}
          </div>
          <Button variant="ghost" onClick={props.onClose} aria-label="Close">
            <X className="size-5" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">{props.children}</div>

        {props.footer && (
          <div className="border-t border-zinc-100 bg-zinc-50 px-6 py-4">
            {props.footer}
          </div>
        )}
      </div>
    </div>
  )
}
