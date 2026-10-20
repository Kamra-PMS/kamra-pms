"""Kitchen printers - where a KOT prints, whoever punched it.

A property lists its printers (Settings > F&B > Kitchen printers) and, for
each one, the outlets and stations it prints KOTs for. Firing a KOT splits
the round by station and queues one Print Job per printer that serves it,
so two restaurants can share one kitchen printer, and the bar's drinks
print at the bar.

Two ways a job reaches paper:

  Print station  a kitchen display screen, set to print for a printer,
                 claims that printer's jobs and prints them to the printer
                 attached to its own device. Works with any printer and any
                 hosting: the browser connects out to Kamra.
  Direct IP      the Kamra server sends ESC/POS straight to the printer's
                 address (port 9100). Only when Kamra runs on the hotel's
                 own network - a cloud server can't reach 192.168.x.x.

No printers configured means nothing changes: the till prints as before.
Lines no printer serves are handed back to the till to print itself.
"""

import json
import socket

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime

from kamra.authz import assert_property_access, require_roles

# Kitchen screens and tills run as these roles; they claim and ack jobs.
STATION_ROLES = ("Front Desk", "Finance", "Kamra Agent")
# Who may add, change and remove printers (admins always may) - the F&B
# settings editors.
EDITOR_ROLES = ("Finance",)
# A claimed job with no answer after this long is offered again.
STALE_CLAIM_S = 60
# A print station that hasn't asked for work in this long shows as offline.
ONLINE_S = 30
KEEP_DAYS = 7


# --- routing ------------------------------------------------------------------

def _printers(property: str) -> list[dict]:
	rows = frappe.get_all(
		"Kitchen Printer", filters={"property": property, "disabled": 0},
		fields=["name", "printer_name", "connection", "copies", "fallback_printer"])
	if not rows:
		return []
	routes = frappe.get_all(
		"Kitchen Printer Route", filters={"parent": ["in", [r.name for r in rows]],
		                                  "parenttype": "Kitchen Printer"},
		fields=["parent", "outlet", "prep_station"])
	by_printer: dict[str, list] = {}
	for r in routes:
		by_printer.setdefault(r.parent, []).append((r.outlet, r.prep_station or ""))
	for r in rows:
		r["routes"] = by_printer.get(r.name, [])
	return rows


def _serves(printer: dict, outlet: str, station: str) -> bool:
	return any(o == outlet and (not s or s == station) for o, s in printer["routes"])


def route_kot(doc, rows, ticket: dict, kind: str = "KOT") -> dict:
	"""Queue this round's KOT on every printer that serves its outlet and
	stations. `rows` are the POS Order Item rows just fired (or voided);
	`ticket` is the till's ticket for the whole round. Returns the jobs and
	the lines no printer took, which the till prints itself."""
	printers = _printers(doc.property)
	lines = [{"item_name": it.item_name, "qty": it.qty,
	          "instructions": it.instructions, "menu_item": it.menu_item} for it in rows]
	if not printers or not lines:
		return {"jobs": [], "unrouted": [_strip(ln) for ln in lines]}
	stations = dict(frappe.get_all(
		"Menu Item", filters={"name": ["in", list({ln["menu_item"] for ln in lines})]},
		fields=["name", "prep_station"], as_list=True))
	outlet_name = frappe.db.get_value("POS Outlet", doc.outlet, "outlet_name") or doc.outlet

	per_printer: dict[str, dict] = {}
	unrouted = []
	for ln in lines:
		station = stations.get(ln["menu_item"]) or "Kitchen"
		hit = [p for p in printers if _serves(p, doc.outlet, station)]
		if not hit:
			unrouted.append(_strip(ln))
		for p in hit:
			slot = per_printer.setdefault(p["name"], {"printer": p, "items": [], "stations": set()})
			slot["items"].append(_strip(ln))
			slot["stations"].add(station)

	jobs = []
	for slot in per_printer.values():
		p = slot["printer"]
		payload = dict(ticket, items=slot["items"], outlet=outlet_name,
		               station=", ".join(sorted(slot["stations"])), kind=kind,
		               copies=int(p.get("copies") or 1))
		job = _queue(doc.property, p, kind, payload, order=doc.name,
		             outlet=doc.outlet, kot_no=doc.kot_no)
		jobs.append({"job": job, "printer": p["name"], "printer_name": p["printer_name"],
		             "items": len(slot["items"])})
	return {"jobs": jobs, "unrouted": unrouted}


