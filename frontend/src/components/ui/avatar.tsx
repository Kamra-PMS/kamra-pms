import { cn } from "../../lib/utils"

// Soft, legible tints - initials on a colour picked deterministically from
// the name, so the same guest always reads the same.
const PALETTE = [
  "bg-brand-50 text-brand-700",
  "bg-sky-50 text-sky-700",
  "bg-amber-50 text-amber-700",
  "bg-rose-50 text-rose-700",
  "bg-indigo-50 text-indigo-700",
  "bg-emerald-50 text-emerald-700",
]

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return "?"
  const first = parts[0][0] ?? ""
  const last = parts.length > 1 ? parts[parts.length - 1][0] : ""
  return (first + last).toUpperCase()
}

function pick(name: string) {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0
  return PALETTE[Math.abs(h) % PALETTE.length]
}

export function Avatar({
  name,
  className,
}: {
  name: string
  className?: string
}) {
  return (
    <span
      className={cn(
        "grid size-8 shrink-0 place-items-center rounded-full text-[11px] font-semibold",
        pick(name),
        className,
      )}
      aria-hidden
    >
      {initials(name)}
    </span>
  )
}
