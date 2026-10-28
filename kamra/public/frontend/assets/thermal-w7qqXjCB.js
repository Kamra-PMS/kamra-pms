import{t as a,a as c,m as o,c as m}from"./index-b0899Jh3.js";const v=`
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
`,s=t=>String(t??"").replace(/[&<>"]/g,d=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[d]),l=t=>Number(t??0).toLocaleString(o(),{minimumFractionDigits:2,maximumFractionDigits:2});function y(t,d){document.querySelectorAll("iframe[data-kamra-print]").forEach(i=>i.remove());const n=document.createElement("iframe");n.setAttribute("data-kamra-print","1"),n.setAttribute("title",a(t)),n.style.cssText="position:fixed;right:0;bottom:0;width:0;height:0;border:0;opacity:0",document.body.appendChild(n);const e=n.contentWindow;if(!e)return n.remove(),!1;e.document.open(),e.document.write(`<!doctype html><html><head><title>${s(a(t))}</title><style>${v}</style></head><body>${d}</body></html>`),e.document.close();const r=()=>{try{n.remove()}catch{}};return e.onafterprint=r,setTimeout(()=>{try{e.focus();const i=performance.now();e.print(),performance.now()-i>1500&&window.dispatchEvent(new CustomEvent($))}catch{r()}},0),setTimeout(r,12e4),!0}const $="kamra:print-dialog";function h(t){const d=new Date().toLocaleString(c(o()),{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}),n=t.items.map(e=>`<tr><td class="num b" style="width:24px">${Math.round(e.qty)}×</td><td class="b">${s(e.item_name)}</td></tr>`+(e.instructions?`<tr><td></td><td class="ins">» ${s(e.instructions)}</td></tr>`:"")).join("");return`
    <div class="c b lg">${s(t.outlet)}</div>
    <div class="c xl b">${t.kind==="Void"?s(a("*** VOID *** KOT #{number}",{number:String(t.kot_no??"-")})):t.kind==="Test"?s(a("TEST PAGE")):s(a("KOT #{number}",{number:String(t.kot_no??"-")}))}${t.reprint?s(a(" (REPRINT)")):""}</div>
    ${t.station?`<div class="c b">${s(t.station)}</div>`:""}
    ${t.fallback_from?`<div class="c sm">${s(a("for"))} ${s(t.fallback_from)}</div>`:""}
    ${t.nc?`<div class="c b lg">${s(a("*** NC - NO CHARGE ***"))}</div>`+(t.nc_by?`<div class="c sm">${s(a("auth:"))} ${s(t.nc_by)}</div>`:""):""}
    <div class="rule"></div>
    <div class="row"><span class="b lg">${s(a(t.label))}</span><span class="sm">${s(a(t.order_type||""))}</span></div>
    <div class="row sm"><span>${s(t.order)}</span><span>${d}</span></div>
    ${t.customer?`<div class="sm">${s(a("For:"))} ${s(t.customer)}</div>`:""}
    ${t.address?`<div class="sm">→ ${s(t.address)}</div>`:""}
    <div class="rule"></div>
    <table>${n}</table>
    <div class="rule"></div>
    <div class="c sm">${t.items.length} ${s(a("item"))}${t.items.length===1?"":"s"}</div>
    <div class="cut">${s(a("- cut -"))}</div>`}function _(t){return t.join('<div style="break-after:page;page-break-after:always"></div>')}function w(t){const d=new Date().toLocaleString(c(o()),{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}),n=t.items.map(e=>`<tr><td class="num b" style="width:26px">${Math.round(e.qty)}×</td><td class="b">${s(e.item_name)}<div class="sm" style="font-weight:400">${s(a(e.service_type))}</div></td></tr>`).join("");return`
    <div class="c b lg">${s(t.property_name||a("Laundry"))}</div>
    <div class="c xl b">${s(a("LAUNDRY DOCKET"))}</div>
    <div class="rule"></div>
    <div class="row"><span class="b lg">${s(t.room_no)}</span><span class="sm">${s(a(t.order_type||"Guest"))}</span></div>
    <div class="row sm"><span>${s(t.order)}</span><span>${d}</span></div>
    ${t.guest_name?`<div class="sm">${s(t.guest_name)}</div>`:""}
    ${t.express?`<div class="c b">${s(a("EXPRESS - SAME DAY"))}</div>`:""}
    ${t.ready_by?`<div class="sm">${s(a("Ready by:"))} ${s(t.ready_by)}</div>`:""}
    <div class="rule"></div>
    <table>${n}</table>
    <div class="rule"></div>
    <div class="row b lg"><span>${s(a("Total"))}</span><span class="num">${m()}${l(t.total)}</span></div>
    <div class="c sm">${s(a("Counted with the guest. Billed to the room."))}</div>`}function f(t){const d=new Date().toLocaleString(c(o()),{day:"2-digit",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit"}),n=t.table_no?a("Table {n}",{n:String(t.table_no)}):t.room_no?a("Room {n}",{n:String(t.room_no)}):a(t.order_type||"Counter"),e=t.items.map(i=>`<tr><td>${s(i.item_name)}</td><td class="num" style="width:28px">${Math.round(i.qty)}</td><td class="num" style="width:52px">${l(i.rate)}</td><td class="num" style="width:62px">${l(i.amount)}</td></tr>`).join(""),r=(i,u,p="")=>`<div class="row ${p}"><span>${i}</span><span class="num">${m()}${l(u)}</span></div>`;return`
    <div class="c b lg">${s(t.property_name)}</div>
    <div class="c">${s(t.outlet_name)}</div>
    ${t.statutory?`<div class="c b sm">${s(t.statutory.title)}</div><div class="c b sm" dir="rtl">${s(t.statutory.title_ar)}</div>`:""}
    <div class="rule"></div>
    <div class="row"><span class="b">${s(n)}</span><span>${d}</span></div>
    <div class="row sm"><span>${s(a("Bill:"))} ${s(t.order)}</span><span>${s(a("KOT #{number}",{number:String(t.kot_no??"-")}))}</span></div>
    ${t.customer_name||t.customer_phone?`<div class="sm">${s([t.customer_name,t.customer_phone].filter(Boolean).join(" · "))}</div>`:""}
    ${t.delivery_address?`<div class="sm">→ ${s(t.delivery_address)}</div>`:""}
    <div class="rule"></div>
    <table>
      <tr class="sm"><td>${s(a("Item"))}</td><td class="num">${s(a("Qty"))}</td><td class="num">${s(a("Rate"))}</td><td class="num">${s(a("Amt"))}</td></tr>
      ${e}
    </table>
    <div class="rule"></div>
    ${r(s(a("Subtotal")),t.subtotal)}
    ${t.discount_amount?r(s(a("Discount")),-t.discount_amount):""}
    ${(t.tax_parts??[{label:"CGST",rate:t.gst_rate/2,amount:t.cgst},{label:"SGST",rate:t.gst_rate/2,amount:t.sgst}]).map(i=>r(`${s(i.label)} @ ${i.rate}%`,i.amount,"sm")).join("")}
    <div class="rule"></div>
    ${r(s(a("TOTAL")),t.grand_total,"b lg")}
    ${t.nc?`<div class="c b" style="margin-top:4px">${s(a("COMPLIMENTARY - NO CHARGE"))}</div><div class="c sm">${s(a("auth:"))} ${s(t.nc_authorized_by||"-")}${t.nc_note?` · ${s(t.nc_note)}`:""}</div>`:""}
    ${t.paid?`<div class="c b" style="margin-top:4px">${s(a("PAID"))} · ${s(a(t.payment_mode))}</div>`:""}
    <div class="rule"></div>
    ${t.statutory?`<div class="c"><img src="${t.statutory.qr_image}" alt="QR" style="width:120px;height:120px"/></div><div class="c sm">ICV ${t.statutory.icv}</div>`:""}
    <div class="c sm">${s(a("Thank you. See you again."))}</div>
    <div class="cut">${s(a("- cut -"))}</div>`}export{$ as P,f as b,_ as j,h as k,w as l,y as p};