def _strip(ln: dict) -> dict:
	return {"item_name": ln["item_name"], "qty": ln["qty"], "instructions": ln.get("instructions")}


def _queue(property: str, printer: dict, kind: str, payload: dict, order=None,
           outlet=None, kot_no=None) -> str:
	job = frappe.get_doc({
		"doctype": "Print Job", "property": property, "printer": printer["name"],
		"kind": kind, "status": "Queued", "pos_order": order, "outlet": outlet,
		"kot_no": kot_no, "payload": frappe.as_json(payload),
	}).insert(ignore_permissions=True)
	if printer.get("connection") == "Direct IP":
		frappe.enqueue("kamra.printing.print_direct", queue="short", job=job.name,
		               enqueue_after_commit=True)
	else:
		frappe.publish_realtime(  # nosemgrep: frappe-realtime-pick-room -- carries only a printer id; every print-station screen filters for its own printer, as realtime.notify does for change pings
			"kamra_print", {"printer": printer["name"]}, after_commit=True)
	return job.name


def void_slip(doc, rows) -> list:
	"""A line voided after it was fired: tell the printer that had the KOT,
	so the kitchen stops cooking it. Off with the F&B setting."""
	from kamra.settings import get_setting
	if not int(get_setting(doc.property, "pos_print_void_slips") or 0):
		return []
	from kamra.pos import _label
	ticket = {"kot_no": doc.kot_no, "at": str(now_datetime()), "label": _label(doc.as_dict()),
	          "order_type": doc.order_type, "order": doc.name, "void": True,
	          "nc": bool(doc.nc), "customer": doc.customer_name, "address": doc.delivery_address}
	out = route_kot(doc, rows, ticket, kind="Void")
	return out["jobs"]


# --- print stations -------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
@require_roles(*STATION_ROLES)
def claim_jobs(printer: str) -> list:
	"""A print station asks for its printer's work. Hands over every queued
	job (and any claimed one nobody confirmed within a minute) and marks
	them Printing. The station prints them and calls ack_jobs."""
	p = frappe.db.get_value("Kitchen Printer", printer,
	                        ["property", "connection", "disabled"], as_dict=True)
	if not p:
		frappe.throw(_("Unknown printer."))
	assert_property_access(p.property)
	if p.connection != "Print station":
		frappe.throw(_("This printer is not a print station."))
	now = now_datetime()
	stale = add_to_date(now, seconds=-STALE_CLAIM_S)
	names = frappe.db.sql(
		"""select name from `tabPrint Job`
		   where printer=%s and (status='Queued' or (status='Printing' and claimed_at < %s))
		   order by creation limit 20 for update""", (printer, stale), pluck=True)
	jobs = []
	for name in names:
		frappe.db.set_value("Print Job", name, {"status": "Printing", "claimed_at": now},
		                    update_modified=False)
		frappe.db.sql("update `tabPrint Job` set attempts = attempts + 1 where name=%s", name)
		payload = frappe.db.get_value("Print Job", name, ["kind", "payload"], as_dict=True)
		jobs.append({"job": name, "kind": payload.kind, "ticket": json.loads(payload.payload or "{}")})
	frappe.db.set_value("Kitchen Printer", printer, "last_seen", now, update_modified=False)
	return jobs


@frappe.whitelist(methods=["POST"])
@require_roles(*STATION_ROLES)
def ack_jobs(printer: str, printed=None, failed=None, error: str | None = None) -> dict:
	"""The station's answer. Printed jobs are done; failed ones move to the
	printer's fallback, or stay Failed for a reprint."""
	printed = frappe.parse_json(printed) if isinstance(printed, str) else (printed or [])
	failed = frappe.parse_json(failed) if isinstance(failed, str) else (failed or [])
	prop = frappe.db.get_value("Kitchen Printer", printer, "property")
	if not prop:
		frappe.throw(_("Unknown printer."))
	assert_property_access(prop)
	now = now_datetime()
	for name in printed:
		if frappe.db.get_value("Print Job", name, "printer") == printer:
			frappe.db.set_value("Print Job", name, {"status": "Printed", "printed_at": now,
			                                        "error": None}, update_modified=False)
	if printed:
		frappe.db.set_value("Kitchen Printer", printer, {"last_printed": now, "last_error": None},
		                    update_modified=False)
	for name in failed:
		if frappe.db.get_value("Print Job", name, "printer") == printer:
			_fail(name, error or _("The print station could not print."))
	return {"ok": True}


