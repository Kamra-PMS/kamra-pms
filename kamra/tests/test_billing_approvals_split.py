"""#411: manager approval for allowances, a separate bill for each guest
sharing a room, and changing the company during a stay."""

from __future__ import annotations

import json

import frappe

from kamra import api, folio as folio_mod
from kamra.settings import clear_cache
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	d,
	ensure_user,
	guest_folio,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)

DESK = "ut.bill.desk@test.local"
FINANCE = "ut.bill.finance@test.local"
GM = "ut.bill.gm@test.local"
COMPANY = "UT Bill Corp"
COMPANY_B = "UT Bill Other Corp"


def set_setting(prop: str, key: str, value) -> None:
	name = frappe.db.get_value("Property Setting",
	                           {"property": prop, "setting_key": key})
	if name:
		frappe.db.set_value("Property Setting", name, "value", json.dumps(value))
	else:
		frappe.get_doc({"doctype": "Property Setting", "property": prop,
		                "setting_key": key, "value": json.dumps(value)}
		               ).insert(ignore_permissions=True)
	clear_cache(prop)


def set_pin(user: str, pin: str = "4321") -> None:
	frappe.db.delete("Cashier PIN", {"name": user})
	frappe.get_doc({"doctype": "Cashier PIN", "user": user, "pin": pin}
	               ).insert(ignore_permissions=True)


