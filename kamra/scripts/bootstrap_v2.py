"""Schema v2: Folio (with charge/payment child tables) and Night Audit Run.

Run via bench console:
    from kamra.scripts.bootstrap_v2 import execute; execute()

Idempotent.
"""

import frappe

from kamra.scripts.bootstrap_schema import f

MODULE = "Kamra"


def _dt(name, fields, *, istable=0, autoname=None, naming_rule=None,
        title_field=None, extra=None):
	if frappe.db.exists("DocType", name):
		print(f"skip (exists): {name}")
		return
	doc = frappe.get_doc({
		"doctype": "DocType",
		"name": name,
		"module": MODULE,
		"istable": istable,
		"track_changes": 0 if istable else 1,
		"autoname": autoname,
		"naming_rule": naming_rule,
		"title_field": title_field,
		"engine": "InnoDB",
		"fields": fields,
		"permissions": [] if istable else [
			{"role": "System Manager", "read": 1, "write": 1, "create": 1,
			 "delete": 1, "report": 1, "export": 1, "print": 1, "email": 1},
		],
		**(extra or {}),
	})
	doc.insert(ignore_permissions=True)
	print(f"created: {name}")


CHARGE_TYPES = (
	"Room\nMeal Plan\nFood & Beverage\nMinibar\nLaundry\nSpa\n"
	"Early Check-in\nLate Checkout\nDiscount\nMisc"
)

PAYMENT_MODES = "Cash\nCard\nUPI\nBank Transfer\nOTA Prepaid\nCompany Credit\nPayment Link"


def execute():
	# ── Folio Charge (child) ─────────────────────────────────────────────
	_dt("Folio Charge", [
		f("posting_date", "Date", reqd=1, in_list_view=1),
		f("charge_type", "Select", options=CHARGE_TYPES, reqd=1,
		  in_list_view=1),
		f("description", "Data", in_list_view=1),
		f("qty", "Float", default="1"),
		f("rate", "Currency"),
		f("amount", "Currency", reqd=1, in_list_view=1,
		  description="Pre-tax line amount (can be negative for discounts)"),
		f("gst_rate", "Percent", label="GST %", in_list_view=1),
		f("gst_amount", "Currency", read_only=1),
		f("total", "Currency", read_only=1, in_list_view=1),
		f("auto_posted", "Check", read_only=1,
		  description="Posted by night audit / checkout automation"),
	], istable=1)

	# ── Folio Payment (child) ────────────────────────────────────────────
	_dt("Folio Payment", [
		f("posting_date", "Date", reqd=1, in_list_view=1),
		f("mode", "Select", options=PAYMENT_MODES, reqd=1, in_list_view=1),
		f("amount", "Currency", reqd=1, in_list_view=1),
		f("reference", "Data", in_list_view=1,
		  description="Txn id / card last-4 / UPI ref"),
	], istable=1)

	# ── Folio ────────────────────────────────────────────────────────────
	_dt("Folio", [
		f("property", "Link", options="Property", reqd=1),
		f("reservation", "Link", options="Reservation", reqd=1, unique=1),
		f("guest", "Link", options="Guest", reqd=1),
		f("guest_name", "Data", fetch_from="guest.full_name", read_only=1,
		  in_list_view=1),
		f("column_break_a", "Column Break"),
		f("status", "Select", options="Open\nClosed", default="Open",
		  in_list_view=1, in_standard_filter=1),
		f("opened_on", "Datetime", read_only=1),
		f("closed_on", "Datetime", read_only=1),
		f("invoice_number", "Data", read_only=1, in_list_view=1,
		  description="Assigned when the folio is closed"),
		f("sb_charges", "Section Break", label="Charges"),
		f("charges", "Table", options="Folio Charge"),
		f("sb_payments", "Section Break", label="Payments"),
		f("payments", "Table", options="Folio Payment"),
		f("sb_totals", "Section Break", label="Totals"),
		f("charges_total", "Currency", read_only=1,
		  description="Pre-tax including discounts"),
		f("tax_total", "Currency", read_only=1),
		f("column_break_b", "Column Break"),
		f("grand_total", "Currency", read_only=1),
		f("payments_total", "Currency", read_only=1),
		f("balance", "Currency", read_only=1, in_list_view=1),
	], naming_rule="Expression", autoname="format:FOLIO-{YYYY}-{#####}",
	   title_field="guest_name")

	# ── Night Audit Run ──────────────────────────────────────────────────
	_dt("Night Audit Run", [
		f("property", "Link", options="Property", reqd=1),
		f("business_date", "Date", reqd=1, in_list_view=1),
		f("status", "Select", options="Completed\nCompleted with Warnings",
		  default="Completed", in_list_view=1),
		f("column_break_a", "Column Break"),
		f("room_charges_posted", "Int", read_only=1, in_list_view=1),
		f("amount_posted", "Currency", read_only=1),
		f("no_shows_flagged", "Int", read_only=1),
		f("folios_opened", "Int", read_only=1),
		f("sb_log", "Section Break", label="Log"),
		f("log", "Small Text", read_only=1),
	], naming_rule="Expression", autoname="format:AUDIT-{business_date}")

	frappe.db.commit()
	print("Kamra v2 schema (folio, night audit) ready.")