def _fail(job: str, error: str):
	"""Mark a job failed; hand it to the printer's fallback if there is one."""
	j = frappe.get_doc("Print Job", job)
	frappe.db.set_value("Kitchen Printer", j.printer, "last_error", error[:500],
	                    update_modified=False)
	fallback = frappe.db.get_value("Kitchen Printer", j.printer, "fallback_printer")
	if fallback and fallback != j.printer and not frappe.db.get_value(
			"Kitchen Printer", fallback, "disabled"):
		fb = frappe.db.get_value("Kitchen Printer", fallback,
		                         ["name", "connection", "copies"], as_dict=True)
		payload = json.loads(j.payload or "{}")
		payload["fallback_from"] = frappe.db.get_value("Kitchen Printer", j.printer, "printer_name")
		_queue(j.property, fb, j.kind, payload, order=j.pos_order, outlet=j.outlet, kot_no=j.kot_no)
		error = f"{error} - sent to {fb.name}"
	frappe.db.set_value("Print Job", job, {"status": "Failed", "error": error[:500]},
	                    update_modified=False)


# --- direct IP (on-site Kamra only) ----------------------------------------------

ESC, GS = b"\x1b", b"\x1d"


def escpos(ticket: dict, width_mm: str = "80 mm") -> bytes:
	"""A KOT as ESC/POS bytes for a plain network thermal printer."""
	cols = 32 if str(width_mm).startswith("58") else 48
	out = [ESC + b"@"]  # reset

	def line(text="", big=False, bold=False, center=False):
		out.append(ESC + b"a" + (b"\x01" if center else b"\x00"))
		out.append(GS + b"!" + (b"\x11" if big else b"\x00"))
		out.append(ESC + b"E" + (b"\x01" if bold else b"\x00"))
		out.append(str(text).encode("ascii", "replace") + b"\n")

	kind = ticket.get("kind") or "KOT"
	head = "VOID" if kind == "Void" else ("TEST PAGE" if kind == "Test" else
	                                      f"KOT {ticket.get('kot_no') or ''}".strip())
	if kind == "Reprint" or ticket.get("reprint"):
		head += " REPRINT"
	line(ticket.get("outlet") or "", big=True, bold=True, center=True)
	line(head, big=True, bold=True, center=True)
	if ticket.get("station"):
		line(ticket["station"], center=True)
	if ticket.get("label"):
		line(ticket["label"], bold=True)
	if ticket.get("customer"):
		line(ticket["customer"])
	if ticket.get("address"):
		line(ticket["address"])
	if ticket.get("nc"):
		line("NC - NO CHARGE", bold=True)
	if ticket.get("fallback_from"):
		line(f"(for {ticket['fallback_from']})")
	line(str(ticket.get("at") or "")[:16])
	line("-" * cols)
	for it in ticket.get("items") or []:
		qty = f"{float(it.get('qty') or 0):g}"
		name = str(it.get("item_name") or "")
		line(f"{qty:>3} {name}"[:cols], big=True, bold=True)
		if it.get("instructions"):
			line(f"    > {it['instructions']}"[:cols], bold=True)
	line("-" * cols)
	out.append(b"\n\n\n" + GS + b"V\x41\x03")  # feed and partial cut
	return b"".join(out)


