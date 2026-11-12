"""A no-show or late-cancellation fee is paid by the advance the guest left,
but the advance stayed in the Deposit ledger: the folio read settled while
the ledgers showed the money as still held and the fee as still owed. Post
the missing transfer, dated to the day the fee was posted.

Idempotent: kamra.ledger.transfer_advances_to_guest only moves what is
still held for each advance payment."""

import frappe


def execute():
	if not frappe.db.table_exists("Folio Ledger Entry"):
		return
	from kamra.ledger import transfer_advances_to_guest

	# a stay that ended without arriving, with an advance and a fee the
	# policy posted (auto_posted Misc charge) on its folio
	stays = frappe.db.sql(
		"""
		SELECT r.name, MIN(c.posting_date) AS fee_date
		FROM `tabReservation` r
		JOIN `tabFolio` f ON f.reservation = r.name
		JOIN `tabFolio Charge` c ON c.parent = f.name AND c.parenttype = 'Folio'
		WHERE r.status IN ('No Show', 'Cancelled')
		  AND c.auto_posted = 1 AND c.charge_type = 'Misc'
		  AND EXISTS (SELECT 1 FROM `tabFolio Payment` p
		              WHERE p.parent = f.name AND p.parenttype = 'Folio'
		                AND p.payment_kind = 'Advance')
		GROUP BY r.name
		""",
		as_dict=True,
	)
	for stay in stays:
		transfer_advances_to_guest(stay.name, business_date=str(stay.fee_date))
