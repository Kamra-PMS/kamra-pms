/*  Allowances to approve: what the desk (or an AI agent) asked to write
    off, waiting for a manager, and what was approved or rejected. The
    approver is set in Settings -> Finance -> Cashier controls. */

import { useState } from "react"
import { getCurrentProperty } from "../lib/api"
import AllowanceRequests from "../components/AllowanceRequests"
import { useT } from "../lib/i18n"

const TABS = ["Pending", "Approved", "Rejected"] as const

export default function AllowanceApprovals() {
  const { t } = useT()
  const [tab, setTab] = useState<(typeof TABS)[number]>("Pending")
  const label = { Pending: t("Waiting"), Approved: t("Approved"), Rejected: t("Rejected") }
  return (
    <div className="w-full max-w-3xl space-y-4">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{t("Billing")}</p>
        <h1 className="text-2xl font-semibold">{t("Allowances to approve")}</h1>
        <p className="text-sm text-zinc-500">
          {t("Nothing is taken off a bill until a manager approves it. A rejection is kept with who and why.")}
        </p>
      </div>
      <div className="flex gap-2">
        {TABS.map((k) => (
          <button key={k} type="button" onClick={() => setTab(k)}
            className={`rounded-full border px-3 py-1 text-xs ${tab === k
              ? "border-brand-600 bg-brand-50 text-brand-800"
              : "border-zinc-200 text-zinc-600 hover:bg-zinc-50"}`}>
            {label[k]}
          </button>
        ))}
      </div>
      <AllowanceRequests key={tab} property={getCurrentProperty()} status={tab} showStay />
    </div>
  )
}
