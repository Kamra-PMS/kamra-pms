import { useState } from "react"
import { CheckCircle2, Download, FileUp, ShieldAlert } from "lucide-react"

import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Card, CardContent } from "../components/ui/card"
import { cn } from "../lib/utils"
import { fmtMoney } from "../lib/money"
import { useT } from "../lib/i18n"

/** Go-live import: move a hotel off its old system on one night, from
 *  Kamra's own CSV templates. Bookings (kamra.migrate), companies and
 *  opening balances (kamra.golive) each preview before anything is written,
 *  then Reconcile ties every file to what is now in Kamra. All amounts are
 *  posted by the server's ledger writers; this screen only sends the files. */

type FileKind = "bookings" | "companies" | "opening"
type Tab = FileKind | "reconcile"

interface Issue {
  row: number
  guest?: string
  name?: string
  who?: string
  type?: string
  error: string
}

interface BookingsPreview {
  mapping: Record<string, string>
  unmapped: string[]
  date_format: string
  ok: number
  skipped: number
  already_imported: number
  issues: Issue[]
}

interface CompaniesPreview {
  mapping: Record<string, string>
  unmapped: string[]
  ok: number
  skipped: number
  new: number
  existing: number
  on_credit: number
  issues: Issue[]
}

interface OpeningCategory {
  category: string
  label: string
  count: number
  total: number
  already_posted: number
}

interface OpeningPreview {
  mapping: Record<string, string>
  unmapped: string[]
  date_format: string
  business_date: string
  ok: number
  skipped: number
  categories: OpeningCategory[]
  issues: Issue[]
}

interface ReconCategory {
  category: string
  label: string
  file_count: number
  file_total: number | null
  kamra_count: number
  kamra_total: number | null
  matched: boolean
  problems: string[]
  by_company?: { company: string; file: number; kamra: number; balance: number; matched: boolean }[]
}

interface Reconciliation {
  business_date: string
  categories: ReconCategory[]
  blockers: string[]
  ready: boolean
}

type Preview = BookingsPreview | CompaniesPreview | OpeningPreview

const TABS: { id: Tab; label: string; hint: string }[] = [
  { id: "bookings", label: "1 · Bookings", hint: "Future, in-house and past stays" },
  { id: "companies", label: "2 · Companies", hint: "Corporate accounts and credit terms" },
  { id: "opening", label: "3 · Opening balances", hint: "In-house folios, city ledger, deposits" },
  { id: "reconcile", label: "4 · Reconcile", hint: "Tie every file to Kamra" },
]

const ENDPOINTS: Record<FileKind, { preview: string; run: string }> = {
  bookings: { preview: "kamra.migrate.preview_import", run: "kamra.migrate.run_import" },
  companies: { preview: "kamra.golive.preview_companies", run: "kamra.golive.run_companies" },
  opening: { preview: "kamra.golive.preview_opening", run: "kamra.golive.run_opening" },
}

