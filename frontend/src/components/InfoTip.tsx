import { useEffect, useRef, useState, type ReactNode } from "react"
import { Info } from "lucide-react"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"

const DOCS = "https://kamrapms.com/docs"

/** A small (i) that explains a choice in place, with a link to the docs.
 *  `doc` is a docs page name ("fnb" -> kamrapms.com/docs/fnb). Click or
 *  keyboard to open; Esc or a click elsewhere closes it. */
export function InfoTip({
  children,
  doc,
  label,
  className,
}: {
  children: ReactNode
  doc?: string
  label?: string
  className?: string
}) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    const away = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false)
    document.addEventListener("mousedown", away)
    document.addEventListener("keydown", esc)
    return () => {
      document.removeEventListener("mousedown", away)
      document.removeEventListener("keydown", esc)
    }
  }, [open])

  return (
    <span ref={ref} className={cn("relative inline-flex align-middle", className)}>
      <button
        type="button"
        aria-label={label ?? t("More information")}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="rounded-full text-zinc-400 hover:text-brand-700 focus-visible:text-brand-700 focus-visible:outline-2 focus-visible:outline-brand-600"
      >
        <Info className="size-4" aria-hidden />
      </button>
      {open && (
        <span
          role="note"
          className="absolute start-0 top-6 z-30 w-72 rounded-lg border border-zinc-200 bg-white p-3 text-start text-xs font-normal normal-case leading-relaxed tracking-normal text-zinc-600 shadow-lg"
        >
          {children}
          {doc && (
            <a
              href={`${DOCS}/${doc}`}
              target="_blank"
              rel="noreferrer"
              className="mt-2 block font-medium text-brand-700 hover:underline"
            >
              {t("Read the guide")} →
            </a>
          )}
        </span>
      )}
    </span>
  )
}
