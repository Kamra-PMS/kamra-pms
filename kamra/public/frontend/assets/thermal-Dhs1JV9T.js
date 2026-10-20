import{m as l,c as o}from"./index-BbDYFc6T.js";const p=`
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
`,s=t=>String(t??"").replace(/[&<>"]/g,n=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[n]),r=t=>Number(t??0).toLocaleString(l(),{minimumFractionDigits:2,maximumFractionDigits:2});function $(t,n){document.querySelectorAll("iframe[data-kamra-print]").forEach(e=>e.remove());const i=document.createElement("iframe");i.setAttribute("data-kamra-print","1"),i.setAttribute("title",t),i.style.cssText="position:fixed;right:0;bottom:0;width:0;height:0;border:0;opacity:0",document.body.appendChild(i);const a=i.contentWindow;if(!a)return i.remove(),!1;a.document.open(),a.document.write(`<!doctype html><html><head><title>${s(t)}</title><style>${p}</style></head><body>${n}</body></html>`),a.document.close();const d=()=>{try{i.remove()}catch{}};return a.onafterprint=d,setTimeout(()=>{try{a.focus();const e=performance.now();a.print(),performance.now()-e>1500&&window.dispatchEvent(new CustomEvent(u))}catch{d()}},0),setTimeout(d,12e4),!0}const u="kamra:print-dialog";function g(t){const n=new Date().toLocaleString(l(),{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}),i=t.items.map(a=>`<tr><td class="num b" style="width:24px">${Math.round(a.qty)}×</td><td class="b">${s(a.item_name)}</td></tr>`+(a.instructions?`<tr><td></td><td class="ins">» ${s(a.instructions)}</td></tr>`:"")).join("");return`
    <div class="c b lg">${s(t.outlet)}</div>
    <div class="c xl b">${t.kind==="Void"?`*** VOID *** KOT #${t.kot_no??"—"}`:t.kind==="Test"?"TEST PAGE":`KOT #${t.kot_no??"—"}`}${t.reprint?" (REPRINT)":""}</div>
    ${t.station?`<div class="c b">${s(t.station)}</div>`:""}
    ${t.fallback_from?`<div class="c sm">for ${s(t.fallback_from)}</div>`:""}
    ${t.nc?'<div class="c b lg">*** NC - NO CHARGE ***</div>'+(t.nc_by?`<div class="c sm">auth: ${s(t.nc_by)}</div>`:""):""}
    <div class="rule"></div>
    <div class="row"><span class="b lg">${s(t.label)}</span><span class="sm">${s(t.order_type||"")}</span></div>
    <div class="row sm"><span>${s(t.order)}</span><span>${n}</span></div>
    ${t.customer?`<div class="sm">For: ${s(t.customer)}</div>`:""}
    ${t.address?`<div class="sm">→ ${s(t.address)}</div>`:""}
    <div class="rule"></div>
    <table>${i}</table>
    <div class="rule"></div>
    <div class="c sm">${t.items.length} item${t.items.length===1?"":"s"}</div>
    <div class="cut">- cut -</div>`}function y(t){return t.join('<div style="break-after:page;page-break-after:always"></div>')}function h(t){const n=new Date().toLocaleString(l(),{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}),i=t.items.map(a=>`<tr><td class="num b" style="width:26px">${Math.round(a.qty)}×</td><td class="b">${s(a.item_name)}<div class="sm" style="font-weight:400">${s(a.service_type)}</div></td></tr>`).join("");return`
    <div class="c b lg">${s(t.property_name||"Laundry")}</div>
    <div class="c xl b">LAUNDRY DOCKET</div>
    <div class="rule"></div>
    <div class="row"><span class="b lg">${s(t.room_no)}</span><span class="sm">${s(t.order_type||"Guest")}</span></div>
    <div class="row sm"><span>${s(t.order)}</span><span>${n}</span></div>
    ${t.guest_name?`<div class="sm">${s(t.guest_name)}</div>`:""}
    ${t.express?'<div class="c b">EXPRESS - SAME DAY</div>':""}
    ${t.ready_by?`<div class="sm">Ready by: ${s(t.ready_by)}</div>`:""}
    <div class="rule"></div>
    <table>${i}</table>
    <div class="rule"></div>
    <div class="row b lg"><span>Total</span><span class="num">${o()}${r(t.total)}</span></div>
    <div class="c sm">Counted with the guest. Billed to the room.</div>`}function _(t){const n=new Date().toLocaleString(l(),{day:"2-digit",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit"}),i=t.table_no?`Table ${t.table_no}`:t.room_no?`Room ${t.room_no}`:t.order_type||"Counter",a=t.items.map(e=>`<tr><td>${s(e.item_name)}</td><td class="num" style="width:28px">${Math.round(e.qty)}</td><td class="num" style="width:52px">${r(e.rate)}</td><td class="num" style="width:62px">${r(e.amount)}</td></tr>`).join(""),d=(e,c,m="")=>`<div class="row ${m}"><span>${e}</span><span class="num">${o()}${r(c)}</span></div>`;return`
    <div class="c b lg">${s(t.property_name)}</div>
    <div class="c">${s(t.outlet_name)}</div>
    ${t.statutory?`<div class="c b sm">${s(t.statutory.title)}</div><div class="c b sm" dir="rtl">${s(t.statutory.title_ar)}</div>`:""}
    <div class="rule"></div>
    <div class="row"><span class="b">${s(i)}</span><span>${n}</span></div>
    <div class="row sm"><span>Bill: ${s(t.order)}</span><span>KOT #${t.kot_no??"—"}</span></div>
    ${t.customer_name||t.customer_phone?`<div class="sm">${s([t.customer_name,t.customer_phone].filter(Boolean).join(" · "))}</div>`:""}
    ${t.delivery_address?`<div class="sm">→ ${s(t.delivery_address)}</div>`:""}
    <div class="rule"></div>
    <table>
      <tr class="sm"><td>Item</td><td class="num">Qty</td><td class="num">Rate</td><td class="num">Amt</td></tr>
      ${a}
    </table>
    <div class="rule"></div>
    ${d("Subtotal",t.subtotal)}
    ${t.discount_amount?d("Discount",-t.discount_amount):""}
    ${(t.tax_parts??[{label:"CGST",rate:t.gst_rate/2,amount:t.cgst},{label:"SGST",rate:t.gst_rate/2,amount:t.sgst}]).map(e=>d(`${s(e.label)} @ ${e.rate}%`,e.amount,"sm")).join("")}
    <div class="rule"></div>
    ${d("TOTAL",t.grand_total,"b lg")}
    ${t.nc?`<div class="c b" style="margin-top:4px">COMPLIMENTARY - NO CHARGE</div><div class="c sm">auth: ${s(t.nc_authorized_by||"—")}${t.nc_note?` · ${s(t.nc_note)}`:""}</div>`:""}
    ${t.paid?`<div class="c b" style="margin-top:4px">PAID · ${s(t.payment_mode)}</div>`:""}
    <div class="rule"></div>
    ${t.statutory?`<div class="c"><img src="${t.statutory.qr_image}" alt="QR" style="width:120px;height:120px"/></div><div class="c sm">ICV ${t.statutory.icv}</div>`:""}
    <div class="c sm">Thank you. See you again.</div>
    <div class="cut">- cut -</div>`}export{u as P,_ as b,y as j,g as k,h as l,$ as p};
