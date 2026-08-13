"""Localization refactor safety net: capture tax/invoice outputs for fixed
inputs. Run BEFORE the seam refactor to write a baseline, AFTER to assert
byte-identical. Usage: capture(<tag>) then compare()."""

import json
import frappe

BASELINE = "/tmp/loc_parity_baseline.json"


def _snapshot():
	from kamra.pricing import quote, room_gst_rate
	P = "Kamra Demo Palace"
	out = {}
	# tax slab at a few nightly rates
	rt = frappe.get_doc("Room Type",
		frappe.db.get_value("Room Type", {"property": P, "room_type_name": "Standard"}, "name"))
	out["slab"] = {str(r): str(room_gst_rate(P, rt, r)) for r in
	               [1000, 5000, 7500, 8000, 15000]}
	# a full quote
	from frappe.utils import add_days, nowdate
	q = quote(P, rt.name, add_days(nowdate(), 10), add_days(nowdate(), 12), 2, 0)
	out["quote"] = {k: str(v) for k, v in q.items()}
	# invoice payload of a closed folio
	from kamra.api import folio_invoice
	f = frappe.db.get_value("Folio", {"property": P, "status": "Closed",
	                                  "invoice_number": ["is", "set"]}, "name")
	if f:
		inv = folio_invoice(f)
		prop = inv["property"]
		out["invoice"] = {k: str(prop.get(k)) for k in
		                  ["sac", "place_of_supply", "gstin", "legal_name"]}
		out["gst_summary"] = json.dumps(inv["gst_summary"], sort_keys=True, default=str)
	return out


def capture():
	with open(BASELINE, "w") as baseline:  # nosemgrep: frappe-security-file-traversal -- path is derived from the app source tree, not from user input
		json.dump(_snapshot(), baseline, sort_keys=True, indent=2)
	print("BASELINE written")


def compare():
	with open(BASELINE) as baseline:  # nosemgrep: frappe-security-file-traversal -- path is derived from the app source tree, not from user input
		before = json.load(baseline)
	after = _snapshot()
	bj = json.dumps(before, sort_keys=True)
	aj = json.dumps(after, sort_keys=True)
	if bj == aj:
		print("PARITY OK - byte identical")
	else:
		print("PARITY DIFF!")
		for k in before:
			if json.dumps(before[k], sort_keys=True) != json.dumps(after.get(k), sort_keys=True):
				print(" DIFF", k, "\n  before:", before[k], "\n  after: ", after.get(k))
