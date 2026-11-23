# Copyright (c) 2026, Kamra and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ERPNextSyncLog(Document):
	"""What Kamra posted to ERPNext, one row per business date, supplier
	bill or supplier payment: kamra.erpnext_bridge keys on it so nothing
	posts twice."""
