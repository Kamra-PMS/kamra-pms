"""The dashboard keeps the hotel's money from the front desk.

A receptionist sees arrivals, departures, in house, rooms and occupancy
(now and 90 days on the books); revenue, ADR, RevPAR, collections and
outstanding are for Finance, Revenue, the night auditor and managers, who
also get today, month to date and year to date against last year. The
server leaves the money out, so it is not just hidden on screen.
"""

from __future__ import annotations

import json

import frappe

from kamra import dashboards, night_audit, reports
from kamra.tests.audit_fixtures import (
	PROP_A,
	TODAY,
	AuditTestCase,
	ensure_user,
	make_property,
	make_room,
	make_reservation,
	make_room_type,
)

DESK = "ut-desk-figures@kamra.local"
FIN = "ut-fin-figures@kamra.local"


class DashboardRolesTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.business_date")
		make_property(PROP_A, business_date=TODAY, country="India")
		self.rt = make_room_type(PROP_A, "STD", base_price=1000)
		self.room = make_room(PROP_A, self.rt, "101")
		ooo = make_room(PROP_A, self.rt, "102")
		frappe.db.set_value("Room", ooo, "housekeeping_status", "Out of Order")
		ensure_user(DESK, ["Front Desk"])
		ensure_user(FIN, ["Finance"])

	def tearDown(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore
		super().tearDown()

	def test_front_desk_gets_movement_but_no_figures(self):
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- the receptionist
		out = dashboards.property_dashboard(PROP_A, TODAY)
		self.assertTrue(out["figures_hidden"])
		for key in dashboards.FIGURE_KEYS:
			self.assertNotIn(key, out)
		self.assertIn("arrivals", out)
		self.assertIn("in_house", out["front_desk"])
		self.assertIn("room_status", out["housekeeping"])
		with self.assertRaises(frappe.PermissionError):
			reports.manager_flash(PROP_A, TODAY)

	def test_front_desk_gets_occupancy_and_forecast(self):
		make_reservation(PROP_A, self.rt, "2031-03-11", "2031-03-14",
		                 status="Checked In", room=self.room)
		sellable = frappe.db.count("Room", {
			"property": PROP_A, "housekeeping_status": ("!=", "Out of Order")})
		occupied = frappe.db.count("Room", {"property": PROP_A, "occupancy_status": "Occupied"})
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- the receptionist
		out = dashboards.property_dashboard(PROP_A, TODAY)
		self.assertEqual(out["occupancy_now"]["sellable"], sellable)
		self.assertEqual(out["occupancy_now"]["occupied"], occupied)
		fc = out["forecast"]
		self.assertEqual(len(fc), 90)
		self.assertEqual(fc[0]["date"], TODAY)
		# on the books the nights of the 12th and 13th, gone by the 14th
		self.assertEqual([f["booked"] for f in fc[:3]], [1, 1, 0])
		self.assertEqual(fc[0]["occupancy_pct"], round(100 / sellable, 1))
		money = {"revenue", "adr", "revpar", "amount", "collections", "outstanding"}
		for row in fc:
			self.assertFalse(money & set(row))

	def _group(self, rooms: int, cutoff: str, **fields) -> str:
		return frappe.get_doc({
			"doctype": "Group Booking", "property": PROP_A, "group_name": "UT Wedding",
			"check_in_date": "2031-03-13", "check_out_date": "2031-03-15",
			"status": "Confirmed", "cutoff_date": cutoff, **fields,
			"blocks": [{"room_type": self.rt, "rooms_blocked": rooms}],
		}).insert(ignore_permissions=True).name

	def test_forecast_shows_unpicked_group_rooms_as_held(self):
		self.at(TODAY, "kamra.business_date", "kamra.group_blocks")
		for no in ("103", "104", "105"):
			make_room(PROP_A, self.rt, no)
		gb = self._group(3, "2031-03-12")
		make_reservation(PROP_A, self.rt, "2031-03-13", "2031-03-15", group_booking=gb)
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- the receptionist
		fc = dashboards.property_dashboard(PROP_A, TODAY)["forecast"]
		# 4 sellable; the 13th and 14th: 1 picked up (booked), 2 still held
		self.assertEqual([(f["booked"], f["held"], f["available"]) for f in fc[:4]],
		                 [(0, 0, 4), (1, 2, 1), (1, 2, 1), (0, 0, 4)])
		self.assertEqual(fc[1]["occupancy_pct"], 25.0)
		self.assertEqual(fc[1]["occupancy_with_holds_pct"], 75.0)

	def test_released_group_holds_do_not_count(self):
		self.at(TODAY, "kamra.business_date", "kamra.group_blocks")
		self._group(1, "2031-03-11")  # cutoff passed yesterday
		fc = dashboards.property_dashboard(PROP_A, TODAY)["forecast"]
		self.assertEqual([f["held"] for f in fc[:4]], [0, 0, 0, 0])
		self.assertEqual(fc[1]["occupancy_with_holds_pct"], fc[1]["occupancy_pct"])

	def test_occupancy_report_has_no_money_for_the_desk(self):
		from kamra import custom_reports
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- the receptionist
		out = custom_reports._run_dataset(PROP_A, "occupancy_by_day", TODAY, TODAY)
		ids = {c["id"] for c in out["columns"]}
		self.assertIn("occupancy_pct", ids)
		self.assertFalse(ids & set(custom_reports.DATASETS["occupancy_by_day"]["money_columns"]))
		self.assertNotIn("adr", out["rows"][0])
		frappe.set_user(FIN)  # nosemgrep: frappe-setuser -- finance
		out = custom_reports._run_dataset(PROP_A, "occupancy_by_day", TODAY, TODAY)
		self.assertIn("adr", {c["id"] for c in out["columns"]})

	def test_finance_gets_the_figures(self):
		frappe.set_user(FIN)  # nosemgrep: frappe-setuser -- finance
		out = dashboards.property_dashboard(PROP_A, TODAY)
		self.assertNotIn("figures_hidden", out)
		for key in ("revenue_today", "adr", "revpar", "occupancy_pct", "finance", "statistics"):
			self.assertIn(key, out)

	def _charge(self, folio, date, charge_type, amount):
		doc = frappe.get_doc("Folio", folio)
		doc.append("charges", {"posting_date": date, "charge_type": charge_type,
		                       "description": "UT", "qty": 1, "rate": amount,
		                       "amount": amount, "reservation": doc.reservation})
		doc.save(ignore_permissions=True)

	def test_manager_gets_this_year_against_last_year(self):
		from frappe.utils import date_diff

		from kamra.tests.audit_fixtures import guest_folio
		res = make_reservation(PROP_A, self.rt, "2031-03-11", "2031-03-14",
		                       status="Checked In", room=self.room)
		folio = guest_folio(res.name)
		for day, kind, amount in (
			("2031-03-12", "Room", 2000), ("2031-03-12", "Food & Beverage", 500),
			("2031-03-01", "Room", 1000), ("2030-05-01", "Room", 3000),
			# last year
			("2030-03-12", "Room", 1500), ("2029-06-01", "Room", 800)):
			self._charge(folio, day, kind, amount)
		rooms = frappe.db.count("Room", {"property": PROP_A})
		frappe.set_user(FIN)  # nosemgrep: frappe-setuser -- finance
		self.assertNotIn("comparison", dashboards.property_dashboard(PROP_A, TODAY))
		out = dashboards.property_dashboard(PROP_A, TODAY, with_comparison=1)
		cmp = out["comparison"]
		# India's financial year starts 1 April
		self.assertEqual(cmp["financial_year_start"], "2030-04-01")
		p = {x["id"]: x for x in cmp["periods"]}
		self.assertEqual(set(p), {"today", "mtd", "ytd", "on_the_books"})

		today = p["today"]
		self.assertEqual(today["ly_from_date"], "2030-03-12")
		self.assertEqual(today["this_year"]["rooms_sold"], 1)
		self.assertEqual(today["this_year"]["room_revenue"], 2000)
		self.assertEqual(today["this_year"]["total_revenue"], 2500)
		self.assertEqual(today["this_year"]["adr"], 2000)
		self.assertEqual(today["this_year"]["revpar"], round(2000 / rooms))
		self.assertEqual(today["last_year"]["room_revenue"], 1500)
		self.assertEqual(today["change_pct"]["room_revenue"], 33.3)

		mtd = p["mtd"]
		self.assertEqual((mtd["from_date"], mtd["ly_from_date"]), ("2031-03-01", "2030-03-01"))
		self.assertEqual(mtd["this_year"]["rooms_sold"], 2)
		self.assertEqual(mtd["this_year"]["room_revenue"], 3000)
		self.assertEqual(mtd["this_year"]["adr"], 1500)
		self.assertEqual(mtd["this_year"]["occupancy_pct"], round(100 * 2 / (rooms * 12), 1))
		self.assertEqual(mtd["last_year"]["room_revenue"], 1500)
		self.assertEqual(mtd["change_pct"]["room_revenue"], 100.0)

		ytd = p["ytd"]
		self.assertEqual((ytd["from_date"], ytd["ly_from_date"], ytd["ly_to_date"]),
		                 ("2030-04-01", "2029-04-01", "2030-03-12"))
		days = date_diff("2031-03-12", "2030-04-01") + 1
		self.assertEqual(ytd["this_year"]["rooms_sold"], 3)
		self.assertEqual(ytd["this_year"]["room_revenue"], 6000)
		self.assertEqual(ytd["this_year"]["total_revenue"], 6500)
		self.assertEqual(ytd["this_year"]["revpar"], round(6000 / (rooms * days)))
		self.assertEqual(ytd["last_year"]["rooms_sold"], 2)
		self.assertEqual(ytd["last_year"]["room_revenue"], 2300)
		self.assertEqual(ytd["change_pct"]["room_revenue"], round(100 * 3700 / 2300, 1))

		# the forecast's 90 nights from tonight, over sellable rooms
		ahead = p["on_the_books"]
		self.assertEqual((ahead["from_date"], ahead["to_date"]), (TODAY, "2031-06-09"))
		self.assertEqual(ahead["rooms_basis"], "sellable")
		sellable = out["occupancy_now"]["sellable"]
		self.assertEqual(ahead["this_year"]["rooms_sold"], 2)  # the 12th and 13th
		self.assertEqual(ahead["this_year"]["occupancy_pct"], round(100 * 2 / (sellable * 90), 1))
		# last year's 2030-03-12 and 2030-05-01 nights fall in the same 90
		self.assertEqual(ahead["last_year"]["rooms_sold"], 2)
		self.assertEqual(ahead["last_year"]["occupancy_pct"], round(100 * 2 / (sellable * 90), 1))
		self.assertEqual(ahead["change_pct"]["rooms_sold"], 0.0)
		self.assertNotIn("room_revenue", ahead["this_year"])  # nothing posted yet
		self.assertEqual(len(out["forecast"]), 90)

	def test_forecast_counts_held_and_pending_payment_stays(self):
		for no in ("103", "104"):
			make_room(PROP_A, self.rt, no)
		for status in ("Held", "Pending Payment", "Cancelled"):
			make_reservation(PROP_A, self.rt, "2031-03-12", "2031-03-13", status=status)
		fc = dashboards.property_dashboard(PROP_A, TODAY)["forecast"]
		self.assertEqual(fc[0]["booked"], 2)  # live, as group_blocks counts a pick up

	def _audit_run(self) -> str:
		pack = {"business_date": TODAY, "in_house": [], "journal": {"rows": []},
		        **{k: {"x": 1} for k in night_audit.PACK_FIGURE_SECTIONS},
		        "reports": [{"key": k, "title": t} for k, t in night_audit.REPORTS]}
		return frappe.get_doc({
			"doctype": "Night Audit Run", "property": PROP_A, "business_date": TODAY,
			"status": "Completed", "report_pack": json.dumps(pack),
		}).insert(ignore_permissions=True).name

	def test_audit_pack_has_no_money_for_the_desk(self):
		run = self._audit_run()
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- the receptionist
		pack = night_audit.night_audit_pack(run)["pack"]
		self.assertTrue(pack["figures_hidden"])
		for key in night_audit.PACK_FIGURE_SECTIONS:
			self.assertNotIn(key, pack)
		self.assertIn("in_house", pack)
		self.assertIn("journal", pack)
		keys = {r["key"] for r in pack["reports"]}
		self.assertFalse(keys & set(night_audit.PACK_FIGURE_REPORTS))
		self.assertIn("no_shows", keys)
		frappe.set_user(FIN)  # nosemgrep: frappe-setuser -- finance
		pack = night_audit.night_audit_pack(run)["pack"]
		self.assertIn("manager_flash", pack)
		self.assertNotIn("figures_hidden", pack)

	def test_scheduled_report_is_sent_as_its_owner(self):
		from unittest.mock import patch

		from frappe.utils import now_datetime

		from kamra import custom_reports
		frappe.set_user(DESK)  # nosemgrep: frappe-setuser -- the receptionist saves it
		frappe.get_doc({
			"doctype": "Kamra Custom Report", "property": PROP_A, "title": "UT sched",
			"dataset": custom_reports.PACK_PREFIX + "hotel_manager", "schedule_frequency": "Daily",
			"schedule_time": now_datetime().strftime("%H:00"),
			"recipients": "ut@kamra.local",
		}).insert(ignore_permissions=True)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- the scheduler
		sent_as = []
		with patch.object(custom_reports, "email_custom_report",
		                  lambda **kw: sent_as.append(frappe.session.user)):
			custom_reports.run_scheduled_custom_reports()
		self.assertIn(DESK, sent_as)
		self.assertEqual(frappe.session.user, "Administrator")
