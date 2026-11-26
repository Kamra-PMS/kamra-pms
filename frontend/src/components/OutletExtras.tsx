import { useCallback, useEffect, useRef, useState } from "react"
import { Check } from "lucide-react"

import { listResource, serverError, updateResource, type Row } from "../lib/resource"
import { billHtml, fitLogos, logoSrc, thermalDocument, ticketAssetsReady, type BillData } from "../lib/thermal"
import { t, useUILanguage } from "../lib/i18n"
import { cn } from "../lib/utils"
import ImageField from "./ImageField"
import OutletWaiters from "./OutletWaiters"
import { Switch } from "./ui/switch"

type Design = "Stacked" | "Columns"

interface Bits {
  logo: string
  design: Design
  barcode: boolean
  outlet: string
  hotel: string
}

/** Fixed example food and plain numbers, the same for every hotel: the preview is only
 *  there to show the two layouts. Real bills use the property's own currency. */
const SAMPLE_ITEMS = [
  { item_name: "Cheeseburger", qty: 2, rate: 12.5, amount: 25 },
  { item_name: "Buffalo Wings", qty: 1, rate: 14, amount: 14 },
  { item_name: "Apple Pie", qty: 3, rate: 7, amount: 21 },
]
const sampleFmt = (n: number) =>
  n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function sampleBill(design: Design, bits: Bits): BillData {
  return {
    order: "ORD-2026-00042", kot_no: 17, property_name: bits.hotel, outlet_name: bits.outlet,
    order_type: "Dine In", table_no: "T3", room_no: null, customer_name: null, customer_phone: null,
    delivery_address: null, captain: null, served_by: "Rina", cashier: null,
    logo: bits.logo || null, receipt_design: design, barcode: bits.barcode,
    items: SAMPLE_ITEMS, subtotal: 60, discount_amount: 0,
    levy: { label: "", percent: 10, amount: 6 }, taxable: 66,
    gst_rate: 8, cgst: 2.64, sgst: 2.64, tax_parts: [{ label: t("Tax"), rate: 8, amount: 5.28 }],
    grand_total: 71.28, paid: 1, payment_mode: "Cash", nc: 0, nc_authorized_by: null, nc_note: null,
  }
}

const SCALE = 0.68

/** The real bill renderer, scaled down. */
function BillPreview({ design, bits }: { design: Design; bits: Bits }) {
  const ref = useRef<HTMLIFrameElement>(null)
  const [height, setHeight] = useState(520)
  const doc = thermalDocument("Bill", billHtml(sampleBill(design, bits), { fmt: sampleFmt, symbol: "", digits: 2 }))

  useEffect(() => {
    const frame = ref.current
    if (!frame) return
    const onLoad = async () => {
      const d = frame.contentDocument
      if (!d) return
      await ticketAssetsReady(d)
      fitLogos(d)
      setHeight(d.documentElement.scrollHeight)
    }
    frame.addEventListener("load", onLoad)
    return () => frame.removeEventListener("load", onLoad)
  }, [doc])

  return (
    <div className="mx-auto mt-3 overflow-hidden border border-zinc-300 bg-white shadow-sm"
      style={{ width: 302 * SCALE, height: height * SCALE }}>
      <iframe ref={ref} title={t("Receipt design")} srcDoc={doc} sandbox="allow-same-origin" tabIndex={-1}
        style={{ width: "80mm", height, border: 0, background: "#fff", transform: `scale(${SCALE})`, transformOrigin: "0 0" }} />
    </div>
  )
}

function DesignCard({ design, bits, selected, onPick }: {
  design: Design; bits: Bits; selected: boolean; onPick: () => void
}) {
  const a = design === "Columns"   // Design A is the original columns layout, Design B the stacked one
  return (
    <div role="radio" aria-checked={selected} tabIndex={0} onClick={onPick}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick() } }}
      className={cn(
        "flex cursor-pointer flex-col rounded-2xl border-2 p-4 outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand-600",
        selected ? "border-brand-600 bg-brand-50/60" : "border-zinc-200 bg-white hover:border-zinc-300",
      )}>
      <div className="flex items-center gap-2">
        <span className={cn("size-5 shrink-0 rounded-full border-2", selected ? "border-brand-600 bg-brand-600 ring-2 ring-inset ring-white" : "border-zinc-400")} />
        <span className="text-base font-semibold text-zinc-900">{a ? t("Design A") : t("Design B")}</span>
        <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">{a ? t("Columns") : t("Stacked")}</span>
        {selected && <Check className="ml-auto size-5 rounded-full bg-brand-600 p-1 text-white" aria-hidden />}
      </div>
      <p className="mt-2 min-h-10 text-sm leading-relaxed text-zinc-600">
        {a ? t("Item, Qty, Rate and Amount in columns. Easy to scan when prices are short.")
          : t("Name on its own line, then quantity x rate and the amount. Stays tidy when prices have many digits.")}
      </p>
      <BillPreview design={design} bits={bits} />
    </div>
  )
}

