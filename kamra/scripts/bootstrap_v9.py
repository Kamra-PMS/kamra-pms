"""Schema v9 — payments: gateway settings + payment link fields on Folio.

Run via bench console:
    from kamra.scripts.bootstrap_v9 import execute; execute()
"""

import frappe

from kamra.scripts.bootstrap_schema import _dt, f
from kamra.scripts.bootstrap_v5 import add_fields
from kamra.scripts.fix_perms_fields import _grant


def execute():
	_dt("Payment Gateway Settings", [
		f("property", "Link", options="Property", reqd=1, unique=1),
		f("gateway", "Select", options="Razorpay", default="Razorpay",
		  in_list_view=1),
		f("column_break_a", "Column Break"),
		f("enabled", "Check", default="1", in_list_view=1),
		f("test_mode", "Check", in_list_view=1,
		  description="Test mode issues fake links locally — no gateway calls"),
		f("sb_keys", "Section Break", label="API Keys"),
		f("key_id", "Data", label="Key ID"),
		f("column_break_b", "Column Break"),
		f("key_secret", "Password", label="Key Secret"),
		f("webhook_secret", "Password", label="Webhook Secret",
		  description="Set the same secret on the Razorpay webhook for signature checks"),
	], naming_rule="Expression", autoname="format:PGW-{property}")

	for role, grants in {
		"System Manager": (1, 1, 1), "Hotel Admin": (1, 1, 1),
		"Finance": (1, 1, 1), "Front Desk": (1, 0, 0),
	}.items():
		r, w, c = grants
		_grant("Payment Gateway Settings", role, r, w, c,
		       delete=1 if role in ("System Manager", "Hotel Admin") else 0)

	add_fields("Folio", [
		dict(fieldname="payment_link_url", fieldtype="Data",
		     label="Payment Link", read_only=1, insert_after="balance"),
		dict(fieldname="payment_link_id", fieldtype="Data", hidden=1,
		     label="Payment Link ID", insert_after="payment_link_url"),
	])

	frappe.db.commit()
	print("Kamra v9 schema (payments) ready.")
