import{m as r,f as o}from"./index-DZFduFl8.js";const p=`
  @page { size: 80mm auto; margin: 0 }
  * { margin: 0; padding: 0; box-sizing: border-box }
  html, body { background: #fff; color: #000 }
  body { width: 72mm; margin: 0 auto; padding: 3mm 1mm 18mm;
         font: 13px/1.35 "Courier New", ui-monospace, monospace; color: #000 }
  .c { text-align: center }
  .b { font-weight: 700 }
  .xl { font-size: 20px; letter-spacing: 0.02em }
  .lg { font-size: 15px }
  .sm { font-size: 11px }
  .rule { border-top: 2px dashed #000; margin: 6px 0 }
  .row { display: flex; justify-content: space-between; gap: 8px }
  table { width: 100%; border-collapse: collapse; font-size: 14px }
  td { padding: 3px 0; vertical-align: top }
  .num { text-align: right; white-space: nowrap; font-weight: 700; width: 28px }
  .ins { font-size: 12px; font-weight: 700; padding-left: 28px }
  .cut { text-align: center; font-size: 10px; margin-top: 10px; letter-spacing: 0.2em }
`,s=t=>String(t??"").replace(/[&<>"]/g,i=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[i]),l=t=>Number(t??0).toLocaleString(r(),{minimumFractionDigits:2,maximumFractionDigits:2});function v(t,i){document.querySelectorAll("iframe[data-kamra-print]").forEach(d=>d.remove());const a=document.createElement("iframe");a.setAttribute("data-kamra-print","1"),a.setAttribute("title",t),a.style.cssText="position:fixed;right:0;bottom:0;width:0;height:0;border:0;opacity:0",document.body.appendChild(a);const e=a.contentWindow;if(!e)return a.remove(),!1;e.document.open(),e.document.write(`<!doctype html><html><head><title>${s(t)}</title><style>${p}</style></head><body>${i}</body></html>`),e.document.close();const n=()=>{try{a.remove()}catch{}};return e.onafterprint=n,setTimeout(()=>{try{e.focus(),e.print()}catch{n()}},200),setTimeout(n,12e4),!0}function $(t){const i=new Date().toLocaleString(r(),{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}),a=t.items.map(e=>`<tr><td class="num b" style="width:24px">${Math.round(e.qty)}×</td><td class="b">${s(e.item_name)}</td></tr>`+(e.instructions?`<tr><td></td><td class="ins">» ${s(e.instructions)}</td></tr>`:"")).join("");return`
    <div class="c b lg">${s(t.outlet)}</div>
    <div class="c xl b">KOT #${t.kot_no??"—"}${t.reprint?" (REPRINT)":""}</div>
    ${t.nc?'<div class="c b lg">*** NC - NO CHARGE ***</div>'+(t.nc_by?`<div class="c sm">auth: ${s(t.nc_by)}</div>`:""):""}
    <div class="rule"></div>
    <div class="row"><span class="b lg">${s(t.label)}</span><span class="sm">${s(t.order_type||"")}</span></div>
    <div class="row sm"><span>${s(t.order)}</span><span>${i}</span></div>
    ${t.customer?`<div class="sm">For: ${s(t.customer)}</div>`:""}
    ${t.address?`<div class="sm">→ ${s(t.address)}</div>`:""}
    <div class="rule"></div>
    <table>${a}</table>
    <div class="rule"></div>
    <div class="c sm">${t.items.length} item${t.items.length===1?"":"s"}</div>
    <div class="cut">- cut -</div>`}function g(t){const i=new Date().toLocaleString(r(),{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}),a=t.items.map(e=>`<tr><td class="num b" style="width:26px">${Math.round(e.qty)}×</td><td class="b">${s(e.item_name)}<div class="sm" style="font-weight:400">${s(e.service_type)}</div></td></tr>`).join("");return`
    <div class="c b lg">${s(t.property_name||"Laundry")}</div>
    <div class="c xl b">LAUNDRY DOCKET</div>
    <div class="rule"></div>
    <div class="row"><span class="b lg">${s(t.room_no)}</span><span class="sm">${s(t.order_type||"Guest")}</span></div>
    <div class="row sm"><span>${s(t.order)}</span><span>${i}</span></div>
    ${t.guest_name?`<div class="sm">${s(t.guest_name)}</div>`:""}
    ${t.express?'<div class="c b">EXPRESS - SAME DAY</div>':""}
    ${t.ready_by?`<div class="sm">Ready by: ${s(t.ready_by)}</div>`:""}
    <div class="rule"></div>
    <table>${a}</table>
    <div class="rule"></div>
    <div class="row b lg"><span>Total</span><span class="num">${o()}${l(t.total)}</span></div>
    <div class="c sm">Counted with the guest. Billed to the room.</div>`}function h(t){const i=new Date().toLocaleString(r(),{day:"2-digit",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit"}),a=t.table_no?`Table ${t.table_no}`:t.room_no?`Room ${t.room_no}`:t.order_type||"Counter",e=t.items.map(d=>`<tr><td>${s(d.item_name)}</td><td class="num" style="width:28px">${Math.round(d.qty)}</td><td class="num" style="width:52px">${l(d.rate)}</td><td class="num" style="width:62px">${l(d.amount)}</td></tr>`).join(""),n=(d,c,m="")=>`<div class="row ${m}"><span>${d}</span><span class="num">${o()}${l(c)}</span></div>`;return`
    <div class="c b lg">${s(t.property_name)}</div>
    <div class="c">${s(t.outlet_name)}</div>
    <div class="rule"></div>
    <div class="row"><span class="b">${s(a)}</span><span>${i}</span></div>
    <div class="row sm"><span>Bill: ${s(t.order)}</span><span>KOT #${t.kot_no??"—"}</span></div>
    ${t.customer_name||t.customer_phone?`<div class="sm">${s([t.customer_name,t.customer_phone].filter(Boolean).join(" · "))}</div>`:""}
    ${t.delivery_address?`<div class="sm">→ ${s(t.delivery_address)}</div>`:""}
    <div class="rule"></div>
    <table>
      <tr class="sm"><td>Item</td><td class="num">Qty</td><td class="num">Rate</td><td class="num">Amt</td></tr>
      ${e}
    </table>
    <div class="rule"></div>
    ${n("Subtotal",t.subtotal)}
    ${t.discount_amount?n("Discount",-t.discount_amount):""}
    ${n(`CGST @ ${t.gst_rate/2}%`,t.cgst,"sm")}
    ${n(`SGST @ ${t.gst_rate/2}%`,t.sgst,"sm")}
    <div class="rule"></div>
    ${n("TOTAL",t.grand_total,"b lg")}
    ${t.nc?`<div class="c b" style="margin-top:4px">COMPLIMENTARY - NO CHARGE</div><div class="c sm">auth: ${s(t.nc_authorized_by||"—")}${t.nc_note?` · ${s(t.nc_note)}`:""}</div>`:""}
    ${t.paid?`<div class="c b" style="margin-top:4px">PAID · ${s(t.payment_mode)}</div>`:""}
    <div class="rule"></div>
    <div class="c sm">Thank you. See you again.</div>
    <div class="cut">- cut -</div>`}export{h as b,$ as k,g as l,v as p};