/** Receipt logo, Receipt design, then Waiters: the outlet's extra sections, under its form. */
export default function OutletExtras({ row, reload }: { row: Row; reload: () => void }) {
  useUILanguage()
  const outlet = String(row.name)
  const [bits, setBits] = useState<Bits | null>(null)
  const [error, setError] = useState<string | null>(null)
  /** A refused logo is explained next to the logo field, not at the bottom of the dialog. */
  const [logoError, setLogoError] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    let live = true
    void (async () => {
      try {
        const [o] = await listResource("POS Outlet", {
          fields: ["name", "outlet_name", "property", "logo", "receipt_design", "print_barcode"], filters: [["name", "=", outlet]], limit: 1,
        })
        const [p] = o ? await listResource("Property", {
          fields: ["name", "property_name"], filters: [["name", "=", String(o.property)]], limit: 1,
        }) : []
        if (live && o) setBits({
          logo: String(o.logo ?? ""), design: o.receipt_design === "Stacked" ? "Stacked" : "Columns",
          barcode: o.print_barcode == null ? true : Boolean(Number(o.print_barcode)),
          outlet: String(o.outlet_name ?? ""), hotel: String(p?.property_name ?? ""),
        })
      } catch (e) {
        if (live) setError(serverError(e))
      }
    })()
    return () => { live = false; clearTimeout(timer.current) }
  }, [outlet])

  const save = useCallback(async (data: Record<string, unknown>, report: (message: string | null) => void = setError) => {
    try {
      report(null)
      await updateResource("POS Outlet", outlet, data)
      reload()
    } catch (e) {
      report(serverError(e))
    }
  }, [outlet, reload])

  const setLogo = (logo: string, now: boolean) => {
    setBits((b) => (b ? { ...b, logo } : b))
    setLogoError(null)
    clearTimeout(timer.current)
    // Typing or pasting waits for a pause before it is checked, so a half-typed link is not
    // refused. A link the bill would not print is not sent: the same rule the server applies.
    const commit = () => {
      if (logo.trim() && !logoSrc(logo)) {
        setLogoError(t("Use the Upload button, or paste a link that starts with https://. Plain http links are not accepted."))
        return
      }
      void save({ logo }, setLogoError)
    }
    if (now) commit()
    else timer.current = setTimeout(commit, 600)
  }
  const toggleBarcode = () => {
    const next = !(bits?.barcode ?? true)
    setBits((b) => (b ? { ...b, barcode: next } : b))
    void save({ print_barcode: next ? 1 : 0 })
  }
  const pick = (design: Design) => {
    setBits((b) => (b ? { ...b, design } : b))
    void save({ receipt_design: design })
  }

  return (
    <div className="space-y-5">
      {bits && (
        <>
          <div className="grid gap-x-8 gap-y-2 border-t border-zinc-200 pt-4 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <div className="min-w-0">
              <div className="text-sm font-medium text-zinc-800">{t("Receipt logo")}</div>
              <p className="mt-0.5 text-xs leading-relaxed text-zinc-500">
                {t("Printed at the top of this outlet's bills, at a fixed small size to save paper. Upload a PNG or paste an https link; black on white, 512px or wider looks best. No logo: the outlet and hotel name print instead.")}
              </p>
            </div>
            <div className="min-w-0">
              <ImageField hint="" value={bits.logo} onChange={(v) => setLogo(v, false)} onUploaded={(v) => setLogo(v, true)}
                accept="image/png,image/jpeg,image/webp" placeholder={t("Upload a PNG, or paste an https link")}
                attach={{ doctype: "POS Outlet", docname: outlet, fieldname: "logo" }} />
              {logoError && <p role="alert" className="mt-1 text-xs text-rose-600">{t(logoError)}</p>}
            </div>
          </div>

          <div className="space-y-1 border-t border-zinc-200 pt-4">
            <div className="text-sm font-medium text-zinc-800">{t("Receipt design")}</div>
            <p className="max-w-2xl text-xs leading-relaxed text-zinc-500">
              {t("How the items print on this outlet's bills. Everything else on the receipt is the same in both. Pick one. The samples use example food and plain numbers; your real bills use your own currency.")}
            </p>
            {/* above the samples, so flipping it shows the change without scrolling */}
            <div className="flex items-start justify-between gap-4 py-2">
              <div className="min-w-0">
                <label htmlFor="outlet-print-barcode" className="text-sm font-medium text-zinc-800">{t("Print a barcode on the bill")}</label>
                <p className="mt-0.5 max-w-2xl text-xs leading-relaxed text-zinc-500">
                  {t("A barcode of the order number prints at the bottom of this outlet's bills, so a bill can be found by scanning it. The samples below follow this switch.")}
                </p>
              </div>
              <Switch id="outlet-print-barcode" on={bits.barcode} onToggle={toggleBarcode} />
            </div>
            <div role="radiogroup" aria-label={t("Receipt design")} className="grid gap-4 pt-1 sm:grid-cols-2">
              <DesignCard design="Columns" bits={bits} selected={bits.design === "Columns"} onPick={() => pick("Columns")} />
              <DesignCard design="Stacked" bits={bits} selected={bits.design === "Stacked"} onPick={() => pick("Stacked")} />
            </div>
          </div>
        </>
      )}
      {error && <p className="text-xs text-rose-600">{t(error)}</p>}
      <OutletWaiters row={row} reload={reload} />
    </div>
  )
}
