import frappe


def execute():
	"""Ensure hotel properties get a default Turnover Profile (inspection off)."""
	if not frappe.db.exists("DocType", "Turnover Profile"):
		return
	from kamra.turnover import ensure_default_profile

	for name in frappe.get_all("Property", pluck="name"):
		kind = frappe.db.get_value("Property", name, "property_kind") or "Hotel"
		ensure_default_profile(name, str_defaults=(kind == "Short Term Rental"))
	frappe.clear_cache()
