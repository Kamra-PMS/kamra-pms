import { t as translate, tn, uiDateLocale } from "./i18n"
/** 80mm thermal printing for KOT tickets, bills and the laundry docket.
 *
 * Renders the ticket in a hidden iframe with an `@page: 80mm` sheet and a
 * condensed monospace layout (Inconsolata, embedded, so it needs no network),
 * waits for the font and any logo to load, then prints. Works with any
 * OS-installed thermal driver; the text column is 68mm, narrower than the
 * common 72mm printable width, so nothing is clipped at the edge.
 */

import { cur, fmtAmount, moneyDigits, moneyLocale } from "./money"
import { addUp } from "./addUp"
import { code128Svg } from "./code128"
import inconsolataLatin from "../assets/fonts/inconsolata-latin.woff2?inline"
import inconsolataVietnamese from "../assets/fonts/inconsolata-vietnamese.woff2?inline"

/** The logo prints inside a box of at most 16 mm high and 60 mm wide, keeping its shape:
 *  a square logo is 16 x 16, a wide one keeps 16 mm until it reaches 60 mm, then shrinks. */
export const LOGO_MAX_H_MM = 16
export const LOGO_MAX_W_MM = 60

// Inconsolata (SIL OFL 1.1, see assets/fonts/OFL.txt): one variable font per script, weights 200-900.
const FONT_FACE = `
  @font-face { font-family: Inconsolata; font-style: normal; font-weight: 200 900; font-stretch: 100%;
    src: url(${inconsolataLatin}) format("woff2");
    unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD }
  @font-face { font-family: Inconsolata; font-style: normal; font-weight: 200 900; font-stretch: 100%;
    src: url(${inconsolataVietnamese}) format("woff2");
    unicode-range: U+0102-0103, U+0110-0111, U+0128-0129, U+0168-0169, U+01A0-01A1, U+01AF-01B0, U+0300-0301, U+0303-0304, U+0308-0309, U+0323, U+0329, U+1EA0-1EF9, U+20AB }
`

