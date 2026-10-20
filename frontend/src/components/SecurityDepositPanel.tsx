/*  The refundable security (damage) deposit on a stay - villas usually take
    one. Collect it (held on the guest folio as a liability, not revenue),
    waive it with a reason, withhold all or part against damage at check-out
    (posted to the folio as a charge) and refund the rest through the
    folio's refund path. Every action is one server call; the cashier PIN
    is asked for where money moves, as on the folio. Used in the
    reservation drawer, which is also where check-out happens. */

import { useState } from "react"
import { ShieldCheck } from "lucide-react"
import { call } from "../lib/api"
import { useAuth } from "../lib/auth"
import { serverError } from "../lib/resource"
import { useCashierAuth } from "../lib/cashierAuth"
import { cur, moneyLocale, useLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"

export interface SecurityDepositState {
  name: string | null
  status: "None" | "Required" | "Waived" | "Collected" | "Held" | "Withheld" | "Refunded"
  policy_amount: number
  required: number
  collected: number
  withheld: number
  refunded: number
  held: number
  due: number
  reason: string | null
  folio: string | null
  folio_credit: number
  history: { kind: "Collected" | "Withheld" | "Refunded"; date: string; amount: number; mode?: string; note?: string }[]
  can_collect: boolean
  can_waive: boolean
  can_withhold: boolean
  can_refund: boolean
  blocks_checkout: boolean
}

type Mode = "collect" | "waive" | "withhold" | "refund"

const ADMIN = ["System Manager", "Administrator"]
// mirrors the server's gates (the server decides; this only hides buttons)
const GATES: Record<Mode, string[]> = {
  collect: ["Front Desk", "Finance", "Hotel Admin", ...ADMIN],
  waive: ["Front Desk", "Hotel Admin", ...ADMIN],
  withhold: ["Front Desk", "Finance", "Hotel Admin", ...ADMIN],
  refund: ["Front Desk", "Finance", "Hotel Admin", ...ADMIN],
}

const fmt = (n: number) =>
  `${cur()}${Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 2 })}`

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

const TONE: Record<string, string> = {
  Held: "bg-violet-50 text-violet-700",
  Collected: "bg-violet-50 text-violet-700",
  Required: "bg-amber-50 text-amber-700",
  Waived: "bg-zinc-100 text-zinc-600",
  Withheld: "bg-rose-50 text-rose-700",
  Refunded: "bg-emerald-50 text-emerald-700",
  None: "bg-zinc-100 text-zinc-500",
}

export default function SecurityDepositPanel(props: {
  reservation: string
  deposit: SecurityDepositState
  /** only an in-house or upcoming stay offers to take one when none is set */
  canStart: boolean
  onChanged: () => void
}) {
  const { t } = useT()
  const loc = useLocale()
  const { roles } = useAuth()
  const { ensureUnlocked, status: pinStatus } = useCashierAuth()
  const d = props.deposit
  const [mode, setMode] = useState<Mode | null>(null)
  const [amount, setAmount] = useState("")
  const [payMode, setPayMode] = useState(loc.payment_modes[0] ?? "Cash")
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const allowed = (m: Mode) => GATES[m].some((r) => roles.includes(r))
  const nothingYet = d.status === "None" && d.history.length === 0
  if (nothingYet && !props.canStart) return null

  function open(m: Mode) {
    setMode(m)
    setError(null)
    setText("")
    const last = [...d.history].reverse().find((h) => h.kind === "Collected")?.mode
    if (m === "collect") setAmount(String(d.due || d.policy_amount || ""))
    if (m === "withhold") setAmount("")
    if (m === "refund") {
      setAmount(String(Math.min(d.held, d.folio_credit) || ""))
      if (last && loc.payment_modes.includes(last)) setPayMode(last)
    }
  }

  async function submit() {
    if (!mode) return
    setBusy(true)
    setError(null)
    try {
      if (mode !== "waive" && pinStatus?.required) await ensureUnlocked()
      const args: Record<string, unknown> = { reservation: props.reservation }
      let method = ""
      if (mode === "collect") {
        method = "kamra.api.collect_security_deposit"
        Object.assign(args, { amount: Number(amount), mode: payMode, reference: text.trim() || undefined })
      } else if (mode === "waive") {
        method = "kamra.api.waive_security_deposit"
        args.reason = text.trim()
      } else if (mode === "withhold") {
        method = "kamra.api.withhold_security_deposit"
        Object.assign(args, { amount: Number(amount), reason: text.trim() })
      } else {
        method = "kamra.api.refund_security_deposit"
        Object.assign(args, { amount: Number(amount), mode: payMode, note: text.trim() || undefined })
      }
      await call(method, args)
      setMode(null)
      props.onChanged()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const amt = Number(amount) || 0
  const ready =
    mode === "waive"
      ? text.trim().length > 0
      : mode === "withhold"
        ? amt > 0 && amt <= d.held && text.trim().length > 0
        : mode === "refund"
          ? amt > 0 && amt <= d.held
          : amt > 0
  const label: Record<Mode, string> = {
    collect: t("Collect {amt}", { amt: fmt(amt) }),
    waive: t("Waive deposit"),
    withhold: t("Withhold {amt}", { amt: fmt(amt) }),
    refund: t("Refund {amt}", { amt: fmt(amt) }),
  }

  return (
    <div
      className={
        "rounded-xl border bg-white p-4 " +
        (d.blocks_checkout ? "border-amber-300" : "border-zinc-200")
      }
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-zinc-800">
          <ShieldCheck className="size-4 text-zinc-400" aria-hidden />
          {t("Security deposit")}
        </h3>
        <span className={"rounded-full px-2 py-0.5 text-xs font-medium " + (TONE[d.status] ?? TONE.None)}>
          {d.status === "None" ? t("None taken") : t(d.status)}
        </span>
      </div>

      {!nothingYet && (
        <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-zinc-400">{t("Required")}</dt>
            <dd className="font-semibold tabular-nums text-zinc-900">
              {d.required > 0 ? fmt(d.required) : "-"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-400">{t("Held")}</dt>
            <dd className="font-semibold tabular-nums text-violet-700">{fmt(d.held)}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-400">{t("Withheld")}</dt>
            <dd className={"font-semibold tabular-nums " + (d.withheld > 0 ? "text-rose-600" : "text-zinc-400")}>
              {fmt(d.withheld)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-400">{t("Refunded")}</dt>
            <dd className={"font-semibold tabular-nums " + (d.refunded > 0 ? "text-emerald-700" : "text-zinc-400")}>
              {fmt(d.refunded)}
            </dd>
          </div>
        </dl>
      )}
      <p className="mt-2 text-xs text-zinc-400">
        {nothingYet
          ? t("Refundable damage deposit - held for the guest, not revenue. Refunded or withheld at check-out.")
          : d.status === "Waived" && d.reason
            ? t("Waived: {reason}", { reason: d.reason })
            : t("Held on the guest folio as a liability - not revenue.")}
      </p>

      {d.history.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-zinc-600">
          {d.history.map((h, i) => (
            <li key={i} className="flex justify-between gap-3">
              <span className="min-w-0 truncate">
                {h.date} · {t(h.kind)}
                {h.mode ? ` · ${t(h.mode)}` : ""}
                {h.note ? ` · ${h.note}` : ""}
              </span>
              <span className="shrink-0 tabular-nums">{fmt(h.amount)}</span>
            </li>
          ))}
        </ul>
      )}

      {d.blocks_checkout && (
        <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800">
          {t("Before check-out: withhold anything for damage, then refund the rest.")}
        </p>
      )}

      {!mode && (
        <div className="mt-3 flex flex-wrap gap-2">
          {d.can_collect && allowed("collect") && (
            <Button variant="outline" onClick={() => open("collect")}>
              {d.held > 0 ? t("Collect more") : t("Collect deposit")}
            </Button>
          )}
          {d.can_withhold && allowed("withhold") && (
            <Button variant="outline" onClick={() => open("withhold")}>
              {t("Withhold for damage")}
            </Button>
          )}
          {d.can_refund && allowed("refund") && (
            <Button variant="outline" onClick={() => open("refund")}>
              {t("Refund deposit")}
            </Button>
          )}
          {d.can_waive && allowed("waive") && (
            <Button variant="ghost" onClick={() => open("waive")}>
              {t("Waive")}
            </Button>
          )}
        </div>
      )}

      {mode && (
        <div className="mt-3 space-y-3 rounded-lg bg-zinc-50 p-3">
          {mode !== "waive" && (
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-zinc-600">
                {mode === "withhold" || mode === "refund"
                  ? t("Amount (held {amt})", { amt: fmt(d.held) })
                  : t("Amount")}
              </span>
              <input
                type="number"
                min={0}
                step="0.01"
                inputMode="decimal"
                className={inputCls}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
          )}
          {(mode === "collect" || mode === "refund") && (
            <div role="radiogroup" aria-label={t("Payment mode")} className="flex flex-wrap gap-2">
              {loc.payment_modes.map((m) => (
                <button
                  key={m}
                  type="button"
                  role="radio"
                  aria-checked={payMode === m}
                  onClick={() => setPayMode(m)}
                  className={
                    "rounded-lg border px-3 py-1.5 text-sm font-medium " +
                    (payMode === m
                      ? "border-brand-600 bg-brand-50 text-brand-800"
                      : "border-zinc-200 bg-white text-zinc-600")
                  }
                >
                  {t(m)}
                </button>
              ))}
            </div>
          )}
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-600">
              {mode === "collect"
                ? t("Card slip / transfer ref (optional)")
                : mode === "refund"
                  ? t("Note (optional)")
                  : t("Reason (required)")}
            </span>
            <input
              className={inputCls}
              value={text}
              placeholder={mode === "withhold" ? t("e.g. Broken glass table, photos on file") : undefined}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          {mode === "withhold" && (
            <p className="text-xs text-zinc-500">
              {t("Posts a damage charge to the folio; the held deposit pays it.")}
            </p>
          )}
          {mode === "refund" && d.folio_credit < d.held && (
            <p className="text-xs text-amber-700">
              {t("The folio only has {amt} in credit - settle the bill first, or let the deposit cover it.", {
                amt: fmt(d.folio_credit),
              })}
            </p>
          )}
          <div className="flex gap-2">
            <Button disabled={busy || !ready} onClick={submit}>
              {busy ? t("Saving…") : label[mode]}
            </Button>
            <Button variant="ghost" onClick={() => setMode(null)}>
              {t("Cancel")}
            </Button>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}
    </div>
  )
}
