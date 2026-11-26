# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class POSOutlet(Document):
	def validate(self):
		if self.logo and not _is_safe_logo(self.logo):
			frappe.throw(_("The receipt logo must be an uploaded file or an https link."))
		percent = float(self.levy_percent or 0)
		if percent < 0 or percent > 100:
			frappe.throw(_("The levy must be between 0 and 100%."))
		if percent > 0 and self.property and _issues_pos_invoices(self.property):
			frappe.throw(_(
				"The levy is not available while this property's e-invoicing is on: "
				"the e-invoice is built from the item lines and would not include it."))


def _is_safe_logo(url: str) -> bool:
	"""Only an uploaded file or an https link may be the receipt logo. A javascript: or data: URL,
	a plain http one, a protocol-relative one or a path with .. in it is refused. The bill renderer
	applies the same rule (logoSrc in frontend/src/lib/thermal.ts)."""
	from urllib.parse import unquote

	url = url.strip()
	# check the decoded path too, so /files/%2e%2e/x cannot step out of /files/
	decoded = unquote(url)
	return (url.startswith(("/files/", "/private/files/", "https://"))
	        and not any(c in url for c in ' "\'<>\\')
	        and ".." not in url.split("/") and ".." not in decoded.split("/"))


def _issues_pos_invoices(property: str) -> bool:
	"""True where the country pack e-invoices every POS bill it settles (Saudi
	Arabia's ZATCA). That invoice is built from the item lines and the
	discount only, so a levy would make the invoice, its QR and the amount the
	guest paid disagree. Until the pack takes the levy line, an outlet there
	cannot set one."""
	from kamra import localization as loc

	return hasattr(loc.pack_for(property), "on_pos_bill_paid")