const CSS = `${FONT_FACE}
  @page { size: 80mm auto; margin: 0 }
  * { margin: 0; padding: 0; box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact }
  html, body { background: #fff; color: #000 }
  body { width: 68mm; margin: 0 auto; padding: 4mm 0 18mm; overflow-wrap: anywhere;
         font: 500 14.5px/1.3 Inconsolata, "Courier New", ui-monospace, monospace; color: #000 }
  .c { text-align: center }
  .b { font-weight: 700 }
  .xl { font-size: 22px; letter-spacing: 0.02em }
  .lg { font-size: 16.5px }
  .sm { font-size: 12px }
  .row { display: flex; justify-content: space-between; align-items: baseline; gap: 8px }
  /* the label may wrap; the amount (.num) never does, and has no fixed width of its own */
  .row > span:first-child { min-width: 0; overflow-wrap: anywhere }
  .num { text-align: right; white-space: nowrap }
  .cut { text-align: center; font-size: 11px; margin-top: 10px; letter-spacing: 0.2em }
  /* the bill: solid rules, thin and thick, and a rounded box for the total */
  .logo img { display: block; margin: 0 auto; filter: grayscale(1) contrast(1.4);
              max-height: ${LOGO_MAX_H_MM}mm; max-width: ${LOGO_MAX_W_MM}mm; object-fit: contain }
  .brand { font-weight: 800; font-size: 21px; letter-spacing: .06em; text-transform: uppercase; line-height: 1.15 }
  .oname { font-weight: 800; font-size: 17px; letter-spacing: .14em; text-transform: uppercase; margin-top: 4px; line-height: 1.15 }
  .hname { font-size: 12px; margin-top: 1px }
  .hr { border-top: 1px solid #000; margin: 5px 0 }
  .hr.thick { border-top: 3px solid #000; margin: 4px 0 }
  .box { border: 2.5px solid #000; border-radius: 11px; padding: 5px 8px 6px; margin: 10px 0 8px; text-align: center }
  .box .legal { font-weight: 800; font-size: 15px; line-height: 1.25 }
  .box .cap { font-weight: 800; font-size: 14.5px; letter-spacing: .04em; text-transform: uppercase }
  .box .big { font-weight: 800; font-size: 27px; line-height: 1.1; margin-top: 1px }
  .box .big.m { font-size: 22px }
  .box .cap.sm { font-size: 12px; letter-spacing: 0 }
  .where { font-weight: 800; font-size: 20px; letter-spacing: .05em; text-transform: uppercase }
  .hd { font-weight: 800; padding: 2px 0 }
  .it { padding: 4px 0 }
  .it + .it { border-top: 1px solid #000 }
  .it .n { font-weight: 700; overflow-wrap: anywhere }
  .it .a { font-weight: 700 }
  .tbl { width: 100%; border-collapse: collapse; font-size: inherit }
  .tbl td { padding: 4px 0; vertical-align: top }
  .tbl tr + tr td { border-top: 1px solid #000 }
  .tbl tr.h td { padding: 2px 0 3px; font-weight: 800; border-bottom: 3px solid #000 }
  .tbl tr.h + tr td { border-top: 0 }
  .tbl td.nm { font-weight: 700; overflow-wrap: anywhere }
  .tbl td.q, .tbl td.r, .tbl td.a { width: 1%; white-space: nowrap; text-align: right; padding-left: 1.4ch }
  .tbl td.a { font-weight: 700 }
  .tbl tr.h td.q, .tbl tr.h td.r, .tbl tr.h td.a { font-weight: 800 }
  .count { text-align: center; font-size: 12px }
  /* kitchen ticket and laundry docket: the same rules, an item list with a bold header row */
  .kt { width: 100%; border-collapse: collapse; font-size: 15.5px }
  .kt td { padding: 4px 0; vertical-align: top }
  .kt tr + tr td { border-top: 1px solid #000 }
  .kt tr.h td { padding: 2px 0 3px; font-weight: 800; font-size: 14.5px; border-bottom: 3px solid #000 }
  .kt tr.h + tr td { border-top: 0 }
  .kt td.q { width: 1%; white-space: nowrap; padding-right: 1.2ch; font-weight: 800; text-align: right }
  .kt tr.h td.q { text-align: right; padding-right: 1.2ch }
  .kt td.n { font-weight: 700; overflow-wrap: anywhere }
  .kt .ins { font-size: 13.5px; font-weight: 700 }
  .kt .mod { font-size: 14px; font-weight: 800 }
  .tbl .mod, .it .mod { font-size: 12px; font-weight: 500 }
  .kt .sv { font-size: 12px; font-weight: 500 }
  .flag { border: 2px solid #000; border-radius: 8px; padding: 2px 6px; text-align: center; font-weight: 800; letter-spacing: .04em; margin: 6px 0 }
  /* totals: the label hugs the value column, regular weight; the value is bold */
  .sum { display: grid; grid-template-columns: 1fr auto; column-gap: 14px; row-gap: 2px; margin: 4px 0 }
  .sum .l { text-align: right; text-transform: uppercase; overflow-wrap: anywhere }
  .sum .v { text-align: right; font-weight: 700; white-space: nowrap }
  .nc { border: 2px double #000; border-radius: 8px; padding: 3px 6px; text-align: center; font-weight: 800; letter-spacing: .04em; margin: 6px 0 }
  .thanks { text-align: center; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; margin-top: 6px }
  .bc { margin: 7px 0 5px }
  .bc svg { display: block; margin: 0 auto }
  .foot { text-align: center; font-size: 12px; line-height: 1.35 }
`

const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string))

/** Only an uploaded file or an https link may print as the logo: a javascript: or data: URL, a plain
 *  http one or a path with .. in it is ignored, and the outlet name prints instead. */
