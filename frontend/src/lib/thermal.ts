/** 80mm thermal printing for KOT tickets and bills.
 *
 * Opens a bare popup, renders the ticket with an `@page: 80mm` sheet and a
 * monospace layout, prints, and closes itself after the print dialog. Works
 * with any OS-installed thermal driver (80mm and 58mm both render fine -
 * the body is 72mm, the common printable width).
 */

const CSS = `
  @page { size: 80mm auto; margin: 0 }
  * { margin: 0; padding: 0; box-sizing: border-box }
  body { width: 72mm; margin: 0 auto; padding: 4mm 0 10mm;
         font: 12px/1.45 "Courier New", ui-monospace, monospace; color: #000 }
  .c { text-align: center }
  .b { font-weight: 700 }
  .xl { font-size: 17px }
  .lg { font-size: 14px }
  .sm { font-size: 11px }
  .rule { border-top: 1px dashed #000; margin: 4px 0 }
  .row { display: flex; justify-content: space-between; gap: 8px }
  table { width: 100%; border-collapse: collapse; font-size: 12px }
  td { padding: 1px 0; vertical-align: top }
  .num { text-align: right; white-space: nowrap }
  .ins { font-size: 11px; padding-left: 14px }
`

const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string))

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export function printThermal(title: string, body: string) {
  const w = window.open("", "_blank", "width=380,height=640")
  if (!w) return
  w.document.write(
    `<!doctype html><html><head><title>${esc(title)}</title>` +
    `<style>${CSS}</style></head><body>${body}</body></html>`)
  w.document.close()
  w.focus()
  w.onafterprint = () => w.close()
  setTimeout(() => w.print(), 250)
}

export interface KotLine { item_name: string; qty: number; instructions?: string | null }

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
}) {
  const when = new Date().toLocaleString("en-IN", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  })
  const rows = o.items.map((it) =>
    `<tr><td class="num b" style="width:24px">${Math.round(it.qty)}×</td>` +
    `<td class="b">${esc(it.item_name)}</td></tr>` +
    (it.instructions
      ? `<tr><td></td><td class="ins">» ${esc(it.instructions)}</td></tr>`
      : "")).join("")
  return `
    <div class="c b lg">${esc(o.outlet)}</div>
    <div class="c xl b">KOT #${o.kot_no ?? "—"}${o.reprint ? " (REPRINT)" : ""}</div>
    ${o.nc ? `<div class="c b lg">*** NC — NO CHARGE ***</div>` +
      (o.nc_by ? `<div class="c sm">auth: ${esc(o.nc_by)}</div>` : "") : ""}
    <div class="rule"></div>
    <div class="row"><span class="b lg">${esc(o.label)}</span><span class="sm">${esc(o.order_type || "")}</span></div>
    <div class="row sm"><span>${esc(o.order)}</span><span>${when}</span></div>
    ${o.customer ? `<div class="sm">For: ${esc(o.customer)}</div>` : ""}
    ${o.address ? `<div class="sm">→ ${esc(o.address)}</div>` : ""}
    <div class="rule"></div>
    <table>${rows}</table>
    <div class="rule"></div>
    <div class="c sm">${o.items.length} item${o.items.length === 1 ? "" : "s"}</div>`
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
  const when = new Date().toLocaleString("en-IN", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  })
  const rows = o.items.map((it) =>
    `<tr><td class="num b" style="width:26px">${Math.round(it.qty)}×</td>` +
    `<td class="b">${esc(it.item_name)}` +
    `<div class="sm" style="font-weight:400">${esc(it.service_type)}</div>` +
    `</td></tr>`).join("")
  return `
    <div class="c b lg">${esc(o.property_name || "Laundry")}</div>
    <div class="c xl b">LAUNDRY DOCKET</div>
    <div class="rule"></div>
    <div class="row"><span class="b lg">${esc(o.room_no)}</span>` +
    `<span class="sm">${esc(o.order_type || "Guest")}</span></div>
    <div class="row sm"><span>${esc(o.order)}</span><span>${when}</span></div>
    ${o.guest_name ? `<div class="sm">${esc(o.guest_name)}</div>` : ""}
    ${o.express ? `<div class="c b">EXPRESS — SAME DAY</div>` : ""}
    ${o.ready_by ? `<div class="sm">Ready by: ${esc(o.ready_by)}</div>` : ""}
    <div class="rule"></div>
    <table>${rows}</table>
    <div class="rule"></div>
    <div class="row b lg"><span>Total</span><span class="num">₹${inr(o.total)}</span></div>
    <div class="c sm">Counted with the guest. Billed to the room.</div>`
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
  items: { item_name: string; qty: number; rate: number; amount: number }[]
  subtotal: number
  discount_amount: number
  taxable: number
  gst_rate: number
  cgst: number
  sgst: number
  grand_total: number
  paid: number
  payment_mode: string | null
  nc: number
  nc_authorized_by: string | null
  nc_note: string | null
}

export function billHtml(b: BillData) {
  const when = new Date().toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  })
  const label = b.table_no ? `Table ${b.table_no}`
    : b.room_no ? `Room ${b.room_no}` : (b.order_type || "Counter")
  const rows = b.items.map((it) =>
    `<tr><td>${esc(it.item_name)}</td>` +
    `<td class="num" style="width:28px">${Math.round(it.qty)}</td>` +
    `<td class="num" style="width:52px">${inr(it.rate)}</td>` +
    `<td class="num" style="width:62px">${inr(it.amount)}</td></tr>`).join("")
  const money = (l: string, v: number, cls = "") =>
    `<div class="row ${cls}"><span>${l}</span><span class="num">₹${inr(v)}</span></div>`
  return `
    <div class="c b lg">${esc(b.property_name)}</div>
    <div class="c">${esc(b.outlet_name)}</div>
    <div class="rule"></div>
    <div class="row"><span class="b">${esc(label)}</span><span>${when}</span></div>
    <div class="row sm"><span>Bill: ${esc(b.order)}</span><span>KOT #${b.kot_no ?? "—"}</span></div>
    ${b.customer_name || b.customer_phone
      ? `<div class="sm">${esc([b.customer_name, b.customer_phone].filter(Boolean).join(" · "))}</div>` : ""}
    ${b.delivery_address ? `<div class="sm">→ ${esc(b.delivery_address)}</div>` : ""}
    <div class="rule"></div>
    <table>
      <tr class="sm"><td>Item</td><td class="num">Qty</td><td class="num">Rate</td><td class="num">Amt</td></tr>
      ${rows}
    </table>
    <div class="rule"></div>
    ${money("Subtotal", b.subtotal)}
    ${b.discount_amount ? money("Discount", -b.discount_amount) : ""}
    ${money(`CGST @ ${b.gst_rate / 2}%`, b.cgst, "sm")}
    ${money(`SGST @ ${b.gst_rate / 2}%`, b.sgst, "sm")}
    <div class="rule"></div>
    ${money("TOTAL", b.grand_total, "b lg")}
    ${b.nc ? `<div class="c b" style="margin-top:4px">COMPLIMENTARY — NO CHARGE</div>` +
      `<div class="c sm">auth: ${esc(b.nc_authorized_by || "—")}${b.nc_note ? ` · ${esc(b.nc_note)}` : ""}</div>` : ""}
    ${b.paid ? `<div class="c b" style="margin-top:4px">PAID · ${esc(b.payment_mode)}</div>` : ""}
    <div class="rule"></div>
    <div class="c sm">Thank you — see you again!</div>`
}
