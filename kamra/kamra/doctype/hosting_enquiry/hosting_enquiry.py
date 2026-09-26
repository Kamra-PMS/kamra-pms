# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class HostingEnquiry(Document):
	"""Lead from kamrapms.com (and similar). System Manager only.

	Personal data (name, email, phone) is deleted after
	``hosting_enquiry_retention_months`` (default 24) unless status is Won.
	See ``kamra.hosting_enquiry_retention``.
	"""

	pass
