import{m as o,f as r}from"./index--k4Sk6TE.js";const p=`
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
`,t=s=>String(s??"").replace(/[&<>"]/g,e=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[e]),l=s=>Number(s??0).toLocaleString(o(),{minimumFractionDigits:2,maximumFractionDigits:2});function v(s,e){const a=window.open("","_blank","width=380,height=640");a&&(a.document.write(`<!doctype html><html><head><title>${t(s)}</title><style>${p}</style></head><body>${e}</body></html>`),a.document.close(),a.focus(),a.onafterprint=()=>a.close(),setTimeout(()=>a.print(),250))}function $(s){const e=new Date().toLocaleString(o(),{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}),a=s.items.map(i=>`<tr><td class="num b" style="width:24px">${Math.round(i.qty)}×</td><td class="b">${t(i.item_name)}</td></tr>`+(i.instructions?`<tr><td></td><td class="ins">» ${t(i.instructions)}</td></tr>`:"")).join("");return`
    <div class="c b lg">${t(s.outlet)}</div>
    <div class="c xl b">KOT #${s.kot_no??"—"}${s.reprint?" (REPRINT)":""}</div>
    ${s.nc?'<div class="c b lg">*** NC — NO CHARGE ***</div>'+(s.nc_by?`<div class="c sm">auth: ${t(s.nc_by)}</div>`:""):""}
    <div class="rule"></div>
    <div class="row"><span class="b lg">${t(s.label)}</span><span class="sm">${t(s.order_type||"")}</span></div>
    <div class="row sm"><span>${t(s.order)}</span><span>${e}</span></div>
    ${s.customer?`<div class="sm">For: ${t(s.customer)}</div>`:""}
    ${s.address?`<div class="sm">→ ${t(s.address)}</div>`:""}
    <div class="rule"></div>
    <table>${a}</table>
    <div class="rule"></div>
    <div class="c sm">${s.items.length} item${s.items.length===1?"":"s"}</div>`}function g(s){const e=new Date().toLocaleString(o(),{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}),a=s.items.map(i=>`<tr><td class="num b" style="width:26px">${Math.round(i.qty)}×</td><td class="b">${t(i.item_name)}<div class="sm" style="font-weight:400">${t(i.service_type)}</div></td></tr>`).join("");return`
    <div class="c b lg">${t(s.property_name||"Laundry")}</div>
    <div class="c xl b">LAUNDRY DOCKET</div>
    <div class="rule"></div>
    <div class="row"><span class="b lg">${t(s.room_no)}</span><span class="sm">${t(s.order_type||"Guest")}</span></div>
    <div class="row sm"><span>${t(s.order)}</span><span>${e}</span></div>
    ${s.guest_name?`<div class="sm">${t(s.guest_name)}</div>`:""}
    ${s.express?'<div class="c b">EXPRESS — SAME DAY</div>':""}
    ${s.ready_by?`<div class="sm">Ready by: ${t(s.ready_by)}</div>`:""}
    <div class="rule"></div>
    <table>${a}</table>
    <div class="rule"></div>
    <div class="row b lg"><span>Total</span><span class="num">${r()}${l(s.total)}</span></div>
    <div class="c sm">Counted with the guest. Billed to the room.</div>`}function y(s){const e=new Date().toLocaleString(o(),{day:"2-digit",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit"}),a=s.table_no?`Table ${s.table_no}`:s.room_no?`Room ${s.room_no}`:s.order_type||"Counter",i=s.items.map(n=>`<tr><td>${t(n.item_name)}</td><td class="num" style="width:28px">${Math.round(n.qty)}</td><td class="num" style="width:52px">${l(n.rate)}</td><td class="num" style="width:62px">${l(n.amount)}</td></tr>`).join(""),d=(n,c,m="")=>`<div class="row ${m}"><span>${n}</span><span class="num">${r()}${l(c)}</span></div>`;return`
    <div class="c b lg">${t(s.property_name)}</div>
    <div class="c">${t(s.outlet_name)}</div>
    <div class="rule"></div>
    <div class="row"><span class="b">${t(a)}</span><span>${e}</span></div>
    <div class="row sm"><span>Bill: ${t(s.order)}</span><span>KOT #${s.kot_no??"—"}</span></div>
    ${s.customer_name||s.customer_phone?`<div class="sm">${t([s.customer_name,s.customer_phone].filter(Boolean).join(" · "))}</div>`:""}
    ${s.delivery_address?`<div class="sm">→ ${t(s.delivery_address)}</div>`:""}
    <div class="rule"></div>
    <table>
      <tr class="sm"><td>Item</td><td class="num">Qty</td><td class="num">Rate</td><td class="num">Amt</td></tr>
      ${i}
    </table>
    <div class="rule"></div>
    ${d("Subtotal",s.subtotal)}
    ${s.discount_amount?d("Discount",-s.discount_amount):""}
    ${d(`CGST @ ${s.gst_rate/2}%`,s.cgst,"sm")}
    ${d(`SGST @ ${s.gst_rate/2}%`,s.sgst,"sm")}
    <div class="rule"></div>
    ${d("TOTAL",s.grand_total,"b lg")}
    ${s.nc?`<div class="c b" style="margin-top:4px">COMPLIMENTARY — NO CHARGE</div><div class="c sm">auth: ${t(s.nc_authorized_by||"—")}${s.nc_note?` · ${t(s.nc_note)}`:""}</div>`:""}
    ${s.paid?`<div class="c b" style="margin-top:4px">PAID · ${t(s.payment_mode)}</div>`:""}
    <div class="rule"></div>
    <div class="c sm">Thank you — see you again!</div>`}export{y as b,$ as k,g as l,v as p};