const PLACEHOLDER: Record<FileKind, string> = {
  bookings:
    "Reservation No,Guest Name,Phone,Room Type,Room,Check In,Check Out,Adults,Total Amount,Status\n" +
    "R-1042,Asha Rao,+91 98xxxx,Deluxe,204,17/10/2026,21/10/2026,2,24000,In House",
  companies:
    "Company Name,Tax ID,Contact Name,Contact Phone,Contact Email,Credit Allowed,Credit Limit,Credit Days\n" +
    "Acme Travels,,Ravi,+91 98xxxx,accounts@acme.example,Yes,50000,30",
  opening:
    "Type,Reservation No,Guest Name,Company,Invoice No,Invoice Date,Amount,Mode\n" +
    "In-house,R-1042,,,,,12600,\n" +
    "City ledger,,,Acme Travels,INV-881,10/09/2026,18000,\n" +
    "Deposit,R-1077,,,,,3000,UPI",
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3.5 py-2.5 text-base " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

function money(n: number | null | undefined) {
  return n === null || n === undefined ? "—" : fmtMoney(n)
}

export default function GoLiveImport({
  property: propProperty,
  embedded = false,
}: {
  property?: string | null
  embedded?: boolean
}) {
  const { t } = useT()
  const property = propProperty || getCurrentProperty()
  const [tab, setTab] = useState<Tab>("bookings")
  const [files, setFiles] = useState<Record<FileKind, string>>({
    bookings: "",
    companies: "",
    opening: "",
  })
  const [preset, setPreset] = useState("auto")
  const [previews, setPreviews] = useState<Partial<Record<FileKind, Preview>>>({})
  const [reports, setReports] = useState<Partial<Record<FileKind, string>>>({})
  const [reportErrors, setReportErrors] = useState<Partial<Record<FileKind, Issue[]>>>({})
  const [recon, setRecon] = useState<Reconciliation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function setFile(kind: FileKind, text: string) {
    setFiles((f) => ({ ...f, [kind]: text }))
    setPreviews((p) => ({ ...p, [kind]: undefined }))
    setRecon(null)
  }

  async function downloadTemplate(kind: FileKind) {
    setError(null)
    try {
      const tpl = await call<{ filename: string; csv: string }>("kamra.golive.csv_template", { kind })
      const a = document.createElement("a")
      a.href = URL.createObjectURL(new Blob([tpl.csv], { type: "text/csv" }))
      a.download = tpl.filename
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (e) {
      setError(serverError(e))
    }
  }

  async function runStep(kind: FileKind, mode: "preview" | "run") {
    if (!property) return
    setBusy(true)
    setError(null)
    try {
      const args: Record<string, string> = { property, csv_text: files[kind] }
      if (kind === "bookings") args.preset = preset
      const res = await call<Record<string, unknown>>(ENDPOINTS[kind][mode], args)
      if (mode === "preview") {
        setPreviews((p) => ({ ...p, [kind]: res as unknown as Preview }))
        setReports((r) => ({ ...r, [kind]: undefined }))
        setReportErrors((r) => ({ ...r, [kind]: undefined }))
      } else {
        setReports((r) => ({ ...r, [kind]: describeRun(kind, res) }))
        setReportErrors((r) => ({ ...r, [kind]: (res.errors as Issue[]) || [] }))
        setPreviews((p) => ({ ...p, [kind]: undefined }))
        setRecon(null)
      }
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  function describeRun(kind: FileKind, res: Record<string, unknown>): string {
    if (kind === "bookings") {
      return t("{n} booking(s) imported, {h} as past-stay history, {a} already in Kamra", {
        n: Number(res.created ?? 0),
        h: Number(res.history ?? 0),
        a: Number(res.already_imported ?? 0),
      })
    }
    if (kind === "companies") {
      return t("{c} companies created, {u} updated", {
        c: Number(res.created ?? 0),
        u: Number(res.updated ?? 0),
      })
    }
    const posted = (res.posted ?? {}) as Record<string, number>
    const totals = (res.totals ?? {}) as Record<string, number>
    return t(
      "Posted on {date}: {i} in-house ({it}), {d} deposit(s) ({dt}), {r} city ledger ({rt}); {a} already posted",
      {
        date: String(res.business_date ?? ""),
        i: posted.in_house ?? 0,
        it: fmtMoney(totals.in_house ?? 0),
        d: posted.deposit ?? 0,
        dt: fmtMoney(totals.deposit ?? 0),
        r: posted.ar ?? 0,
        rt: fmtMoney(totals.ar ?? 0),
        a: Number(res.already_posted ?? 0),
      },
    )
  }

  async function reconcile() {
    if (!property) return
    setBusy(true)
    setError(null)
    try {
      setRecon(
        await call<Reconciliation>("kamra.golive.reconcile", {
          property,
          bookings_csv: files.bookings,
          companies_csv: files.companies,
          opening_csv: files.opening,
        }),
      )
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const kind = tab === "reconcile" ? null : tab
  const preview = kind ? previews[kind] : undefined

  return (
    <div className="space-y-4">
      {!embedded && (
        <header className="flex flex-wrap items-center gap-2">
          <FileUp className="size-5 text-brand-600" aria-hidden />
          <h1 className="text-xl font-semibold tracking-tight">{t("Go-live import")}</h1>
          <p className="ml-2 text-sm text-zinc-500">
            {t("Bring bookings, companies and opening balances over from your old system, then reconcile before you switch.")}
          </p>
        </header>
      )}
      {!property && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {t("Pick a property first.")}
        </div>
      )}

      <div className="flex flex-wrap gap-1 rounded-xl bg-zinc-100 p-1" role="tablist">
        {TABS.map((tb) => (
          <button
            key={tb.id}
            role="tab"
            aria-selected={tab === tb.id}
            onClick={() => setTab(tb.id)}
            className={cn(
              "flex-1 rounded-lg px-3 py-2 text-left text-sm transition",
              tab === tb.id ? "bg-white font-semibold text-zinc-900 shadow-sm" : "text-zinc-600 hover:text-zinc-900",
            )}
          >
            <span className="block">{t(tb.label)}</span>
            <span className="block text-xs font-normal text-zinc-500">{t(tb.hint)}</span>
          </button>
        ))}
      </div>

      {kind && (
        <Card>
          <CardContent className="space-y-3 pt-4">
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" onClick={() => downloadTemplate(kind)}>
                <Download className="size-4" aria-hidden />
                {t("Download template")}
              </Button>
              {kind === "bookings" && (
                <select
                  className={cn(inputCls, "w-auto py-2 text-sm")}
                  value={preset}
                  onChange={(e) => {
                    setPreset(e.target.value)
                    setPreviews((p) => ({ ...p, bookings: undefined }))
                  }}
                  aria-label={t("Which system is this export from?")}
                >
                  <option value="auto">{t("Auto-detect format")}</option>
                  <option value="ezee">{t("eZee export")}</option>
                  <option value="cloudbeds">{t("Cloudbeds export")}</option>
                </select>
              )}
              <label className="cursor-pointer rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 hover:border-brand-400">
                {t("Upload CSV file")}
                <input
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={async (e) => {
                    const f = e.target.files?.[0]
                    if (f) setFile(kind, await f.text())
                    e.target.value = ""
                  }}
                />
              </label>
              <span className="text-xs text-zinc-400">{t("or paste it below")}</span>
            </div>
            {kind === "opening" && (
              <p className="text-sm text-zinc-600">
                {t(
                  "One row per balance. Type is In-house (what the guest owes; negative if in credit, 0 if settled), City ledger (an unpaid company invoice; negative for money paid ahead) or Deposit (an advance a future booking has paid). Use the closing figures from the old system's last night audit.",
                )}
              </p>
            )}
            <textarea
              className={cn(inputCls, "font-mono text-xs")}
              rows={7}
              placeholder={PLACEHOLDER[kind]}
              value={files[kind]}
              onChange={(e) => setFile(kind, e.target.value)}
            />

            {preview && <PreviewPanel kind={kind} preview={preview} />}

            {reports[kind] && (
              <div className="rounded-lg bg-zinc-50 px-4 py-3 text-sm">
                <p className="font-medium text-emerald-700">{reports[kind]}</p>
                <IssueList issues={reportErrors[kind] ?? []} />
              </div>
            )}

            <div className="flex justify-end gap-2">
              {!preview ? (
                <Button disabled={busy || !property || !files[kind].trim()} onClick={() => runStep(kind, "preview")}>
                  {busy ? t("Checking…") : t("Preview")}
                </Button>
              ) : (
                <>
                  <Button variant="outline" disabled={busy} onClick={() => runStep(kind, "preview")}>
                    {t("Check again")}
                  </Button>
                  <Button disabled={busy || preview.ok === 0} onClick={() => runStep(kind, "run")}>
                    {busy ? t("Importing…") : t("Import {n} row(s)", { n: preview.ok })}
                  </Button>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "reconcile" && (
        <Card>
          <CardContent className="space-y-4 pt-4">
            <p className="text-sm text-zinc-600">
              {t(
                "Compares the files loaded in steps 1-3 with what is now in Kamra: counts and totals per category. Go live only when every line matches.",
              )}
            </p>
            <div className="flex flex-wrap gap-2 text-xs">
              {(["bookings", "companies", "opening"] as FileKind[]).map((k) => (
                <Badge key={k} tone={files[k].trim() ? "green" : "zinc"}>
                  {t(k === "opening" ? "Opening balances" : k === "bookings" ? "Bookings" : "Companies")}
                  {files[k].trim() ? "" : ` · ${t("no file")}`}
                </Badge>
              ))}
            </div>
            <div className="flex justify-end">
              <Button
                disabled={busy || !property || !(files.bookings.trim() || files.companies.trim() || files.opening.trim())}
                onClick={reconcile}
              >
                {busy ? t("Checking…") : t("Reconcile")}
              </Button>
            </div>
            {recon && <ReconView recon={recon} />}
          </CardContent>
        </Card>
      )}

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      )}
    </div>
  )
}

function IssueList({ issues }: { issues: Issue[] }) {
  if (!issues.length) return null
  return (
    <ul className="mt-1 space-y-0.5">
      {issues.map((iss, i) => {
        const who = iss.guest || iss.name || iss.who
        return (
          <li key={`${iss.row}-${i}`} className="text-rose-600">
            Row {iss.row}
            {who ? ` (${who})` : ""}: {iss.error}
          </li>
        )
      })}
    </ul>
  )
}

function PreviewPanel({ kind, preview }: { kind: FileKind; preview: Preview }) {
  const { t } = useT()
  return (
    <div className="space-y-2 rounded-lg bg-zinc-50 px-4 py-3 text-sm">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-medium text-emerald-700">{t("{n} ready to import", { n: preview.ok })}</span>
        {preview.skipped > 0 && (
          <span className="font-medium text-rose-600">{t("{n} will be skipped", { n: preview.skipped })}</span>
        )}
        {kind === "bookings" && (preview as BookingsPreview).already_imported > 0 && (
          <span className="text-zinc-500">
            {t("{n} already in Kamra (left alone)", { n: (preview as BookingsPreview).already_imported })}
          </span>
        )}
        {kind === "companies" && (
          <span className="text-zinc-500">
            {t("{n} new, {e} existing (updated), {c} on credit", {
              n: (preview as CompaniesPreview).new,
              e: (preview as CompaniesPreview).existing,
              c: (preview as CompaniesPreview).on_credit,
            })}
          </span>
        )}
        {"date_format" in preview && (
          <span className="text-zinc-400">{t("dates read as {format}", { format: preview.date_format })}</span>
        )}
        {kind === "opening" && (
          <span className="text-zinc-400">
            {t("posts on business date {date}", { date: (preview as OpeningPreview).business_date })}
          </span>
        )}
      </p>
      <div className="flex flex-wrap gap-1">
        {Object.entries(preview.mapping).map(([k, v]) => (
          <Badge key={k} tone="zinc">
            {v} → {k.replace(/_/g, " ")}
          </Badge>
        ))}
        {preview.unmapped.map((h) => (
          <Badge key={h} tone="amber">
            {t("{header} (ignored)", { header: h })}
          </Badge>
        ))}
      </div>
      {kind === "opening" && (
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-zinc-500">
            <tr>
              <th className="py-1 font-medium">{t("Category")}</th>
              <th className="py-1 text-right font-medium">{t("Rows")}</th>
              <th className="py-1 text-right font-medium">{t("Total")}</th>
              <th className="py-1 text-right font-medium">{t("Already posted")}</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {(preview as OpeningPreview).categories.map((c) => (
              <tr key={c.category} className="border-t border-zinc-200">
                <td className="py-1">{t(c.label)}</td>
                <td className="py-1 text-right">{c.count}</td>
                <td className="py-1 text-right">{fmtMoney(c.total)}</td>
                <td className="py-1 text-right">{c.already_posted}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <IssueList issues={preview.issues} />
    </div>
  )
}

function ReconView({ recon }: { recon: Reconciliation }) {
  const { t } = useT()
  return (
    <div className="space-y-3">
      <div
        className={cn(
          "flex items-start gap-3 rounded-lg border px-4 py-3 text-sm",
          recon.ready
            ? "border-emerald-200 bg-emerald-50 text-emerald-800"
            : "border-amber-200 bg-amber-50 text-amber-900",
        )}
      >
        {recon.ready ? (
          <CheckCircle2 className="mt-0.5 size-5 shrink-0" aria-hidden />
        ) : (
          <ShieldAlert className="mt-0.5 size-5 shrink-0" aria-hidden />
        )}
        <div>
          <p className="font-semibold">
            {recon.ready ? t("Ready for go-live") : t("Not ready for go-live yet")}
          </p>
          <p>
            {recon.ready
              ? t("Every file ties to Kamra as of business date {date}. Switch the desk over.", {
                  date: recon.business_date,
                })
              : t("Fix what is listed below, import again (already-posted rows are skipped), then reconcile again.")}
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-left text-sm">
          <thead className="text-xs uppercase text-zinc-500">
            <tr>
              <th className="py-1.5 font-medium">{t("Category")}</th>
              <th className="py-1.5 text-right font-medium">{t("File rows")}</th>
              <th className="py-1.5 text-right font-medium">{t("File total")}</th>
              <th className="py-1.5 text-right font-medium">{t("In Kamra")}</th>
              <th className="py-1.5 text-right font-medium">{t("Kamra total")}</th>
              <th className="py-1.5 text-right font-medium">{t("Status")}</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {recon.categories.map((c) => (
              <tr key={c.category} className="border-t border-zinc-200 align-top">
                <td className="py-1.5">{t(c.label)}</td>
                <td className="py-1.5 text-right">{c.file_count}</td>
                <td className="py-1.5 text-right">{c.category === "companies" ? "—" : money(c.file_total)}</td>
                <td className="py-1.5 text-right">{c.kamra_count}</td>
                <td className="py-1.5 text-right">{money(c.kamra_total)}</td>
                <td className="py-1.5 text-right">
                  <Badge tone={c.matched ? "green" : "rose"}>{c.matched ? t("Matches") : t("Differs")}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {recon.categories
        .filter((c) => c.by_company && c.by_company.length > 0)
        .map((c) => (
          <div key={`${c.category}-co`} className="overflow-x-auto">
            <p className="mb-1 text-xs font-semibold uppercase text-zinc-500">{t("City ledger by company")}</p>
            <table className="w-full min-w-[30rem] text-left text-sm">
              <thead className="text-xs text-zinc-500">
                <tr>
                  <th className="py-1 font-medium">{t("Company")}</th>
                  <th className="py-1 text-right font-medium">{t("File")}</th>
                  <th className="py-1 text-right font-medium">{t("Carried over")}</th>
                  <th className="py-1 text-right font-medium">{t("Account balance")}</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {c.by_company!.map((b) => (
                  <tr key={b.company} className="border-t border-zinc-200">
                    <td className={cn("py-1", !b.matched && "text-rose-600")}>{b.company}</td>
                    <td className="py-1 text-right">{fmtMoney(b.file)}</td>
                    <td className="py-1 text-right">{fmtMoney(b.kamra)}</td>
                    <td className="py-1 text-right">{fmtMoney(b.balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

      {recon.blockers.length > 0 && (
        <div className="rounded-lg bg-zinc-50 px-4 py-3 text-sm">
          <p className="mb-1 font-medium text-zinc-800">{t("To fix before go-live")}</p>
          <ul className="list-disc space-y-0.5 pl-5 text-rose-700">
            {recon.blockers.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
          {recon.categories
            .filter((c) => c.problems.length > 0)
            .map((c) => (
              <div key={`${c.category}-p`} className="mt-2">
                <p className="text-xs font-semibold uppercase text-zinc-500">{t(c.label)}</p>
                <ul className="list-disc pl-5 text-zinc-700">
                  {c.problems.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </div>
            ))}
        </div>
      )}
    </div>
  )
}