def print_direct(job: str):
	"""Background job: send one Print Job to a Direct IP printer."""
	j = frappe.get_doc("Print Job", job)
	if j.status == "Printed":
		return
	p = frappe.db.get_value("Kitchen Printer", j.printer,
	                        ["ip_address", "port", "paper_width", "copies"], as_dict=True)
	ticket = json.loads(j.payload or "{}")
	data = escpos(ticket, p.paper_width) * max(1, int(p.copies or 1))
	frappe.db.set_value("Print Job", job, {"status": "Printing", "claimed_at": now_datetime(),
	                                       "attempts": (j.attempts or 0) + 1}, update_modified=False)
	try:
		with socket.create_connection((p.ip_address, int(p.port or 9100)), timeout=5) as s:
			s.sendall(data)
	except Exception as e:
		_fail(job, f"{p.ip_address}:{p.port or 9100} - {e}")
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- background job (print_direct / daily purge) runs outside a request; its result must persist
		return
	now = now_datetime()
	frappe.db.set_value("Print Job", job, {"status": "Printed", "printed_at": now, "error": None},
	                    update_modified=False)
	frappe.db.set_value("Kitchen Printer", j.printer, {"last_printed": now, "last_seen": now,
	                                                 "last_error": None}, update_modified=False)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- background job (print_direct / daily purge) runs outside a request; its result must persist


# --- settings endpoints -----------------------------------------------------------

def _check_property(property: str):
	assert_property_access(property)
	if not frappe.db.exists("Property", property):
		frappe.throw(_("Unknown property."))


@frappe.whitelist()
@require_roles(*STATION_ROLES)
def printers(property: str) -> list:
	"""Every printer with its routes and whether it's online - for the
	settings card and for a kitchen screen choosing what to print for."""
	_check_property(property)
	rows = frappe.get_all(
		"Kitchen Printer", filters={"property": property},
		fields=["name", "printer_name", "connection", "paper_width", "copies", "ip_address",
		        "port", "fallback_printer", "disabled", "last_seen", "last_printed", "last_error"],
		order_by="printer_name")
	routes = frappe.get_all(
		"Kitchen Printer Route", filters={"parent": ["in", [r.name for r in rows] or [""]],
		                                  "parenttype": "Kitchen Printer"},
		fields=["parent", "outlet", "prep_station"], order_by="idx")
	queued = dict(frappe.db.sql(
		"""select printer, count(*) from `tabPrint Job`
		   where property=%s and status in ('Queued', 'Printing') group by printer""",
		property))
	failed = dict(frappe.db.sql(
		"""select printer, count(*) from `tabPrint Job`
		   where property=%s and status='Failed' and creation > %s group by printer""",
		(property, add_to_date(now_datetime(), days=-1))))
	cutoff = add_to_date(now_datetime(), seconds=-ONLINE_S)
	for r in rows:
		r["routes"] = [{"outlet": x.outlet, "prep_station": x.prep_station or ""}
		               for x in routes if x.parent == r.name]
		r["queued"] = queued.get(r.name, 0)
		r["failed_today"] = failed.get(r.name, 0)
		r["online"] = bool(r.last_seen and r.last_seen >= cutoff) \
			if r.connection == "Print station" else None
	return rows


