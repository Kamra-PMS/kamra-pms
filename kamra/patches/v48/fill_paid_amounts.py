"""Bills paid at the till before refunds existed learn what they took: from
the till's Payment rows, or - on a property that doesn't use tills, where no
row was written - the bill's total plus tax at the outlet's rate today. A bill
with neither keeps nothing, and cannot be refunded. Refunds never work this
out themselves."""

import frappe


def execute():
	from kamra.cashier import tills_required
	from kamra.pos import _bill_tax

	taken = dict(frappe.db.sql(
		"""select pos_order, sum(amount) from `tabCashier Transaction`
		where kind = 'Payment' and ifnull(pos_order, '') != '' group by pos_order"""))
	tills = {}
	for bill in frappe.get_all(
			"POS Order",
			filters={"paid": 1, "nc": 0, "posted_to_folio": 0, "paid_amount": 0},
			fields=["name", "property", "order_total"]):
		amount = round(float(taken.get(bill.name) or 0), 2)
		if amount > 0:
			tax = round(max(amount - float(bill.order_total or 0), 0), 2)
		else:
			if bill.property not in tills:
				tills[bill.property] = tills_required(bill.property)
			if tills[bill.property]:
				continue
			tax = _bill_tax(frappe.get_doc("POS Order", bill.name))[1]
			amount = round(float(bill.order_total or 0) + tax, 2)
		frappe.db.set_value("POS Order", bill.name, {"paid_amount": amount, "paid_tax": tax},
		                    update_modified=False)
