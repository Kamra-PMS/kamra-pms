import { t as translate, useUILanguage } from "../../lib/i18n"
import { cn } from "../../lib/utils"

/** The on/off pill used across Settings (and the outlet form's switch fields). */
export function Switch({
  on, onToggle, disabled, label, id,
}: {
  on: boolean
  onToggle: () => void
  disabled?: boolean
  label?: string
  id?: string
}) {
  useUILanguage()
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={translate(label)}
      disabled={disabled}
      onClick={onToggle}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600",
        "disabled:cursor-not-allowed disabled:opacity-60",
        on ? "bg-brand-600" : "bg-zinc-300",
      )}
    >
      <span
        className={cn(
          "inline-block size-5 rounded-full bg-white shadow transition-transform",
          on ? "translate-x-5.5 rtl:-translate-x-5.5" : "translate-x-0.5 rtl:-translate-x-0.5",
        )}
      />
    </button>
  )
}