def ledger_net(folio: str) -> float:
	"""Every folio's Guest-ledger legs net to what the folio still owes."""
	return round(float(frappe.db.sql(
		"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabFolio Ledger Entry`
		   WHERE folio = %s AND ledger = 'Guest'""", folio)[0][0]), 2)


def bal(folio: str) -> float:
	return round(float(frappe.db.get_value("Folio", folio, "balance") or 0), 2)


def company(name: str, rules: list[tuple[str, str]], credit: int = 1) -> str:
	if frappe.db.exists("Corporate Account", name):
		corp = frappe.get_doc("Corporate Account", name)
	else:
		corp = frappe.get_doc({"doctype": "Corporate Account", "company_name": name})
	corp.credit_allowed = credit
	corp.disabled = 0
	corp.set("billing_rules", [{"charge_type": c, "pay_by": p} for c, p in rules])
	corp.save(ignore_permissions=True) if not corp.is_new() else \
		corp.insert(ignore_permissions=True)
	return corp.name


class BillingApprovalsSplitTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY)
		frappe.db.delete("Property Setting", {"property": PROP_A})
		set_setting(PROP_A, "use_cashier_tills", 0)
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		ensure_user(DESK, ["Front Desk"])
		ensure_user(FINANCE, ["Finance"])
		ensure_user(GM, ["Hotel Admin"])
		self.corp = company(COMPANY, [("Room", "Company")])
		self.corp_b = company(COMPANY_B, [("Room", "Company"),
		                                  ("Laundry", "Company")])

	def stay(self, **fields):
		return make_reservation(PROP_A, self.rt, d(-1), d(1),
		                        status="Checked In", room=self.room, **fields)

	# 1. allowances need a manager ----------------------------------------

	def test_allowance_waits_for_a_manager_then_posts_with_approver(self):
		set_setting(PROP_A, "allowance_approval", "Hotel Admin")
		set_setting(PROP_A, "allowance_approval_above", 100)
		res = self.stay()
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, "Laundry", "UT Laundry", 500, gst_rate=0)

		frappe.set_user(DESK)
		small = api.post_allowance(folio, 50, "UT stain")
		self.assertNotIn("pending", small)  # under the threshold: posts
		out = api.post_allowance(folio, 200, "UT late towels")
		self.assertTrue(out["pending"])
		self.assertEqual(bal(folio), 450)  # the folio is untouched

		# Finance is not the approver here
		frappe.set_user(FINANCE)
		with self.assertRaises(frappe.PermissionError):
			api.decide_allowance(out["request"], approve=1)

		frappe.set_user(GM)
		self.assertTrue(api.allowance_requests(PROP_A)["can_decide"])
		api.decide_allowance(out["request"], approve=1)
		frappe.set_user("Administrator")
		self.assertEqual(bal(folio), 250)
		self.assertEqual(ledger_net(folio), 250)
		req = frappe.get_doc("Allowance Request", out["request"])
		self.assertEqual((req.status, req.decided_by), ("Approved", GM))
		rows = [r for r in api_report() if r["action"] == "Allowance"]
		self.assertEqual(rows[0]["approver"], GM)
		self.assertIn(f"asked by {DESK}", rows[0]["detail"])
		with self.assertRaisesRegex(frappe.ValidationError, "already approved"):
			api.decide_allowance(out["request"], approve=1)

	def test_rejection_is_kept_with_who_and_why(self):
		set_setting(PROP_A, "allowance_approval", "Hotel Admin or Finance")
		res = self.stay()
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, "Laundry", "UT Laundry", 500, gst_rate=0)
		frappe.set_user(DESK)
		out = api.post_allowance(folio, 10, "UT goodwill")
		self.assertTrue(out["pending"])  # 0 = every allowance
		frappe.set_user(FINANCE)
		with self.assertRaisesRegex(frappe.ValidationError, "Say why"):
			api.decide_allowance(out["request"], approve=0)
		api.decide_allowance(out["request"], approve=0, note="UT not ours")
		frappe.set_user("Administrator")
		self.assertEqual(bal(folio), 500)
		req = frappe.get_doc("Allowance Request", out["request"])
		self.assertEqual((req.status, req.decided_by, req.decision_note),
		                 ("Rejected", FINANCE, "UT not ours"))
		rej = [r for r in api_report() if r["action"] == "Allowance rejected"]
		self.assertEqual(rej[0]["approver"], FINANCE)

	def test_on_the_spot_approval_with_the_managers_pin(self):
		set_setting(PROP_A, "allowance_approval", "Hotel Admin")
		set_pin(GM, "2468")
		res = self.stay()
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, "Laundry", "UT Laundry", 500, gst_rate=0)
		frappe.set_user(DESK)
		out = api.post_allowance(folio, 100, "UT noisy room")
		self.assertIn(GM, [a["user"] for a in api.allowance_approvers(PROP_A)])
		with self.assertRaises(frappe.ValidationError):
			api.decide_allowance(out["request"], supervisor=GM, supervisor_pin="0000")
		api.decide_allowance(out["request"], supervisor=GM, supervisor_pin="2468")
		frappe.set_user("Administrator")
		self.assertEqual(bal(folio), 400)
		self.assertEqual(frappe.db.get_value("Allowance Request", out["request"],
		                                     "decided_by"), GM)

	def test_agents_ask_but_never_approve(self):
		set_setting(PROP_A, "allowance_approval", "Hotel Admin")
		res = self.stay()
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, "Laundry", "UT Laundry", 500, gst_rate=0)
		frappe.flags.kamra_agent_call = "MCP"
		try:
			# even as Administrator, an agent call only asks
			out = api.post_allowance(folio, 100, "UT agent asks")
			self.assertTrue(out["pending"])
			with self.assertRaises(frappe.PermissionError):
				api.decide_allowance(out["request"], approve=1)
		finally:
			frappe.flags.kamra_agent_call = None
		self.assertEqual(bal(folio), 500)

	def test_supervisor_reason_code_asks_even_with_the_setting_off(self):
		from kamra.ledger import ensure_default_reason_codes
		ensure_default_reason_codes()
		res = self.stay()
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, "Laundry", "UT Laundry", 500, gst_rate=0)
		frappe.set_user(DESK)
		self.assertNotIn("pending", api.post_allowance(folio, 20, "", reason_code="ADJ-RATE"))
		self.assertTrue(api.post_allowance(folio, 20, "UT", reason_code="ADJ-COMP")["pending"])
		with self.assertRaisesRegex(frappe.ValidationError, "Adjust"):
			api.post_allowance(folio, 20, "UT", reason_code="VOID-ERR")

	# 2. a bill for each guest -------------------------------------------

	def test_each_guest_gets_a_bill_in_their_name(self):
		res = self.stay(occupants=[{"full_name": "Asha Rao"},
		                           {"full_name": "Ben Ode"}])
		folio_mod.post_room_night(res, d(-1))
		main = guest_folio(res.name)
		total = bal(main)
		bills = api.open_guest_bills(res.name)["bills"]
		self.assertEqual({b["name"] for b in bills}, {"Asha Rao", "Ben Ode"})
		# asking again reuses them
		self.assertEqual(api.open_guest_bills(res.name)["bills"], bills)
		room = [c.name for c in frappe.get_doc("Folio", main).charges
		        if c.charge_type == "Room"]
		api.share_folio_charges(main, room, [b["folio"] for b in bills])
		others = [b["folio"] for b in bills]
		parts = [bal(f) for f in others]
		self.assertEqual(parts[0], parts[1])
		self.assertAlmostEqual(bal(main) + sum(parts), total, places=2)
		for f in [main, *others]:
			self.assertEqual(ledger_net(f), bal(f))
		# same tax rate on every part
		rates = {c.gst_rate for f in [main, *others]
		         for c in frappe.get_doc("Folio", f).charges if c.charge_type == "Room"}
		self.assertEqual(len(rates), 1)
		inv = api.folio_invoice(others[0])
		self.assertEqual(inv["bill_to"]["name"], "Asha Rao")
		# check-out wants every bill settled
		with self.assertRaisesRegex(frappe.ValidationError, "owed"):
			api.check_out(res.name)

	def test_share_by_chosen_percent(self):
		res = self.stay(occupants=[{"full_name": "Cara Lee"}])
		folio_mod.post_room_night(res, d(-1))
		main = guest_folio(res.name)
		row = next(c for c in frappe.get_doc("Folio", main).charges
		           if c.charge_type == "Room")
		base = row.amount
		bill = api.open_guest_bills(res.name)["bills"][0]["folio"]
		with self.assertRaises(frappe.ValidationError):
			api.share_folio_charges(main, [row.name], [bill], shares=[100])
		api.share_folio_charges(main, [row.name], [bill], shares=[30])
		moved = frappe.get_doc("Folio", bill).charges[0].amount
		self.assertAlmostEqual(moved, round(base * 0.3, 2), places=2)


def api_report():
	from kamra.reports import void_allowance_report
	return void_allowance_report(PROP_A)
