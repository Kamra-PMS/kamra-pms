/*  The paper a function produces.

    One renderer for all five documents, because they're the same facts cut
    differently: the quotation is the price, the contract is the price plus
    what both sides signed up to, the event order is the day itself, the
    pack list is what has to be carried, the invoice is what's owed.

    Everything outside the sheet is print:hidden, so Ctrl-P gives the
    customer's copy and nothing else. */

import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, Printer } from "lucide-react"

import {
  banquet,
  type BanquetDocument as Doc,
  type DocumentKind,
  type MenuCard,
} from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { taxLabel } from "../lib/money"
import { Empty, ErrorNote, inrExact } from "./banquet/shared"

const KINDS: DocumentKind[] = ["quote", "contract", "beo", "pack_list", "invoice"]
/** The menu card isn't one of the priced documents - it's the sheet the
 *  customer signs off and the kitchen cooks from, with no money on it. */
const EXTRA_KINDS = ["menu_card"] as const
const KIND_LABEL: Record<DocumentKind, string> = {
  quote: "Quotation",
  contract: "Contract",
  beo: "Event order",
  pack_list: "Pack list",
  invoice: "Invoice",
}
const MENU_CARD = "menu_card"

export default function BanquetDocument() {
  const { name = "", kind = "quote" } = useParams()
  const [doc, setDoc] = useState<Doc | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [card, setCard] = useState<MenuCard | null>(null)
  const isCard = kind === MENU_CARD

  useEffect(() => {
    setDoc(null)
    setCard(null)
    setError(null)
    const load = isCard
      ? banquet.menuCard(name).then(setCard)
      : banquet.document(name, kind as DocumentKind).then(setDoc)
    load.catch((e) => setError(serverError(e)))
  }, [name, kind, isCard])

  if (error) return <ErrorNote error={error} />
  if (isCard)
    return card ? (
      <MenuCardSheet name={name} card={card} />
    ) : (
      <Empty>Loading…</Empty>
    )
  if (!doc) return <Empty>Loading…</Empty>

  const showsMoney = kind !== "pack_list" && kind !== "beo"

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 print:hidden">
        <Link
          to={`/banquet/${encodeURIComponent(name)}`}
          className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800"
        >
          <ArrowLeft className="size-4" />
          Back to the function
        </Link>
        <div className="flex flex-wrap items-center gap-1.5">
          {KINDS.map((k) => (
            <Link
              key={k}
              to={`/banquet/${encodeURIComponent(name)}/${k}`}
              className={
                "rounded-lg px-2.5 py-1.5 text-sm font-medium " +
                (k === kind
                  ? "bg-zinc-900 text-white"
                  : "text-zinc-500 hover:bg-zinc-100")
              }
            >
              {KIND_LABEL[k]}
            </Link>
          ))}
          {EXTRA_KINDS.map((k) => (
            <Link
              key={k}
              to={`/banquet/${encodeURIComponent(name)}/${k}`}
              className={
                "rounded-lg px-2.5 py-1.5 text-sm font-medium " +
                (k === kind
                  ? "bg-zinc-900 text-white"
                  : "text-zinc-500 hover:bg-zinc-100")
              }
            >
              Menu card
            </Link>
          ))}
          <Button onClick={() => window.print()}>
            <Printer className="size-4" />
            Print
          </Button>
        </div>
      </div>

      <article className="rounded-xl border border-zinc-200 bg-white p-8 text-sm print:border-0 print:p-0">
        <Letterhead doc={doc} />

        <Parties doc={doc} />

        {kind === "beo" && <RunSheet doc={doc} />}
        {kind === "pack_list" ? (
          <PackList doc={doc} />
        ) : (
          <Lines doc={doc} showsMoney={showsMoney} />
        )}

        {(kind === "beo" || kind === "pack_list") && doc.menus && (
          <Menus doc={doc} />
        )}

        {showsMoney && <TaxBreakup doc={doc} />}
        {showsMoney && <Totals doc={doc} />}

        {kind === "invoice" && doc.receipts && doc.receipts.length > 0 && (
          <Section title="Received">
            <table className="w-full">
              <tbody>
                {doc.receipts.map((r, i) => (
                  <tr key={i} className="border-b border-zinc-100">
                    <td className="py-1.5 text-zinc-500">{r.date}</td>
                    <td className="py-1.5">{r.kind}</td>
                    <td className="py-1.5 text-zinc-500">{r.mode}</td>
                    <td className="py-1.5 text-zinc-400">{r.reference}</td>
                    <td className="py-1.5 text-right tabular-nums">
                      {inrExact(r.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
        )}

        {doc.terms.length > 0 && kind !== "pack_list" && (
          <Section title="Payment schedule">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-400">
                  <th className="py-1.5 font-medium">Milestone</th>
                  <th className="py-1.5 font-medium">Due</th>
                  <th className="py-1.5 text-right font-medium">Amount</th>
                  <th className="py-1.5 text-right font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {doc.terms.map((t, i) => (
                  <tr key={i} className="border-b border-zinc-100">
                    <td className="py-1.5">{t.milestone}</td>
                    <td className="py-1.5 text-zinc-500">{t.due_date ?? "-"}</td>
                    <td className="py-1.5 text-right tabular-nums">
                      {inrExact(t.amount)}
                      {t.percent ? (
                        <span className="text-zinc-400"> ({t.percent}%)</span>
                      ) : null}
                    </td>
                    <td
                      className={
                        "py-1.5 text-right " +
                        (t.status === "Received"
                          ? "text-emerald-700"
                          : t.status === "Overdue"
                            ? "text-rose-700"
                            : "text-zinc-500")
                      }
                    >
                      {t.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
        )}

        {doc.open_items.filter((o) => o.status === "Open").length > 0 &&
          kind !== "pack_list" && (
            <Section title="Still to be agreed">
              <ul className="space-y-1">
                {doc.open_items
                  .filter((o) => o.status === "Open")
                  .map((o, i) => (
                    <li key={i} className="flex justify-between gap-4">
                      <span>
                        {o.title}
                        {o.detail && (
                          <span className="text-zinc-400"> - {o.detail}</span>
                        )}
                        <span className="text-zinc-400"> ({o.owner_side})</span>
                      </span>
                      {o.price_impact ? (
                        <span className="shrink-0 tabular-nums text-zinc-500">
                          {o.price_impact > 0 ? "+" : ""}
                          {inrExact(o.price_impact)}
                        </span>
                      ) : null}
                    </li>
                  ))}
              </ul>
            </Section>
          )}

        {doc.terms_note && kind !== "pack_list" && (
          <Section title="Terms & conditions">
            <p className="whitespace-pre-wrap text-zinc-600">{doc.terms_note}</p>
          </Section>
        )}

        {doc.notes && (
          <Section title="Instructions">
            <p className="whitespace-pre-wrap text-zinc-600">{doc.notes}</p>
          </Section>
        )}

        {doc.requirements && kind === "quote" && (
          <Section title="What you asked for">
            <p className="whitespace-pre-wrap text-zinc-600">
              {doc.requirements}
            </p>
          </Section>
        )}

        {doc.signatures && (
          <div className="mt-12 grid grid-cols-2 gap-12">
            {doc.signatures.map((s, i) => (
              <div key={i}>
                <div className="h-16 border-b border-zinc-400" />
                <p className="mt-1 text-xs font-medium">{s.for}</p>
                <p className="text-xs text-zinc-400">{s.role}</p>
              </div>
            ))}
          </div>
        )}
        {doc.signed_on && (
          <p className="mt-4 text-xs text-zinc-400">
            Signed on {doc.signed_on}.
          </p>
        )}

        {/* every priced document closes the same way: who it's from, and
            the note that says it needs no wet signature */}
        {showsMoney && !doc.signatures && (
          <footer className="mt-10 flex items-end justify-between gap-6 border-t border-zinc-200 pt-4">
            <p className="max-w-sm text-[11px] leading-relaxed text-zinc-400">
              {doc.header.footer}
            </p>
            <div className="shrink-0 text-center">
              <div className="mb-1 h-10 w-44 border-b border-zinc-300" />
              <p className="text-xs">
                For {doc.property.legal_name || doc.property.property_name}
              </p>
              <p className="text-[11px] text-zinc-400">Authorised signatory</p>
            </div>
          </footer>
        )}
      </article>
    </div>
  )
}

/* ── pieces ───────────────────────────────────────────────────────────── */

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="mt-6 break-inside-avoid">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">
        {title}
      </h3>
      {children}
    </section>
  )
}

function Letterhead({ doc }: { doc: Doc }) {
  const p = doc.property
  const h = doc.header
  return (
    <header className="border-b-2 border-zinc-900 pb-4">
      <div className="flex items-start justify-between gap-6">
        <div className="flex items-start gap-3">
          {/* the hotel's own mark - a document without it doesn't look
              like it came from the hotel */}
          {p.logo_url && (
            <img
              src={p.logo_url}
              alt=""
              className="h-14 w-14 shrink-0 rounded object-contain"
              onError={(e) => {
                ;(e.target as HTMLImageElement).style.display = "none"
              }}
            />
          )}
          <div>
            <h1 className="text-lg font-semibold leading-tight">
              {p.legal_name || p.property_name}
            </h1>
            {p.legal_name && p.legal_name !== p.property_name && (
              <p className="text-sm text-zinc-500">{p.property_name}</p>
            )}
            <p className="mt-1 text-xs leading-relaxed text-zinc-500">
              {p.address}
              {(p.phone || p.email) && (
                <>
                  <br />
                  {[p.phone, p.email].filter(Boolean).join(" · ")}
                </>
              )}
              {p.website && (
                <>
                  <br />
                  {p.website}
                </>
              )}
              {p.gstin && (
                <>
                  <br />
                  <span className="font-medium text-zinc-700">
                    {h.tax_id_label ?? "GSTIN"}: {p.gstin}
                  </span>
                </>
              )}
            </p>
          </div>
        </div>

        <div className="shrink-0 text-right">
          <h2 className="text-base font-semibold uppercase tracking-[0.15em]">
            {h.title}
          </h2>
          <table className="ml-auto mt-2 text-xs">
            <tbody>
              <Meta label="No." value={h.number} mono />
              {h.issued_on && <Meta label="Dated" value={h.issued_on} />}
              {!h.issued_on && (
                <Meta label="Printed" value={h.printed_on.slice(0, 10)} />
              )}
              {h.version > 0 && h.kind !== "beo" && (
                <Meta label="Revision" value={String(h.version)} />
              )}
              {h.valid_till && h.kind === "quote" && (
                <Meta label="Valid till" value={h.valid_till} />
              )}
              {h.place_of_supply && h.kind === "invoice" && (
                <Meta label="Place of supply" value={h.place_of_supply} />
              )}
              <Meta label="Function" value={h.function ?? h.reference} mono />
            </tbody>
          </table>
          {!h.is_final && h.kind !== "pack_list" && h.kind !== "beo" && (
            <p className="mt-1.5 max-w-48 text-[11px] text-amber-700">
              Draft — no number issued yet.
            </p>
          )}
        </div>
      </div>
    </header>
  )
}

function Meta({
  label,
  value,
  mono,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <tr>
      <td className="pr-3 text-right align-top text-zinc-400">{label}</td>
      <td className={"text-left font-medium" + (mono ? " font-mono" : "")}>
        {value}
      </td>
    </tr>
  )
}

function Parties({ doc }: { doc: Doc }) {
  const c = doc.customer
  const e = doc.event
  return (
    <div className="mt-4 grid gap-6 sm:grid-cols-2">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          For
        </h3>
        <p className="mt-1 font-medium">{c.name}</p>
        {c.company && <p className="text-zinc-600">{c.company}</p>}
        {c.address && (
          <p className="whitespace-pre-wrap text-xs text-zinc-500">
            {c.address}
          </p>
        )}
        <p className="mt-1 text-xs text-zinc-500">
          {[c.contact, c.phone, c.email].filter(Boolean).join(" · ")}
        </p>
        {c.gstin && (
          <p className="text-xs text-zinc-500">
            {taxLabel()}: {c.gstin}
            {c.place_of_supply ? ` · Place of supply: ${c.place_of_supply}` : ""}
          </p>
        )}
      </div>
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          The function
        </h3>
        <p className="mt-1 font-medium">
          {String(e.event_name || e.event_type)}
        </p>
        <dl className="mt-1 space-y-0.5 text-xs text-zinc-600">
          <Line k="Venue" v={`${e.venue}${e.venue_type ? ` (${e.venue_type})` : ""}`} />
          <Line
            k="Date"
            v={
              String(e.event_date) +
              (e.end_date && e.end_date !== e.event_date
                ? ` → ${e.end_date}`
                : "")
            }
          />
          {e.start_time ? (
            <Line
              k="Time"
              v={`${e.start_time} – ${e.end_time}${
                e.hours ? ` (${e.hours} hrs)` : ""
              }`}
            />
          ) : null}
          <Line
            k="Pax"
            v={
              `${e.billable_pax} billable` +
              (e.pax_guaranteed ? ` · ${e.pax_guaranteed} guaranteed` : "") +
              (e.pax_actual ? ` · ${e.pax_actual} actual` : "")
            }
          />
          {e.setup_style ? <Line k="Setup" v={String(e.setup_style)} /> : null}
          {e.green_room ? (
            <Line
              k="Green room"
              v={
                String(e.green_room) +
                (e.green_room_complimentary ? " (complimentary)" : "")
              }
            />
          ) : null}
        </dl>
      </div>
    </div>
  )
}

function Line({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2">
      <dt className="w-20 shrink-0 text-zinc-400">{k}</dt>
      <dd>{v}</dd>
    </div>
  )
}

function RunSheet({ doc }: { doc: Doc }) {
  const e = doc.event
  const moments = [
    ["Setup access from", e.setup_from],
    ["Doors / guests in", `${e.event_date} ${e.start_time ?? ""}`],
    ["Function ends", `${e.end_date ?? e.event_date} ${e.end_time ?? ""}`],
    ["Cleared by", e.teardown_by],
  ].filter(([, v]) => v) as [string, string][]
  return (
    <Section title="Running order">
      <div className="grid gap-2 sm:grid-cols-4">
        {moments.map(([k, v]) => (
          <div key={k} className="rounded-lg border border-zinc-200 px-3 py-2">
            <p className="text-[11px] uppercase tracking-wider text-zinc-400">
              {k}
            </p>
            <p className="mt-0.5 font-medium tabular-nums">
              {String(v).replace("T", " ").slice(0, 16)}
            </p>
          </div>
        ))}
      </div>
      {e.setup_notes ? (
        <p className="mt-2 whitespace-pre-wrap text-zinc-600">
          {String(e.setup_notes)}
        </p>
      ) : null}
    </Section>
  )
}

function Lines({ doc, showsMoney }: { doc: Doc; showsMoney: boolean }) {
  const all = [...doc.lines, ...doc.complimentary]
  if (all.length === 0) return null
  return (
    <Section title={showsMoney ? "Charges" : "What's included"}>
      <table className="w-full">
        <thead>
          <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-400">
            <th className="py-1.5 font-medium">Item</th>
            {showsMoney && (
              <th className="py-1.5 font-medium">
                {doc.header.service_code_label}
              </th>
            )}
            <th className="py-1.5 text-right font-medium">Qty</th>
            {showsMoney && (
              <>
                <th className="py-1.5 text-right font-medium">Rate</th>
                <th className="py-1.5 text-right font-medium">{taxLabel()}</th>
                <th className="py-1.5 text-right font-medium">Amount</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {all.map((l) => (
            <tr key={l.name} className="border-b border-zinc-100">
              <td className="py-1.5">
                <span className={l.chargeable ? "" : "text-zinc-500"}>
                  {l.item_name}
                </span>
                {!l.chargeable && (
                  <span className="ml-1.5 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                    complimentary
                  </span>
                )}
                {l.description && (
                  <p className="text-xs text-zinc-400">{l.description}</p>
                )}
                {l.notes && l.notes !== "green-room" && (
                  <p className="text-xs text-zinc-400">{l.notes}</p>
                )}
              </td>
              {showsMoney && (
                <td className="py-1.5 font-mono text-[11px] text-zinc-400">
                  {l.service_code ?? ""}
                </td>
              )}
              <td className="py-1.5 text-right tabular-nums">
                {l.qty % 1 === 0 ? l.qty : l.qty.toFixed(2)}{" "}
                <span className="text-zinc-400">{l.uom}</span>
              </td>
              {showsMoney && (
                <>
                  <td className="py-1.5 text-right tabular-nums">
                    {l.chargeable ? inrExact(l.rate) : "-"}
                  </td>
                  <td className="py-1.5 text-right tabular-nums text-zinc-500">
                    {l.chargeable ? `${l.gst_rate}%` : "-"}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {l.chargeable ? inrExact(l.net_amount) : "-"}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  )
}

function Menus({ doc }: { doc: Doc }) {
  if (!doc.menus?.length) return null
  return (
    <Section title="Menus">
      <div className="space-y-4">
        {doc.menus.map((m, i) => (
          <div key={i} className="break-inside-avoid">
            <p className="font-medium">
              {m.menu_name}
              <span className="ml-2 text-xs font-normal text-zinc-400">
                {m.meal_period} · {m.food_type} · {m.service_style} · {m.pax} pax
                {m.menu_code ? ` · ${m.menu_code}` : ""}
                {m.chargeable ? "" : " · complimentary"}
              </span>
            </p>
            <ul className="mt-1 space-y-0.5">
              {m.courses.map((c, j) => (
                <li key={j} className="flex gap-2 text-xs">
                  <span className="w-36 shrink-0 font-medium text-zinc-500">
                    {c.course}
                    {c.is_live_counter && (
                      <span className="ml-1 text-amber-700">live</span>
                    )}
                    {c.choice_of ? (
                      <span className="ml-1 text-zinc-400">
                        (pick {c.choice_of})
                      </span>
                    ) : null}
                  </span>
                  <span className="text-zinc-600">{c.dishes}</span>
                </li>
              ))}
            </ul>
            {m.inclusions && (
              <p className="mt-1 text-xs text-zinc-400">
                Includes: {m.inclusions}
              </p>
            )}
            {m.exclusions && (
              <p className="text-xs text-zinc-400">Excludes: {m.exclusions}</p>
            )}
          </div>
        ))}
      </div>
    </Section>
  )
}

function PackList({ doc }: { doc: Doc }) {
  const p = doc.pack
  if (!p) return null
  return (
    <>
      <Section title="Delivery">
        <p className="text-zinc-600">
          To <span className="font-medium">{p.venue}</span> by{" "}
          <span className="font-medium tabular-nums">
            {p.deliver_by.replace("T", " ").slice(0, 16)}
          </span>
          {p.collect_after && (
            <>
              , collected after{" "}
              <span className="font-medium tabular-nums">
                {p.collect_after.replace("T", " ").slice(0, 16)}
              </span>
            </>
          )}
          . {p.total_items} item{p.total_items === 1 ? "" : "s"}.
        </p>
      </Section>
      {p.groups.map((g) => (
        <Section key={g.group} title={g.group}>
          <table className="w-full">
            <tbody>
              {g.items.map((it, i) => (
                <tr key={i} className="border-b border-zinc-100">
                  <td className="w-8 py-1.5">
                    <span className="inline-block size-4 rounded border border-zinc-300" />
                  </td>
                  <td className="py-1.5">
                    {it.item_name}
                    {!it.chargeable && (
                      <span className="ml-1.5 text-xs text-emerald-700">
                        (complimentary)
                      </span>
                    )}
                    {it.description && (
                      <p className="text-xs text-zinc-400">{it.description}</p>
                    )}
                    {it.notes && (
                      <p className="text-xs text-zinc-400">{it.notes}</p>
                    )}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {it.qty % 1 === 0 ? it.qty : it.qty.toFixed(2)}{" "}
                    <span className="text-zinc-400">{it.uom}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      ))}
    </>
  )
}

function TaxBreakup({ doc }: { doc: Doc }) {
  const rows = doc.tax_breakup ?? []
  if (!rows.length) return null
  const label = doc.header.tax_label ?? "GST"
  return (
    <Section title={`${label} breakup`}>
      <table className="w-full">
        <thead>
          <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-400">
            <th className="py-1.5 font-medium">Rate</th>
            <th className="py-1.5 text-right font-medium">Taxable</th>
            {rows[0].parts.map((p) => (
              <th key={p.label} className="py-1.5 text-right font-medium">
                {p.label}
              </th>
            ))}
            <th className="py-1.5 text-right font-medium">Total {label}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.rate} className="border-b border-zinc-100">
              <td className="py-1.5">{r.rate}%</td>
              <td className="py-1.5 text-right tabular-nums">
                {inrExact(r.taxable)}
              </td>
              {r.parts.map((p) => (
                <td key={p.label} className="py-1.5 text-right tabular-nums">
                  <span className="text-zinc-400">{p.rate}% </span>
                  {inrExact(p.amount)}
                </td>
              ))}
              <td className="py-1.5 text-right tabular-nums font-medium">
                {inrExact(r.total_tax)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  )
}

function Totals({ doc }: { doc: Doc }) {
  const t = doc.totals
  return (
    <section className="mt-6 flex justify-end break-inside-avoid">
      <div className="w-72 space-y-1">
        <Amt k="Subtotal" v={t.subtotal} />
        {t.discount > 0 && <Amt k="Discount" v={-t.discount} />}
        <Amt k="Taxable" v={t.taxable} />
        {t.tax_summary.map((s) => (
          <Amt
            key={s.gst_rate}
            k={`${taxLabel()} @ ${s.gst_rate}%`}
            v={s.tax}
            muted
          />
        ))}
        <div className="flex justify-between border-t border-zinc-300 pt-1 font-semibold">
          <span>Total</span>
          <span className="tabular-nums">{inrExact(t.grand_total)}</span>
        </div>
        {t.received > 0 && (
          <>
            <Amt k="Received" v={-t.received} />
            <div className="flex justify-between border-t border-zinc-200 pt-1 font-semibold">
              <span>Balance due</span>
              <span className="tabular-nums">{inrExact(t.balance_due)}</span>
            </div>
          </>
        )}
        {t.complimentary_value > 0 && (
          <p className="pt-2 text-xs text-zinc-400">
            Complimentary items worth {inrExact(t.complimentary_value)} are
            included at no charge.
          </p>
        )}
        {doc.header.amount_in_words && (
          <p className="border-t border-zinc-200 pt-2 text-xs italic text-zinc-600">
            {doc.header.amount_in_words}
          </p>
        )}
      </div>
    </section>
  )
}

function Amt({ k, v, muted }: { k: string; v: number; muted?: boolean }) {
  return (
    <div className={"flex justify-between " + (muted ? "text-zinc-500" : "")}>
      <span className="text-zinc-500">{k}</span>
      <span className="tabular-nums">{inrExact(v)}</span>
    </div>
  )
}

/* ── the menu card ────────────────────────────────────────────────────── */

/** What will actually be served, course by course, with no money on it —
 *  the sheet the customer signs and the kitchen cooks from. Keeping price
 *  off it is the point: the moment a plate rate appears, the conversation
 *  stops being about the food. */
function MenuCardSheet({ name, card }: { name: string; card: MenuCard }) {
  const e = card.event
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between gap-2 print:hidden">
        <Link
          to={`/banquet/${encodeURIComponent(name)}`}
          className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800"
        >
          <ArrowLeft className="size-4" />
          Back to the function
        </Link>
        <div className="flex items-center gap-1.5">
          {KINDS.map((k) => (
            <Link
              key={k}
              to={`/banquet/${encodeURIComponent(name)}/${k}`}
              className="rounded-lg px-2.5 py-1.5 text-sm font-medium text-zinc-500 hover:bg-zinc-100"
            >
              {KIND_LABEL[k]}
            </Link>
          ))}
          <span className="rounded-lg bg-zinc-900 px-2.5 py-1.5 text-sm font-medium text-white">
            Menu card
          </span>
          <Button onClick={() => window.print()}>
            <Printer className="size-4" />
            Print
          </Button>
        </div>
      </div>

      <article className="rounded-xl border border-zinc-200 bg-white px-10 py-8 print:border-0 print:px-0">
        <header className="border-b border-zinc-200 pb-4 text-center">
          <h1 className="text-lg font-semibold tracking-wide">
            {card.property.property_name ?? card.property.legal_name}
          </h1>
          <p className="mt-0.5 text-xs text-zinc-500">
            {[card.property.address_line, card.property.city]
              .filter(Boolean)
              .join(", ")}
            {card.property.phone ? ` · ${card.property.phone}` : ""}
          </p>
          <p className="mt-3 text-xs font-semibold uppercase tracking-[0.25em] text-zinc-400">
            {card.header.title}
          </p>
        </header>

        <dl className="mt-4 grid gap-x-8 gap-y-1 text-xs sm:grid-cols-2">
          {(
            [
              ["Function", String(e.event_name || e.event_type || "")],
              ["Customer", String(e.customer ?? "")],
              ["Date", String(e.event_date ?? "")],
              ["Hall / session", `${e.venue ?? ""} · ${e.session ?? ""}`],
              ["Covers", String(e.pax ?? "")],
              ["Setup", String(e.setup_style ?? "")],
            ] as [string, string][]
          )
            .filter(([, v]) => v.trim() && v.trim() !== "·")
            .map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <dt className="w-24 shrink-0 text-zinc-400">{k}</dt>
                <dd className="font-medium">{v}</dd>
              </div>
            ))}
        </dl>

        <div className="mt-8 space-y-8">
          {card.menus.length === 0 && (
            <p className="text-center text-sm text-zinc-400">
              No menu chosen yet.
            </p>
          )}
          {card.menus.map((m, i) => (
            <section key={i} className="break-inside-avoid text-center">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em]">
                {m.menu_name}
              </h2>
              <p className="mt-0.5 text-[11px] text-zinc-400">
                {[m.meal_period, m.food_type, m.service_style, m.cuisine]
                  .filter(Boolean)
                  .join(" · ")}
                {m.chargeable ? "" : " · complimentary"}
              </p>
              <div className="mt-4 space-y-3">
                {m.courses.map((c, j) => (
                  <div key={j}>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-zinc-500">
                      {c.course}
                      {c.choice_of ? ` — choose ${c.choice_of}` : ""}
                      {c.is_live_counter && (
                        <span className="ml-1 text-amber-600">live</span>
                      )}
                    </p>
                    <p className="mt-0.5 text-sm leading-relaxed">{c.dishes}</p>
                  </div>
                ))}
              </div>
              {m.inclusions && (
                <p className="mt-3 text-[11px] text-zinc-400">
                  Includes {m.inclusions}
                </p>
              )}
            </section>
          ))}

          {card.extras.length > 0 && (
            <section className="break-inside-avoid text-center">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em]">
                Also being served
              </h2>
              <ul className="mt-2 space-y-0.5 text-sm">
                {card.extras.map((x, i) => (
                  <li key={i}>
                    {x.item_name}
                    {x.chargeable ? "" : " (complimentary)"}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        {card.notes && (
          <p className="mt-8 whitespace-pre-wrap border-t border-zinc-200 pt-3 text-xs text-zinc-500">
            {card.notes}
          </p>
        )}

        <div className="mt-14 grid grid-cols-2 gap-16">
          {card.signatures.map((s, i) => (
            <div key={i} className="text-center">
              <div className="h-12 border-b border-zinc-400" />
              <p className="mt-1 text-xs font-medium">{s.for}</p>
              <p className="text-[11px] text-zinc-400">{s.role}</p>
            </div>
          ))}
        </div>
      </article>
    </div>
  )
}
