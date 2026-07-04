"""Schema v1: meal plans, seasons, discount vouchers + booking fields
on Reservation.

Run with:
    bench --site kamra.localhost execute kamra.scripts.bootstrap_v1.execute

Idempotent.
"""

import frappe

from kamra.scripts.bootstrap_schema import _dt, f


def execute():
	# ── Meal Plan (EP/CP/MAP/AP board basis) ─────────────────────────────
	_dt("Meal Plan", [
		f("property", "Link", options="Property", reqd=1),
		f("code", "Select", reqd=1, in_list_view=1,
		  options="EP\nCP\nMAP\nAP",
		  description="EP room only · CP breakfast · MAP breakfast + 1 meal · AP all meals"),
		f("label", "Data", in_list_view=1),
		f("column_break_a", "Column Break"),
		f("price_per_adult", "Currency", in_list_view=1,
		  description="Per adult, per night, added to the room rate"),
		f("price_per_child", "Currency",
		  description="Per paying child, per night"),
		f("is_default", "Check"),
		f("disabled", "Check"),
	], autoname="format:{property}-{code}", naming_rule="Expression",
	   title_field="label")

	# ── Season (named date range that adjusts rates) ─────────────────────
	_dt("Season", [
		f("property", "Link", options="Property", reqd=1),
		f("season_name", "Data", reqd=1, in_list_view=1),
		f("start_date", "Date", reqd=1, in_list_view=1),
		f("end_date", "Date", reqd=1, in_list_view=1,
		  description="Inclusive last night affected"),
		f("column_break_a", "Column Break"),
		f("adjustment_type", "Select", default="Percent",
		  options="Percent\nAmount\nAbsolute",
		  description="Percent uplift, flat amount per night, or absolute nightly rate"),
		f("adjustment_value", "Float", in_list_view=1,
		  description="20 = +20%, or 1000 = +1000/night, or 5000 = flat 5000/night"),
		f("priority", "Int", default="0",
		  description="Higher wins when seasons overlap"),
		f("disabled", "Check"),
	], naming_rule="Expression", autoname="format:SEA-{#####}",
	   title_field="season_name")

	# ── Discount Voucher ─────────────────────────────────────────────────
	_dt("Discount Voucher", [
		f("property", "Link", options="Property", reqd=1),
		f("voucher_code", "Data", reqd=1, in_list_view=1,
		  description="Code the guest types, e.g. WELCOME10"),
		f("column_break_a", "Column Break"),
		f("discount_type", "Select", options="Percent\nAmount",
		  default="Percent", in_list_view=1),
		f("value", "Float", reqd=1, in_list_view=1,
		  description="10 = 10% off, or a flat amount off the pre-tax total"),
		f("sb_rules", "Section Break", label="Rules"),
		f("valid_from", "Date"),
		f("valid_to", "Date"),
		f("min_nights", "Int", default="1"),
		f("column_break_b", "Column Break"),
		f("max_uses", "Int", default="0",
		  description="0 = unlimited"),
		f("times_used", "Int", read_only=1, default="0"),
		f("disabled", "Check"),
	], autoname="format:{property}-{voucher_code}", naming_rule="Expression",
	   title_field="voucher_code")

	# ── Company (corporate account) ──────────────────────────────────────
	_dt("Company", [
		f("company_name", "Data", reqd=1, unique=1, in_list_view=1),
		f("gstin", "Data", label="GSTIN"),
		f("column_break_a", "Column Break"),
		f("contact_name", "Data"),
		f("contact_phone", "Data", options="Phone"),
		f("contact_email", "Data", options="Email"),
		f("sb_terms", "Section Break", label="Commercial Terms"),
		f("negotiated_rate_plan", "Link", options="Rate Plan",
		  description="Applied by default on this company's bookings"),
		f("column_break_b", "Column Break"),
		f("credit_allowed", "Check",
		  description="Bill-to-company (city ledger) permitted"),
		f("disabled", "Check"),
	], autoname="field:company_name", naming_rule="By fieldname")

	# ── Group Booking (parent of N reservations) ─────────────────────────
	_dt("Group Booking", [
		f("property", "Link", options="Property", reqd=1),
		f("group_name", "Data", reqd=1, in_list_view=1),
		f("company", "Link", options="Company",
		  description="Set for corporate groups"),
		f("column_break_a", "Column Break"),
		f("check_in_date", "Date", reqd=1, in_list_view=1),
		f("check_out_date", "Date", reqd=1),
		f("status", "Select", options="Open\nConfirmed\nCancelled",
		  default="Open", in_list_view=1),
		f("notes", "Small Text"),
	], naming_rule="Expression", autoname="format:GRP-{YYYY}-{####}",
	   title_field="group_name")

	# ── New booking fields on Reservation ────────────────────────────────
	add_reservation_fields()

	frappe.db.commit()
	print("Kamra v1 schema (meal plans, seasons, vouchers, groups, corporate) ready.")


def add_reservation_fields():
	dt = frappe.get_doc("DocType", "Reservation")
	existing = {df.fieldname for df in dt.fields}
	new_fields = [
		# inserted after the stay section fields via insert_after chain
		dict(fieldname="booking_type", fieldtype="Select",
		     options="Individual\nGroup\nCorporate", default="Individual",
		     label="Booking Type", insert_after="status"),
		dict(fieldname="company", fieldtype="Link", options="Company",
		     label="Company", depends_on="eval:doc.booking_type=='Corporate'",
		     insert_after="booking_type"),
		dict(fieldname="group_booking", fieldtype="Link",
		     options="Group Booking", label="Group Booking",
		     depends_on="eval:doc.booking_type=='Group'",
		     insert_after="company"),
		dict(fieldname="meal_plan", fieldtype="Link", options="Meal Plan",
		     label="Meal Plan", insert_after="room"),
		dict(fieldname="rate_plan", fieldtype="Link", options="Rate Plan",
		     label="Rate Plan", insert_after="meal_plan"),
		dict(fieldname="voucher", fieldtype="Link", options="Discount Voucher",
		     label="Voucher", insert_after="is_pay_at_hotel"),
		dict(fieldname="discount_amount", fieldtype="Currency",
		     label="Discount", read_only=1, insert_after="voucher"),
		dict(fieldname="auto_price", fieldtype="Check", label="Auto Price",
		     default="1", insert_after="discount_amount",
		     description="Recompute amounts from rates on every save"),
	]
	added = False
	for spec in new_fields:
		if spec["fieldname"] in existing:
			continue
		anchor = spec.pop("insert_after")
		idx = next(
			(i for i, df in enumerate(dt.fields) if df.fieldname == anchor),
			len(dt.fields) - 1,
		)
		dt.fields.insert(idx + 1, frappe.get_doc(
			{"doctype": "DocField", **spec}
		))
		added = True
		print(f"Reservation: added field {spec['fieldname']}")
	if added:
		for i, df in enumerate(dt.fields):
			df.idx = i + 1
		dt.save(ignore_permissions=True)
