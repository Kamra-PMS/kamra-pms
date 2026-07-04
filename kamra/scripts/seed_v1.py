"""Seed v1 demo data: meal plans, a season, vouchers, a corporate account.

Run with:
    bench --site kamra.localhost execute kamra.scripts.seed_v1.execute

Idempotent.
"""

import frappe
from frappe.utils import add_days, nowdate

PROPERTY = "Kamra Demo Palace"


def upsert(doctype, keys, values):
	name = frappe.db.exists(doctype, keys)
	if name:
		return name
	doc = frappe.get_doc({"doctype": doctype, **keys, **values})
	doc.insert(ignore_permissions=True)
	print(f"created {doctype}: {doc.name}")
	return doc.name


def execute():
	if not frappe.db.exists("Property", PROPERTY):
		print("Run seed_demo first.")
		return

	# Meal plans
	upsert("Meal Plan", {"property": PROPERTY, "code": "EP"},
	       {"label": "Room Only", "price_per_adult": 0, "price_per_child": 0})
	upsert("Meal Plan", {"property": PROPERTY, "code": "CP"},
	       {"label": "Breakfast Included", "price_per_adult": 350,
	        "price_per_child": 200, "is_default": 1})
	upsert("Meal Plan", {"property": PROPERTY, "code": "MAP"},
	       {"label": "Breakfast + Dinner", "price_per_adult": 800,
	        "price_per_child": 450})

	# A season covering the next two weekends (visible in the calendar)
	upsert("Season", {"property": PROPERTY, "season_name": "Summer Peak"},
	       {"start_date": add_days(nowdate(), 4),
	        "end_date": add_days(nowdate(), 8),
	        "adjustment_type": "Percent", "adjustment_value": 20,
	        "priority": 10})

	# Vouchers
	upsert("Discount Voucher", {"property": PROPERTY, "voucher_code": "WELCOME10"},
	       {"discount_type": "Percent", "value": 10, "min_nights": 1,
	        "max_uses": 100, "valid_to": add_days(nowdate(), 90)})
	upsert("Discount Voucher", {"property": PROPERTY, "voucher_code": "LONGSTAY500"},
	       {"discount_type": "Amount", "value": 500, "min_nights": 3,
	        "max_uses": 0})

	# Corporate account
	upsert("Company", {"company_name": "Rock8 Technologies"},
	       {"gstin": "29AAViCR1234A1Z1", "contact_name": "Priya Nair",
	        "contact_email": "travel@rock8.ai", "credit_allowed": 1})

	frappe.db.commit()
	print("v1 demo data ready.")
