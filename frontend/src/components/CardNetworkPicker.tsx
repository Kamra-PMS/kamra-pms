/** Card type and the last 4 digits, in one row, shown when the payment mode is Card.
    A dropdown, not a button per network: twelve buttons would push the form down. */
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { CARD_NETWORKS } from "../lib/cardNetwork"

interface Props {
  network?: string
  last4?: string
  onChange: (patch: { network?: string; last4?: string }) => void
  /** Size of the form it sits in, so the fields line up with their neighbours:
      sm for the compact dialogs, md for forms with larger labels, lg for forms with large inputs. */
  size?: "sm" | "md" | "lg"
}

const heights = { sm: "h-10 text-sm", md: "h-10 text-sm", lg: "h-11 text-base" } as const
const field =
  "w-full rounded-lg border bg-white px-3 focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export function CardNetworkPicker({ network, last4, onChange, size = "sm" }: Props) {
  const { t } = useT()
  const label = size === "sm" ? "mb-1 block text-xs text-zinc-600" : "mb-1.5 block text-sm font-medium text-zinc-600"
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_8rem] items-start gap-3">
      <label className="block">
        <span className={label}>{t("Card type (from the card machine slip)")}</span>
        <select
          aria-label={t("Card type")}
          aria-required="true"
          value={network ?? ""}
          onChange={(e) => onChange({ network: e.target.value })}
          className={cn(field, heights[size], network ? "border-zinc-300" : "border-amber-400 text-zinc-500")}
        >
          <option value="">{t("Choose card type")}</option>
          {CARD_NETWORKS.map((n) => (
            <option key={n} value={n}>{t(n)}</option>
          ))}
        </select>
      </label>
      <label className="block">
        <span className={label}>{t("Last 4 (optional)")}</span>
        <input
          inputMode="numeric"
          maxLength={4}
          aria-label={t("Last 4 digits of the card (optional)")}
          className={cn(field, heights[size], "border-zinc-300 tabular-nums")}
          placeholder="1234"
          value={last4 ?? ""}
          autoComplete="off"
          onChange={(e) => onChange({ last4: e.target.value.replace(/\D/g, "").slice(0, 4) })}
        />
      </label>
    </div>
  )
}