export const logoSrc = (u: unknown): string => {
  const s = String(u ?? "").trim()
  const allowed = /^(\/files\/|\/private\/files\/|https:\/\/)[^\s"'<>\\]+$/.test(s)
  // check the decoded path too, so /files/%2e%2e/x cannot step out of /files/
  let decoded: string
  try { decoded = decodeURIComponent(s) } catch { return "" }
  const noDotDot = (p: string) => !p.split("/").includes("..")
  return allowed && noDotDot(s) && noDotDot(decoded) ? s : ""
}

export function logoSizeMm(naturalWidth: number, naturalHeight: number) {
  const ratio = naturalWidth / naturalHeight
  let height = LOGO_MAX_H_MM
  let width = height * ratio
  if (width > LOGO_MAX_W_MM) {
    width = LOGO_MAX_W_MM
    height = width / ratio
  }
  return { width, height }
}

/** Size every logo in a ticket document by the rule above (needs the images loaded). */
export function fitLogos(doc: Document) {
  doc.querySelectorAll<HTMLImageElement>(".logo img").forEach((img) => {
    if (!img.naturalWidth || !img.naturalHeight) return
    const s = logoSizeMm(img.naturalWidth, img.naturalHeight)
    img.style.width = `${s.width.toFixed(2)}mm`
    img.style.height = `${s.height.toFixed(2)}mm`
  })
}

/** The whole HTML document for a ticket body (print and the settings preview share it). */
export function thermalDocument(title: string, body: string): string {
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(translate(title))}</title>` +
    `<style>${CSS}</style></head><body>${body}</body></html>`
}

/** Wait for the embedded font (for the characters actually used) and any images. */
export async function ticketAssetsReady(doc: Document) {
  const text = doc.body?.innerText || "A"
  await Promise.all([
    ...[500, 700, 800].map((w) => doc.fonts.load(`${w} 14px Inconsolata`, text).catch(() => [])),
    ...Array.from(doc.images).map((img) => img.decode().catch(() => undefined)),
  ])
}

/** Print without a popup. Popups get blocked on a till; an iframe does not. */
export function printThermal(title: string, body: string): boolean {
  document.querySelectorAll("iframe[data-kamra-print]").forEach((n) => n.remove())
  const iframe = document.createElement("iframe")
  iframe.setAttribute("data-kamra-print", "1")
  iframe.setAttribute("title", translate(title))
  iframe.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;opacity:0"
  document.body.appendChild(iframe)
  const w = iframe.contentWindow
  if (!w) { iframe.remove(); return false }
  w.document.open()
  w.document.write(thermalDocument(title, body))
  w.document.close()
  const cleanup = () => { try { iframe.remove() } catch { /* already gone */ } }
  w.onafterprint = cleanup
  // Print once the font and the logo are in (a fixed delay printed the fallback
  // font on a cold start), but never wait more than 2.5 s for them.
  const ready = Promise.race([
    ticketAssetsReady(w.document).then(() => fitLogos(w.document)),
    new Promise<void>((resolve) => setTimeout(resolve, 2500)),
  ])
  void ready.then(() => {
    try {
      w.focus()
      const t0 = performance.now()
      w.print() // blocks while a print dialog is open; returns at once with --kiosk-printing
      if (performance.now() - t0 > 1500) {
        window.dispatchEvent(new CustomEvent(PRINT_DIALOG_EVENT))
      }
    } catch { cleanup() }
  })
  setTimeout(cleanup, 120_000)
  return true
}

/** Fired when a print looked like it waited on a dialog: the till can tell
 *  staff how to print silently (Chrome --kiosk-printing). */
export const PRINT_DIALOG_EVENT = "kamra:print-dialog"

export interface KotLine {
  item_name: string
  qty: number
  instructions?: string | null
  /** the choices ticked for the dish (milk, size, extras), by name */
  modifiers?: string[]
}

/** The choices under a dish, one per line: "+ Oat milk". Empty when it has none. */
const modLines = (mods?: string[]) => (mods ?? []).map((m) => `<div class="mod">+ ${esc(m)}</div>`).join("")

export function kotHtml(o: {
  outlet: string
  kot_no: number | null
  label: string
  order_type?: string | null
  order: string
  reprint?: boolean
  customer?: string | null
  address?: string | null
  nc?: boolean
  nc_by?: string | null
  items: KotLine[]
  /** a kitchen printer's slice of the round: which station(s) it covers */
  station?: string | null
  /** Void: lines to stop cooking. Test: a printer test page. */
  kind?: string | null
  /** printed on the fallback because this printer failed */
  fallback_from?: string | null
}) {
  const when = new Date().toLocaleString(uiDateLocale(moneyLocale()), {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  })
  const rows = o.items.map((it) =>
    `<tr><td class="q">${Math.round(it.qty)}×</td>` +
    `<td class="n">${esc(it.item_name)}` + modLines(it.modifiers) +
    (it.instructions ? `<div class="ins">» ${esc(it.instructions)}</div>` : "") +
    `</td></tr>`).join("")
  const title = (o.kind === "Void" ? translate("*** VOID *** KOT #{number}", { number: String(o.kot_no ?? "-") })
    : o.kind === "Test" ? translate("TEST PAGE")
      : translate("KOT #{number}", { number: String(o.kot_no ?? "-") })) + (o.reprint ? translate(" (REPRINT)") : "")
  return `
    <div class="c oname">${esc(o.outlet)}</div>
    <div class="box">
      ${o.station ? `<div class="cap">${esc(o.station)}</div>` : ""}
      ${o.fallback_from ? `<div class="cap sm">${esc(translate("for"))} ${esc(o.fallback_from)}</div>` : ""}
      <div class="big${title.length > 14 ? " m" : ""}">${esc(title)}</div>
      ${o.nc ? `<div class="cap">${esc(translate("*** NC - NO CHARGE ***"))}</div>` +
        (o.nc_by ? `<div class="cap sm">${esc(translate("auth:"))} ${esc(o.nc_by)}</div>` : "") : ""}
    </div>
    <div class="row"><span class="where">${esc(translate(o.label))}</span><span>${esc(translate(o.order_type || ""))}</span></div>
    <div class="row sm"><span>${esc(o.order)}</span><span>${when}</span></div>
    ${o.customer ? `<div class="sm">${esc(translate("For:"))} ${esc(o.customer)}</div>` : ""}
    ${o.address ? `<div class="sm">→ ${esc(o.address)}</div>` : ""}
    <div class="hr"></div>
    <table class="kt"><tr class="h"><td class="q">${esc(translate("Qty"))}</td><td>${esc(translate("Item"))}</td></tr>${rows}</table>
    <div class="hr"></div>
    <div class="count">${esc(tn(o.items.length, "{n} item", "{n} items"))}</div>
    <div class="hr thick"></div>
    <div class="cut">${esc(translate("- cut -"))}</div>`
}

/** Several tickets in one print: one paper cut between each. */
export function joinTickets(bodies: string[]): string {
  return bodies.join('<div style="break-after:page;page-break-after:always"></div>')
}

export function laundryDocketHtml(o: {
  property_name?: string
  order: string
  room_no: string
  guest_name?: string | null
  order_type?: string
  express?: boolean
  ready_by?: string | null
  items: { item_name: string; service_type: string; qty: number }[]
  total: number
}) {
  const when = new Date().toLocaleString(uiDateLocale(moneyLocale()), {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  })
  const rows = o.items.map((it) =>
    `<tr><td class="q">${Math.round(it.qty)}×</td>` +
    `<td class="n">${esc(it.item_name)}<div class="sv">${esc(translate(it.service_type))}</div></td></tr>`).join("")
  return `
    <div class="c oname">${esc(o.property_name || translate("Laundry"))}</div>
    <div class="box">
      <div class="cap">${esc(translate("LAUNDRY DOCKET"))}</div>
      <div class="big">${esc(o.room_no)}</div>
    </div>
    <div class="row"><span class="where">${esc(translate(o.order_type || "Guest"))}</span><span class="sm">${esc(o.order)}</span></div>
    <div class="row sm"><span>${esc(o.guest_name || "")}</span><span>${when}</span></div>
    ${o.express ? `<div class="flag">${esc(translate("EXPRESS - SAME DAY"))}</div>` : ""}
    ${o.ready_by ? `<div class="sm">${esc(translate("Ready by:"))} ${esc(o.ready_by)}</div>` : ""}
    <div class="hr"></div>
    <table class="kt"><tr class="h"><td class="q">${esc(translate("Qty"))}</td><td>${esc(translate("Item"))}</td></tr>${rows}</table>
    <div class="hr"></div>
    <div class="sum"><span class="l">${esc(translate("Total"))}</span><span class="v">${cur()}${fmtAmount(o.total)}</span></div>
    <div class="hr thick"></div>
    <div class="c sm">${esc(translate("Counted with the guest. Billed to the room."))}</div>`
}

export interface BillData {
  order: string
  kot_no: number | null
  property_name: string
  outlet_name: string
  order_type: string | null
  table_no: string | null
  room_no: string | null
  customer_name: string | null
  customer_phone: string | null
  delivery_address: string | null
  captain: string | null
  /** the waiter typed on the bill, else the captain's name */
  served_by?: string | null
  /** who took payment or closed the bill */
  cashier?: string | null
  /** the outlet's receipt logo (a file URL), printed at the top when set */
  logo?: string | null
  /** how the item lines print: in columns (the default) or stacked */
  receipt_design?: "Stacked" | "Columns" | null
  /** the outlet's "print a barcode" switch: the barcode prints unless this is 0 or false */
  barcode?: boolean | number | null
  /** `rate` already includes the dish's choices; `modifiers` are their names, printed under the dish */
  items: { item_name: string; qty: number; rate: number; amount: number; modifiers?: string[] }[]
  subtotal: number
  discount_amount: number
  /** the outlet's levy (a service charge) as charged on this bill; none when absent */
  levy?: { label: string; percent: number; amount: number } | null
  taxable: number
  gst_rate: number
  cgst: number
  sgst: number
  /** The tax named and split the country's way (CGST+SGST, or one VAT). */
  tax_label?: string
  tax_parts?: { label: string; rate: number; amount: number }[]
  /** ZATCA QR + Arabic title where the country requires them. */
  statutory?: { title: string; title_ar: string; qr_image: string; icv: number } | null
  grand_total: number
  paid: number
  payment_mode: string | null
  nc: number
  nc_authorized_by: string | null
  nc_note: string | null
}

/** Only the settings-page preview passes these: example numbers, no currency symbol. */
export interface BillOptions {
  fmt?: (n: number) => string
  symbol?: string
  /** decimals `fmt` prints with; the property currency's own when not given */
  digits?: number
}

export function billHtml(b: BillData, opts: BillOptions = {}) {
  const f = opts.fmt ?? fmtAmount
  const sym = opts.symbol ?? cur()
  const when = new Date().toLocaleString(uiDateLocale(moneyLocale()), {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  })
  const label = b.table_no ? translate("Table {n}", { n: String(b.table_no) })
    : b.room_no ? translate("Room {n}", { n: String(b.room_no) }) : translate(b.order_type || "Counter")
  const logo = logoSrc(b.logo)
  const head = (logo
    ? `<div class="logo"><img src="${esc(logo)}" alt=""></div><div class="c oname">${esc(b.outlet_name)}</div>`
    : `<div class="c brand">${esc(b.outlet_name)}</div>`) +
    `<div class="c hname">${esc(b.property_name)}</div>`
  // the printed figures add up: lines, then subtotal = their sum, and a Rounding line only
  // when the printed pieces still miss the printed total (see lib/addUp.ts)
  const taxParts = b.tax_parts ?? [
    { label: "CGST", rate: b.gst_rate / 2, amount: b.cgst },
    { label: "SGST", rate: b.gst_rate / 2, amount: b.sgst },
  ]
  const fig = addUp({
    digits: opts.digits ?? moneyDigits(), lines: b.items.map((it) => it.amount),
    discount: b.discount_amount, levy: b.levy?.amount, taxes: taxParts.map((p) => p.amount),
    total: b.grand_total,
  })
  const columns = b.receipt_design !== "Stacked"   // Columns is the default
  // the item header row (bold) and the thick rule under it; the columns design has them inside its table
  const itemHead = columns ? "" :
    `<div class="row hd"><span>${esc(translate("Item"))}</span><span>${esc(translate("Amount"))}</span></div><div class="hr thick"></div>`
  const items = columns
    ? `<table class="tbl"><tr class="h"><td>${esc(translate("Item"))}</td><td class="q">${esc(translate("Qty"))}</td>` +
      `<td class="r">${esc(translate("Rate"))}</td><td class="a">${esc(translate("Amt"))}</td></tr>` +
      b.items.map((it, i) =>
        `<tr><td class="nm">${esc(it.item_name)}${modLines(it.modifiers)}</td><td class="q">${Math.round(it.qty)}</td>` +
        `<td class="r">${f(it.rate)}</td><td class="a">${f(fig.lines[i])}</td></tr>`).join("") + `</table>`
    : b.items.map((it, i) =>
      `<div class="it"><div class="n">${esc(it.item_name)}</div>${modLines(it.modifiers)}<div class="row"><span>${Math.round(it.qty)} x ${f(it.rate)}</span>` +
      `<span class="a num">${f(fig.lines[i])}</span></div></div>`).join("")
  const sum = (l: string, v: number) => `<span class="l">${l}</span><span class="v">${f(v)}</span>`
  const n = b.items.length
  const customer = [b.customer_name, b.customer_phone].filter(Boolean).join(" · ")
  const barcode = b.barcode === 0 || b.barcode === false ? "" : code128Svg(b.order)
  const served = b.served_by || ""
  // the total in a rounded box at the top: "BILL / RECEIPT <order> TOTAL", then the amount. A country that
  // requires a legal title on the bill (ZATCA) puts it in the box in place of BILL / RECEIPT.
  const caption = `${b.statutory ? "" : esc(b.paid ? translate("RECEIPT") : translate("BILL")) + " "}${esc(b.order)} ${esc(translate("TOTAL"))}`
  const box = `<div class="box">` +
    (b.statutory ? `<div class="legal">${esc(b.statutory.title)}</div><div class="legal" dir="rtl">${esc(b.statutory.title_ar)}</div>` : "") +
    `<div class="cap">${caption}</div>` +
    `<div class="big">${esc(sym)}${/\w$/.test(sym) ? " " : ""}${f(fig.total)}</div></div>`
  return `
    ${head}
    ${box}
    <div class="row"><span class="where">${esc(label)}</span><span>${esc(translate(b.order_type || ""))}</span></div>
    <div class="row sm"><span>${esc(customer)}</span><span>${esc(translate("KOT #{number}", { number: String(b.kot_no ?? "-") }))}</span></div>
    ${b.delivery_address ? `<div class="sm">→ ${esc(b.delivery_address)}</div>` : ""}
    <div class="hr"></div>
    ${itemHead}
    ${items}
    <div class="hr"></div>
    <div class="count">${esc(tn(n, "{n} item", "{n} items"))}</div>
    <div class="sum">
      ${sum(esc(translate("Subtotal")), fig.subtotal)}
      ${b.discount_amount ? sum(esc(translate("Discount")), -fig.discount) : ""}
      ${b.levy ? sum(`${esc(b.levy.label || translate("Service charge"))} ${b.levy.percent}%`, fig.levy) : ""}
      ${taxParts.map((p, i) => sum(`${esc(p.label)} @ ${p.rate}%`, fig.taxes[i])).join("")}
      ${fig.rounding !== 0 && !b.nc ? sum(esc(translate("Rounding")), fig.rounding) : ""}
      ${sum(esc(translate("TOTAL")), fig.total)}
    </div>
    ${b.paid && b.payment_mode && !b.nc ? `<div class="hr"></div><div class="sum">${sum(esc(translate(b.payment_mode)), fig.total)}</div>` : ""}
    <div class="hr thick"></div>
    ${b.nc ? `<div class="nc">${esc(translate("COMPLIMENTARY - NO CHARGE"))}</div>` +
      `<div class="c sm">${esc(translate("auth:"))} ${esc(b.nc_authorized_by || "-")}${b.nc_note ? ` · ${esc(b.nc_note)}` : ""}</div>` : ""}
    ${b.statutory ? `<div class="c"><img src="${esc(b.statutory.qr_image)}" alt="QR" style="width:120px;height:120px"/></div>` +
      `<div class="c sm">ICV ${esc(b.statutory.icv)}</div>` : ""}
    <div class="thanks">${esc(translate("Thank you. See you again."))}</div>
    ${barcode ? `<div class="bc">${barcode}</div>` : ""}
    <div class="foot">
      <div>${esc(translate("Date:"))} ${esc(when)}</div>
      ${served ? `<div>${esc(translate("Served by:"))} ${esc(served)}</div>` : ""}
      ${b.cashier && b.cashier !== served ? `<div>${esc(translate("Cashier:"))} ${esc(b.cashier)}</div>` : ""}
      <div>${esc(translate("Order:"))} ${esc(b.order)}</div>
    </div>
    <div class="cut">${esc(translate("- cut -"))}</div>`
}
