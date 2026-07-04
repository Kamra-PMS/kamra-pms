"""Schema v5 — eZee-parity billing correctness:

- Property: GST slab config (auto 5%/18% by nightly rate) + tax-inclusive mode
- Reservation: day-use flag
- Guest: blacklist flag + reason
- Folio: folio_type (Guest/Extra/Company), multiple folios per reservation

Run via bench console:
    from kamra.scripts.bootstrap_v5 import execute; execute()
"""

import frappe


def add_fields(doctype: str, specs: list[dict]):
	dt = frappe.get_doc("DocType", doctype)
	existing = {df.fieldname for df in dt.fields}
	changed = False
	for spec in specs:
		spec = dict(spec)
		anchor = spec.pop("insert_after")
		if spec["fieldname"] in existing:
			continue
		row = dt.append("fields", spec)
		fields = list(dt.fields)
		fields.remove(row)
		idx = next(
			(i for i, df in enumerate(fields) if df.fieldname == anchor),
			len(fields) - 1,
		)
		fields.insert(idx + 1, row)
		for i, df in enumerate(fields):
			df.idx = i + 1
		dt.fields = fields
		changed = True
		print(f"{doctype}: appended {spec['fieldname']}")
	if changed:
		dt.save(ignore_permissions=True)


def execute():
	add_fields("Property", [
		dict(fieldname="sb_gst", fieldtype="Section Break", label="GST Rules",
		     insert_after="gstin"),
		dict(fieldname="gst_mode", fieldtype="Select", label="Room GST Mode",
		     options="Slab\nFixed", default="Slab", insert_after="sb_gst",
		     description="Slab: rate decides GST (India). Fixed: use the room type's tax_percent."),
		dict(fieldname="gst_slab_threshold", fieldtype="Currency",
		     label="Slab Threshold (₹/night)", default="7500",
		     insert_after="gst_mode"),
		dict(fieldname="gst_rate_low", fieldtype="Percent",
		     label="GST at/below threshold", default="5",
		     insert_after="gst_slab_threshold"),
		dict(fieldname="gst_rate_high", fieldtype="Percent",
		     label="GST above threshold", default="18",
		     insert_after="gst_rate_low"),
		dict(fieldname="rates_include_tax", fieldtype="Check",
		     label="Rates Include Tax",
		     insert_after="gst_rate_high",
		     description="On: configured room prices are tax-inclusive; the engine back-computes the taxable value."),
	])

	add_fields("Reservation", [
		dict(fieldname="is_day_use", fieldtype="Check", label="Day Use",
		     insert_after="nights",
		     description="Same-day stay: check-out date equals check-in date."),
	])

	add_fields("Guest", [
		dict(fieldname="blacklisted", fieldtype="Check", label="Blacklisted",
		     insert_after="vip"),
		dict(fieldname="blacklist_reason", fieldtype="Small Text",
		     label="Blacklist Reason", insert_after="blacklisted",
		     depends_on="eval:doc.blacklisted"),
	])

	add_fields("Folio", [
		dict(fieldname="folio_type", fieldtype="Select", label="Folio Type",
		     options="Guest\nExtra\nCompany", default="Guest",
		     insert_after="status"),
	])

	# multiple folios per reservation: drop the unique constraint
	dt = frappe.get_doc("DocType", "Folio")
	res_field = next(df for df in dt.fields if df.fieldname == "reservation")
	if res_field.unique:
		res_field.unique = 0
		dt.save(ignore_permissions=True)
		print("Folio.reservation: unique constraint removed")
		try:
			frappe.db.sql_ddl("ALTER TABLE `tabFolio` DROP INDEX reservation")
		except Exception:
			pass

	frappe.db.commit()
	print("Kamra v5 schema ready.")