@frappe.whitelist(methods=["POST"])
@require_roles(*EDITOR_ROLES)
def save_printer(property: str, printer: dict | str, name: str | None = None) -> dict:
	"""Add or change a printer and its routes. Logged to the Activity log."""
	_check_property(property)
	data = frappe.parse_json(printer) if isinstance(printer, str) else (printer or {})
	if not (data.get("printer_name") or "").strip():
		frappe.throw(_("Give the printer a name."))
	conn = data.get("connection") or "Print station"
	if conn not in ("Print station", "Direct IP"):
		frappe.throw(_("Unknown connection type."))
	if conn == "Direct IP" and not (data.get("ip_address") or "").strip():
		frappe.throw(_("A Direct IP printer needs its IP address."))
	outlets = set(frappe.get_all("POS Outlet", filters={"property": property}, pluck="name"))
	routes = []
	for r in data.get("routes") or []:
		if r.get("outlet") not in outlets:
			frappe.throw(_("Outlet {0} is not at this property.").format(r.get("outlet")))
		routes.append({"outlet": r["outlet"], "prep_station": r.get("prep_station") or ""})
	taken = frappe.db.get_value("Kitchen Printer", {"property": property,
	                                               "printer_name": data["printer_name"].strip()})
	if taken and taken != name:
		frappe.throw(_("There's already a printer called {0}.").format(data["printer_name"].strip()))
	fallback = data.get("fallback_printer") or None
	if fallback and frappe.db.get_value("Kitchen Printer", fallback, "property") != property:
		frappe.throw(_("The fallback printer must be at this property."))

	fields = {
		"printer_name": data["printer_name"].strip(), "connection": conn,
		"paper_width": data.get("paper_width") or "80 mm",
		"copies": min(max(int(data.get("copies") or 1), 1), 3),
		"ip_address": (data.get("ip_address") or "").strip() or None,
		"port": int(data.get("port") or 9100),
		"fallback_printer": fallback, "disabled": 1 if data.get("disabled") else 0,
	}
	if name:
		doc = frappe.get_doc("Kitchen Printer", name)
		if doc.property != property:
			frappe.throw(_("That printer is not at this property."))
		if fallback == doc.name:
			frappe.throw(_("A printer can't be its own fallback."))
		doc.update(fields)
		doc.set("routes", routes)
		doc.save(ignore_permissions=True)  # role checked above
	else:
		doc = frappe.get_doc(dict(fields, doctype="Kitchen Printer", property=property,
		                          routes=routes)).insert(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("printer_saved", reference_doctype="Kitchen Printer", reference_name=doc.name,
	           property=property, rationale=f"Kitchen printer {doc.printer_name} saved")
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
@require_roles(*EDITOR_ROLES)
def delete_printer(name: str) -> dict:
	prop = frappe.db.get_value("Kitchen Printer", name, "property")
	if not prop:
		frappe.throw(_("Unknown printer."))
	_check_property(prop)
	frappe.db.set_value("Kitchen Printer", {"fallback_printer": name}, "fallback_printer", None)
	frappe.db.delete("Print Job", {"printer": name, "status": ["in", ["Queued", "Printing"]]})
	frappe.delete_doc("Kitchen Printer", name, ignore_permissions=True, force=True)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@require_roles(*EDITOR_ROLES)
def test_print(name: str) -> dict:
	"""Queue a test page on one printer."""
	p = frappe.db.get_value("Kitchen Printer", name,
	                        ["name", "property", "printer_name", "connection", "copies"], as_dict=True)
	if not p:
		frappe.throw(_("Unknown printer."))
	_check_property(p.property)
	ticket = {"kind": "Test", "outlet": p.printer_name, "label": _("Test page"),
	          "at": str(now_datetime()), "station": p.connection, "copies": 1,
	          "items": [{"item_name": _("If you can read this, the printer works"), "qty": 1}]}
	job = _queue(p.property, dict(p, copies=1), "Test", ticket)
	return {"ok": True, "job": job}


@frappe.whitelist(methods=["POST"])
@require_roles(*STATION_ROLES)
def reprint(job: str, printer: str | None = None) -> dict:
	"""Print a job again - on its own printer or another one."""
	j = frappe.get_doc("Print Job", job)
	assert_property_access(j.property)
	target = printer or j.printer
	p = frappe.db.get_value("Kitchen Printer", target, ["name", "property", "connection", "copies"],
	                        as_dict=True)
	if not p or p.property != j.property:
		frappe.throw(_("Unknown printer."))
	payload = json.loads(j.payload or "{}")
	payload["reprint"] = True
	return {"ok": True, "job": _queue(j.property, p, "Reprint", payload, order=j.pos_order,
	                                  outlet=j.outlet, kot_no=j.kot_no)}


@frappe.whitelist()
@require_roles(*STATION_ROLES)
def order_print_status(order: str) -> list:
	"""Where an order's tickets went and whether they printed - for the till."""
	prop = frappe.db.get_value("POS Order", order, "property")
	if not prop:
		frappe.throw(_("Unknown order."))
	assert_property_access(prop)
	return frappe.db.sql(
		"""select j.name as job, j.kind, j.status, j.kot_no, j.error, j.printer,
		          p.printer_name, j.creation
		   from `tabPrint Job` j left join `tabKitchen Printer` p on p.name = j.printer
		   where j.pos_order=%s order by j.creation desc limit 30""", order, as_dict=True)


def purge_old_jobs():
	"""Daily: finished print jobs carry guest names and addresses on the
	ticket - keep a week for reprints and disputes, then drop them."""
	frappe.db.delete("Print Job", {
		"status": ["in", ["Printed", "Failed"]],
		"creation": ["<", add_to_date(now_datetime(), days=-KEEP_DAYS)]})
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- background job (print_direct / daily purge) runs outside a request; its result must persist
