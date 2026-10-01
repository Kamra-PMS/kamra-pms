"""Kamra's corporate clients used to be a DocType named "Company", the same
global name as ERPNext's core Company - the same clash as the kitchen ledger
(issue #131). On a shared site one definition overwrote the other.

They are now "Corporate Account". This moves Kamra's rows across with their
billing rules, history, attachments and permissions, then hands "Company"
back to ERPNext - or drops it when ERPNext is not installed.

ERPNext companies always carry an abbreviation (mandatory, unique); Kamra's
corporate clients never had that field. That is how the two are told apart.
"""

import frappe

OLD = "Company"
NEW = "Corporate Account"
KAMRA_ONLY_COLUMN = "negotiated_rate_plan"
KAMRA_ROLES = ("Front Desk", "Housekeeping", "Finance", "Revenue Manager",
               "Hotel Admin", "Kamra Agent")

# (doctype, doctype column, name column) for rows that point at a document
REFERENCES = (
	("Version", "ref_doctype", "docname"),
	("Comment", "reference_doctype", "reference_name"),
	("Communication", "reference_doctype", "reference_name"),
	("Activity Log", "reference_doctype", "reference_name"),
	("File", "attached_to_doctype", "attached_to_name"),
	("DocShare", "share_doctype", "share_name"),
	("ToDo", "reference_type", "reference_name"),
	("User Permission", "allow", "for_value"),
)


def execute():
	if not frappe.db.table_exists(OLD) or not frappe.db.has_column(OLD, KAMRA_ONLY_COLUMN):
		return

	erpnext = "erpnext" in frappe.get_installed_apps()
	frappe.reload_doc("kamra", "doctype", "corporate_account")

	if frappe.db.has_column(OLD, "abbr"):
		names = frappe.db.sql_list(f"SELECT name FROM `tab{OLD}` WHERE IFNULL(abbr, '') = ''")  # nosemgrep: frappe-sql-format-injection -- constant
	else:
		names = frappe.db.sql_list(f"SELECT name FROM `tab{OLD}`")  # nosemgrep: frappe-sql-format-injection -- constant

	if names:
		_copy_rows(names)
		_repoint_references(names)

	_move_custom_perms(erpnext)
	_repoint_custom_fields()

	if erpnext:
		if names:
			frappe.db.sql(f"DELETE FROM `tab{OLD}` WHERE name IN %(names)s", {"names": tuple(names)})  # nosemgrep: frappe-sql-format-injection -- constant
		frappe.reload_doc("setup", "doctype", "company", force=True)
	elif frappe.db.get_value("DocType", OLD, "module") == "Kamra":
		frappe.delete_doc("DocType", OLD, force=True, ignore_permissions=True, ignore_missing=True)
		frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{OLD}`")

	frappe.clear_cache(doctype=OLD)
	frappe.clear_cache(doctype=NEW)


def _copy_rows(names):
	cols = sorted(set(frappe.db.get_table_columns(OLD)) & set(frappe.db.get_table_columns(NEW)))
	col_sql = ", ".join(f"`{c}`" for c in cols)
	frappe.db.sql(
		f"INSERT IGNORE INTO `tab{NEW}` ({col_sql}) "  # nosemgrep: frappe-sql-format-injection -- column names come from the schema, not user input
		f"SELECT {col_sql} FROM `tab{OLD}` WHERE name IN %(names)s",
		{"names": tuple(names)},
	)
	copied = frappe.db.count(NEW, {"name": ["in", names]})
	if copied != len(names):
		frappe.throw(f"Only {copied} of {len(names)} corporate accounts copied to {NEW}; {OLD} left untouched.")

	frappe.db.sql(
		"UPDATE `tabCompany Billing Rule` SET parenttype = %s WHERE parenttype = %s AND parent IN %s",
		(NEW, OLD, tuple(names)),
	)


def _repoint_references(names):
	for doctype, dt_col, name_col in REFERENCES:
		if not frappe.db.table_exists(doctype) or not frappe.db.has_column(doctype, dt_col):
			continue
		frappe.db.sql(
			f"UPDATE `tab{doctype}` SET `{dt_col}` = %s WHERE `{dt_col}` = %s AND `{name_col}` IN %s",  # nosemgrep: frappe-sql-format-injection -- identifiers come from the constant REFERENCES
			(NEW, OLD, tuple(names)),
		)


def _move_custom_perms(erpnext):
	"""Custom DocPerms replace a DocType's standard perms wholesale, so they
	travel with the data. On an ERPNext site only Kamra's roles leave Company,
	and only they (plus System Manager) are granted on Corporate Account - an
	ERPNext/HR role like Employee Self Service must not gain corporate clients."""
	for perm in frappe.get_all("Custom DocPerm", filters={"parent": OLD}, pluck="name"):
		doc = frappe.get_doc("Custom DocPerm", perm)
		ours = doc.role in KAMRA_ROLES or doc.role == "System Manager"
		if (not erpnext or ours) and not frappe.db.exists(
				"Custom DocPerm", {"parent": NEW, "role": doc.role, "permlevel": doc.permlevel}):
			new = frappe.copy_doc(doc)
			new.parent = NEW
			new.insert(ignore_permissions=True)
		if not erpnext or doc.role in KAMRA_ROLES:
			frappe.delete_doc("Custom DocPerm", perm, ignore_permissions=True, force=True)


def _repoint_custom_fields():
	"""Custom Fields / Property Setters on Kamra's own DocTypes that linked to
	the old Company. Links on ERPNext DocTypes really mean ERPNext's Company."""
	frappe.db.sql(
		"""UPDATE `tabCustom Field` cf JOIN `tabDocType` d ON d.name = cf.dt
		      SET cf.options = %s
		    WHERE cf.fieldtype = 'Link' AND cf.options = %s AND d.module = 'Kamra'""",
		(NEW, OLD),
	)
	frappe.db.sql(
		"""UPDATE `tabProperty Setter` ps JOIN `tabDocType` d ON d.name = ps.doc_type
		      SET ps.value = %s
		    WHERE ps.property = 'options' AND ps.value = %s AND d.module = 'Kamra'""",
		(NEW, OLD),
	)
