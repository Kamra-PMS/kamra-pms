/*  Take a deposit on a booking before arrival (#114): record it as paid at
    the desk, or send the guest a payment link. Either way it lands on the
    guest folio as an Advance, so the balance at check-in is right. Used in
    the reservation drawer and on the booking-confirmed screen. */

import { useState } from "react"
import { Check, Copy, Link2, MessageCircle } from "lucide-react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { useCashierAuth } from "../lib/cashierAuth"
import { cur, moneyLocale, useLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"

export interface DepositState {
  pct: number
  expected: number
  paid: number
  due: number
  link_url: string | null
  link_amount: number | null
  can_take: boolean
}

const fmt = (n: number) =>
  `${cur()}${Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 2 })}`

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function DepositPanel(props: {
  reservation: string
  deposit: DepositState
  guestPhone?: string | null
  onChanged: (d: DepositState) => void
}) {
  const { t } = useT()
  const loc = useLocale()
  const { ensureUnlocked, status: pinStatus } = useCashierAuth()
  const { deposit } = props
  const [mode, setMode] = useState<"record" | "link" | null>(null)
  const [amount, setAmount] = useState(String(deposit.due || ""))
  const [payMode, setPayMode] = useState(loc.payment_modes[0] ?? "Cash")
  const [reference, setReference] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [link, setLink] = useState<{ url: string; message: string; test_mode: boolean } | null>(
    null,
  )
  const [copied, setCopied] = useState(false)

  if (!deposit.can_take && !deposit.paid) return null

  function open(m: "record" | "link") {
    setMode(m)
    setError(null)
    setAmount(String(deposit.due || ""))
  }

  async function record() {
    setBusy(true)
    setError(null)
    try {
      if (pinStatus?.required) await ensureUnlocked()
      const r = await call<{ deposit: DepositState }>("kamra.api.record_advance", {
        reservation: props.reservation,
        amount: Number(amount),
        mode: payMode,
        reference: reference.trim() || undefined,
      })
      props.onChanged(r.deposit)
      setMode(null)
      setReference("")
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function sendLink() {
    setBusy(true)
    setError(null)
    try {
      const r = await call<{
        url: string
        message: string
        test_mode: boolean
        deposit: DepositState
      }>("kamra.api.deposit_payment_link", {
        reservation: props.reservation,
        amount: Number(amount) || undefined,
      })
      setLink(r)
      props.onChanged(r.deposit)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function simulate() {
    setBusy(true)
    setError(null)
    try {
      const r = await call<{ deposit: DepositState }>("kamra.api.simulate_payment_link", {
        reservation: props.reservation,
      })
      props.onChanged(r.deposit)
      setLink(null)
      setMode(null)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const waPhone = (props.guestPhone || "").replace(/[^\d]/g, "")
  const secured = deposit.expected > 0 && deposit.due <= 0

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-800">{t("Deposit")}</h3>
        <span
          className={
            "rounded-full px-2 py-0.5 text-xs font-medium " +
            (secured
              ? "bg-emerald-50 text-emerald-700"
              : deposit.paid > 0
                ? "bg-amber-50 text-amber-700"
                : "bg-zinc-100 text-zinc-600")
          }
        >
          {secured
            ? t("Secured")
            : deposit.paid > 0
              ? t("Part paid")
              : t("Not paid")}
        </span>
      </div>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
        <div>
          <dt className="text-xs text-zinc-400">
            {deposit.pct > 0 ? t("Expected ({pct}%)", { pct: deposit.pct }) : t("Expected")}
          </dt>
          <dd className="font-semibold tabular-nums text-zinc-900">
            {deposit.expected > 0 ? fmt(deposit.expected) : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-zinc-400">{t("Received")}</dt>
          <dd className="font-semibold tabular-nums text-emerald-700">{fmt(deposit.paid)}</dd>
        </div>
        <div>
          <dt className="text-xs text-zinc-400">{t("Still due")}</dt>
          <dd
            className={
              "font-semibold tabular-nums " +
              (deposit.due > 0 ? "text-rose-600" : "text-zinc-400")
            }
          >
            {fmt(deposit.due)}
          </dd>
        </div>
      </dl>
      <p className="mt-2 text-xs text-zinc-400">
        {t("Carried to the guest folio - at check-in it counts against the bill.")}
      </p>

      {deposit.link_url && !link && (
        <p className="mt-2 flex items-center gap-1.5 truncate text-xs text-zinc-500">
          <Link2 className="size-3.5 shrink-0" aria-hidden />
          {t("Link sent")}
          {deposit.link_amount ? ` · ${fmt(deposit.link_amount)}` : ""} ·{" "}
          <a href={deposit.link_url} target="_blank" rel="noreferrer" className="truncate text-brand-700 hover:underline">
            {deposit.link_url}
          </a>
        </p>
      )}

      {deposit.can_take && !mode && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => open("record")}>
            {t("Record payment")}
          </Button>
          <Button variant="outline" onClick={() => open("link")}>
            <Link2 className="size-4" aria-hidden />
            {t("Send payment link")}
          </Button>
        </div>
      )}

      {mode && (
        <div className="mt-3 space-y-3 rounded-lg bg-zinc-50 p-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-600">{t("Amount")}</span>
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

          {mode === "record" && (
            <>
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
              {payMode !== "Cash" && (
                <input
                  className={inputCls}
                  placeholder={t("Card slip / transfer ref (optional)")}
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                />
              )}
              <div className="flex gap-2">
                <Button disabled={busy || !(Number(amount) > 0)} onClick={record}>
                  {busy ? t("Saving…") : t("Record {amt}", { amt: fmt(Number(amount) || 0) })}
                </Button>
                <Button variant="ghost" onClick={() => setMode(null)}>
                  {t("Cancel")}
                </Button>
              </div>
            </>
          )}

          {mode === "link" && !link && (
            <div className="flex gap-2">
              <Button disabled={busy || !(Number(amount) > 0)} onClick={sendLink}>
                {busy ? t("Creating…") : t("Create link for {amt}", { amt: fmt(Number(amount) || 0) })}
              </Button>
              <Button variant="ghost" onClick={() => setMode(null)}>
                {t("Cancel")}
              </Button>
            </div>
          )}

          {mode === "link" && link && (
            <div className="space-y-2">
              <p className="break-all rounded-md border border-zinc-200 bg-white px-2.5 py-2 text-xs text-zinc-700">
                {link.message}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(link.message)
                      setCopied(true)
                      setTimeout(() => setCopied(false), 1500)
                    } catch {
                      /* clipboard blocked - the text is selectable */
                    }
                  }}
                >
                  {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
                  {copied ? t("Copied") : t("Copy message")}
                </Button>
                {waPhone && (
                  <a
                    className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
                    href={`https://wa.me/${waPhone}?text=${encodeURIComponent(link.message)}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <MessageCircle className="size-4" aria-hidden />
                    WhatsApp
                  </a>
                )}
                {link.test_mode && (
                  <Button variant="ghost" disabled={busy} onClick={simulate}>
                    {t("Simulate payment (test mode)")}
                  </Button>
                )}
              </div>
              <p className="text-xs text-zinc-400">
                {t("When the guest pays, the deposit posts here automatically.")}
              </p>
            </div>
          )}
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
