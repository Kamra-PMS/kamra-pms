# Copyright (c) 2026, Kamra and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class CashTransfer(Document):
	def validate(self):
		# cashier owns the safe balance. Imported here so that module does
		# not load this controller at import time (it inserts by doctype name).
		from kamra.cashier import assert_transfer_keeps_safe_solvent
		assert_transfer_keeps_safe_solvent(self)
