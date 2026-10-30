"""Every property gets a short code for its allowance voucher series:
its initials, with a digit added where two properties share them
(oldest property keeps the plain initials)."""

import frappe


def execute():
	frappe.reload_doc("kamra", "doctype", "property")
	from kamra.kamra.doctype.property.property import default_short_code
	for p in frappe.get_all("Property", filters={"short_code": ("is", "not set")},
	                        fields=["name", "property_name"], order_by="creation asc"):
		frappe.db.set_value("Property", p.name, "short_code",
		                    default_short_code(p.property_name or p.name, exclude=p.name),
		                    update_modified=False)
