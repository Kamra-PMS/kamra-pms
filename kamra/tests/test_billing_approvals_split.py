"""#411: manager approval for allowances, a separate bill for each guest
sharing a room, and changing the company during a stay."""

from __future__ import annotations

import json

import frappe

from kamra import api, folio as folio_mod
from kamra.settings import clear_cache
from kamra.tests.audit_fixtures import (
	PROP_A,
	PROP_B,
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
	properties = (PROP_A, PROP_B)

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

		set_pin(GM, "2468")
		frappe.set_user(GM)
		self.assertTrue(api.allowance_requests(PROP_A)["can_decide"])
		api.decide_allowance(out["request"], approve=1, pin="2468")
		frappe.set_user("Administrator")
		self.assertEqual(bal(folio), 250)
		self.assertEqual(ledger_net(folio), 250)
		req = frappe.get_doc("Allowance Request", out["request"])
		self.assertEqual((req.status, req.decided_by), ("Approved", GM))
		rows = [r for r in api_report() if r["action"] == "Allowance"]
		self.assertEqual(rows[0]["approver"], GM)
		self.assertIn(f"asked by {DESK}", rows[0]["detail"])
		with self.assertRaisesRegex(frappe.ValidationError, "already approved"):
			api.decide_allowance(out["request"], approve=1, pin="2468")

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

	def test_request_cannot_be_decided_or_reopened_outside_the_api(self):
		set_setting(PROP_A, "allowance_approval", "Hotel Admin")
		res = self.stay()
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, "Laundry", "UT Laundry", 500, gst_rate=0)
		frappe.set_user(DESK)
		out = api.post_allowance(folio, 100, "UT rest bypass")
		frappe.set_user("Administrator")
		req = frappe.get_doc("Allowance Request", out["request"])
		req.amount = 400  # what was asked for is fixed
		with self.assertRaises(frappe.ValidationError):
			req.save(ignore_permissions=True)
		req.reload()
		req.status = "Approved"  # /api/resource can't decide
		with self.assertRaises(frappe.PermissionError):
			req.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "Allowance Request", "property": PROP_A,
			                "folio": folio, "amount": 10, "reason": "UT",
			                "status": "Approved"}).insert(ignore_permissions=True)
		set_pin("Administrator", "1357")
		api.decide_allowance(out["request"], approve=1, pin="1357")
		req.reload()
		req.status = "Pending"  # re-opened, it would post twice
		with self.assertRaises(frappe.ValidationError):
			req.save(ignore_permissions=True)
		self.assertEqual(bal(folio), 400)

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

	def test_serial_given_once_when_an_allowance_posts(self):
		set_setting(PROP_A, "allowance_approval", "Hotel Admin")
		set_pin(GM, "2468")
		res = self.stay()
		folio = guest_folio(res.name)
		api.add_folio_charge(folio, "Laundry", "UT Laundry", 500, gst_rate=0)
		frappe.set_user(DESK)
		asked = api.post_allowance(folio, 30, "UT asked")
		refused = api.post_allowance(folio, 40, "UT refused")
		frappe.set_user("Administrator")
		# asking gives no number
		self.assertFalse(frappe.db.get_value("Allowance Request", asked["request"], "serial"))
		frappe.set_user(GM)
		api.decide_allowance(refused["request"], approve=0, note="UT no")
		with self.assertRaises(frappe.ValidationError):  # approving takes the PIN
			api.decide_allowance(asked["request"], approve=1)
		first = api.decide_allowance(asked["request"], approve=1, pin="2468")["serial"]
		# a manager's own allowance posts at once, signed with their PIN
		with self.assertRaises(frappe.ValidationError):
			api.post_allowance(folio, 20, "UT own")
		own = api.post_allowance(folio, 20, "UT own", pin="2468")
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.get_value("Allowance Request", refused["request"], "serial"))
		code = frappe.db.get_value("Property", PROP_A, "short_code")
		self.assertRegex(first, rf"^ALW-{code}-\d\d-\d{{5}}$")
		self.assertEqual(int(own["serial"][-5:]), int(first[-5:]) + 1)
		# on the bill line and the request, once each
		lines = [c.allowance_serial for c in frappe.get_doc("Folio", folio).charges
		         if c.charge_type == "Allowance"]
		self.assertEqual(sorted(lines), sorted([first, own["serial"]]))
		self.assertEqual(frappe.db.count("Allowance Request", {"serial": own["serial"]}), 1)
		self.assertEqual(bal(folio), 450)
		self.assertEqual(ledger_net(folio), 450)
		self.assertEqual({r["serial"] for r in api_report() if r["action"] == "Allowance"},
		                 {first, own["serial"]})

		# the voucher names the approver and carries the number
		v = api.allowance_voucher(first)
		self.assertEqual((v["serial"], v["approved_by"], v["approved_by_role"],
		                  v["requested_by"], v["amount"], v["approved_with_pin"]),
		                 (first, GM, "Hotel Admin", DESK, 30, True))
		self.assertEqual(v["room"], "101")
		# signed with the job title from Staff & access, else the role
		self.assertEqual(v["approved_by_title"], "Hotel Admin")
		frappe.db.set_value("User", GM, "kamra_job_title", "Duty Manager")
		self.assertEqual(api.allowance_voucher(first)["approved_by_title"], "Duty Manager")
		row = next(r for r in api.allowance_requests(PROP_A, status="Approved")["requests"]
		           if r["serial"] == first)
		self.assertEqual(row["decided_by_title"], "Duty Manager")
		frappe.db.set_value("User", GM, "kamra_job_title", "")
		with self.assertRaisesRegex(frappe.ValidationError, "posted allowance"):
			api.allowance_voucher(refused["request"])

		# a second property counts on its own
		make_property(PROP_B, business_date=TODAY)
		frappe.db.delete("Property Setting", {"property": PROP_B})
		set_setting(PROP_B, "use_cashier_tills", 0)
		rt_b = make_room_type(PROP_B, "STD", base_price=1000)
		res_b = make_reservation(PROP_B, rt_b, d(-1), d(1), status="Checked In",
		                         room=make_room(PROP_B, rt_b, "201"))
		folio_b = guest_folio(res_b.name)
		api.add_folio_charge(folio_b, "Laundry", "UT Laundry", 500, gst_rate=0)
		b = api.post_allowance(folio_b, 10, "UT other hotel")["serial"]
		code_b = frappe.db.get_value("Property", PROP_B, "short_code")
		self.assertNotEqual(code_b, code)  # same initials, own code
		self.assertTrue(b.startswith(f"ALW-{code_b}-"))
		self.assertNotEqual(b, first)

		# a new short code starts a new series: no number comes back
		frappe.set_user("Administrator")
		prop = frappe.get_doc("Property", PROP_A)
		prop.short_code = "utz9"
		prop.save(ignore_permissions=True)
		self.assertEqual(prop.short_code, "UTZ9")
		frappe.set_user(GM)
		new = api.post_allowance(folio, 5, "UT new code", pin="2468")["serial"]
		self.assertTrue(new.startswith("ALW-UTZ9-"), new)
		self.assertNotIn(new, (first, own["serial"]))

	def test_short_code_is_checked_and_unique(self):
		from kamra.kamra.doctype.property.property import default_short_code
		make_property(PROP_B, business_date=TODAY)
		def save(code):
			a = frappe.get_doc("Property", PROP_A)
			a.short_code = code
			a.save(ignore_permissions=True)
			return a
		for bad in ("A", "TOOLONG7", "S-R", "SR X"):
			with self.assertRaisesRegex(frappe.ValidationError, "Short code"):
				save(bad)
		with self.assertRaisesRegex(frappe.ValidationError, "already used"):
			save(frappe.db.get_value("Property", PROP_B, "short_code"))
		# empty: back to its initials, de-duplicated
		a = save("")
		self.assertRegex(a.short_code, r"^[A-Z0-9]{2,6}$")
		self.assertNotEqual(a.short_code, frappe.db.get_value("Property", PROP_B, "short_code"))
		self.assertEqual(default_short_code("The Sunrise & Sea Residency", exclude=PROP_A)[:3], "TSS")
		self.assertEqual(default_short_code("Ewa")[:2], "EW")  # one word: first letters

	def test_backfill_gives_each_property_its_own_code(self):
		from kamra.patches.v46.backfill_property_short_code import execute
		twins = ("UT Sun Rise", "UT Sea Rock")  # both U S R
		for p in twins:
			make_property(p)
		frappe.db.sql("UPDATE `tabProperty` SET short_code = NULL WHERE name IN %s", (twins,))
		execute()
		a, b = (frappe.db.get_value("Property", p, "short_code") for p in twins)
		self.assertTrue(a and b and a != b, (a, b))
		# same initials: the older one keeps them, the other gets a digit
		self.assertEqual(a[:3], b[:3])
		self.assertTrue(a[-1].isdigit() or b[-1].isdigit(), (a, b))

	def test_staff_job_title_set_in_staff_and_access(self):
		from kamra import staff
		ensure_user("ut.bill.duty@test.local", ["Front Desk"])
		frappe.set_user(GM)
		staff.save_staff(PROP_A, "ut.bill.duty@test.local", "Duty Person", ["Front Desk"],
		                 job_title=" Duty Manager ")
		row = next(r for r in staff.list_staff(PROP_A) if r["user"] == "ut.bill.duty@test.local")
		self.assertEqual(row["job_title"], "Duty Manager")
		# your own name and title, never your own access
		me = next(r for r in staff.list_staff(PROP_A) if r["is_self"])
		staff.save_staff(PROP_A, GM, "UT General", me["roles"], me["properties"] or "all",
		                 job_title="General Manager")
		self.assertEqual(frappe.db.get_value("User", GM, "kamra_job_title"), "General Manager")
		with self.assertRaises(frappe.PermissionError):
			staff.save_staff(PROP_A, GM, "UT General", ["Front Desk"], "all")
		frappe.set_user("Administrator")
		frappe.db.set_value("User", GM, "kamra_job_title", "")

	def test_new_property_starts_with_approval_on(self):
		from kamra.settings import get_setting
		name = "UT Fresh Approvals"
		frappe.db.delete("Property Setting", {"property": name})
		if frappe.db.exists("Property", name):
			frappe.delete_doc("Property", name, force=True, ignore_permissions=True)
		frappe.get_doc({"doctype": "Property", "property_name": name,
		                "city": "Testville", "state": "Karnataka"}
		               ).insert(ignore_permissions=True)
		self.assertEqual(get_setting(name, "allowance_approval"), "Hotel Admin")
		self.assertEqual(get_setting(name, "allowance_approval_above"), 0)
		# an existing property without the setting keeps the old default
		frappe.db.delete("Property Setting", {"property": PROP_A})
		clear_cache(PROP_A)
		self.assertEqual(get_setting(PROP_A, "allowance_approval"), "Off")
		clear_cache(name)

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
		# a line listed twice is shared once
		api.share_folio_charges(main, [row.name, row.name], [bill], shares=[30])
		moved = frappe.get_doc("Folio", bill).charges[0].amount
		self.assertAlmostEqual(moved, round(base * 0.3, 2), places=2)

	# 3. change the company ----------------------------------------------

	def test_change_company_reroutes_and_logs(self):
		res = self.stay(company=self.corp, booking_type="Corporate")
		folio_mod.post_room_night(res, d(-1))
		main = guest_folio(res.name)
		api.add_folio_charge(main, "Laundry", "UT Laundry", 300, gst_rate=0)
		cf = frappe.db.get_value("Folio", {"reservation": res.name,
		                                   "folio_type": "Company"})
		room_total = bal(cf)
		self.assertGreater(room_total, 0)
		with self.assertRaisesRegex(frappe.ValidationError, "why"):
			api.change_stay_company(res.name, "", company=self.corp_b)
		out = api.change_stay_company(res.name, "UT employer changed",
		                              company=self.corp_b)
		self.assertEqual(frappe.db.get_value("Reservation", res.name, "company"),
		                 self.corp_b)
		# company B also pays laundry: it joins the company bill
		self.assertEqual(out["moved"], 1)
		self.assertEqual(bal(cf), room_total + 300)
		self.assertEqual(bal(main), 0)
		for f in (cf, main):
			self.assertEqual(ledger_net(f), bal(f))
		# future charges route by company B's rules
		self.assertEqual(folio_mod.target_folio(
			frappe.get_doc("Reservation", res.name), "Laundry"), cf)
		self.assertTrue(frappe.db.exists("Agent Action Log", {
			"action_type": "change_company", "reference_name": res.name}))

		# no company: everything goes back to the guest
		api.change_stay_company(res.name, "UT paying himself", company=None)
		self.assertEqual(bal(cf), 0)
		self.assertEqual(bal(main), room_total + 300)
		self.assertEqual(frappe.db.get_value("Reservation", res.name,
		                                     "booking_type"), "Individual")

	def test_change_company_refused_after_an_invoice_to_the_old_one(self):
		from kamra import ledger
		res = self.stay(company=self.corp, booking_type="Corporate")
		folio_mod.post_room_night(res, d(-1))
		cf = frappe.db.get_value("Folio", {"reservation": res.name,
		                                   "folio_type": "Company"})
		ledger.transfer_to_city_ledger(cf, self.corp)
		with self.assertRaisesRegex(frappe.ValidationError, "city ledger"):
			api.change_stay_company(res.name, "UT", company=self.corp_b)
		folio_mod.close_folio(cf)
		with self.assertRaisesRegex(frappe.ValidationError, "Cancel that invoice"):
			api.change_stay_company(res.name, "UT", company=self.corp_b)

	def test_change_company_runs_credit_control(self):
		from kamra.credit import CreditBlocked
		set_setting(PROP_A, "credit_control", "Block")
		acct = frappe.get_doc({"doctype": "City Ledger Account",
		                       "property": PROP_A, "company": self.corp_b,
		                       "credit_limit": 100}).insert(ignore_permissions=True)
		self.assertTrue(acct.name)
		res = self.stay(company=self.corp, booking_type="Corporate")
		folio_mod.post_room_night(res, d(-1))
		frappe.set_user(DESK)
		with self.assertRaises(CreditBlocked):
			api.change_stay_company(res.name, "UT", company=self.corp_b)


def api_report():
	from kamra.reports import void_allowance_report
	return void_allowance_report(PROP_A)
