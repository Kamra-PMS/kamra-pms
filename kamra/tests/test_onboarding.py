"""Guided and quick setup, and the Finish setup list."""

from __future__ import annotations

import frappe

from kamra import api, onboarding
from kamra.tests.audit_fixtures import AuditTestCase

NAME = "UT Setup Palace"


class OnboardingTestCase(AuditTestCase):
	properties = (NAME,)

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- admin onboarding
		if frappe.db.exists("Property", NAME):
			frappe.delete_doc("Property", NAME, force=True, ignore_permissions=True)

	def setup(self, **extra):
		return api.setup_property({"property": {"property_name": NAME, "country": "India",
		                                        "city": "Pune"}, **extra})

	def test_quick_setup_is_just_the_property_in_its_region(self):
		out = self.setup()
		self.assertEqual((out["room_types"], out["rooms"]), (0, 0))
		prop = frappe.get_doc("Property", NAME)
		self.assertEqual(prop.currency, "INR")
		self.assertTrue(prop.timezone)
		# nothing picked: every module stays on, as before
		self.assertEqual(api.enabled_modules(NAME), list(api.ALL_MODULES))
		self.assertEqual(frappe.db.count("POS Outlet", {"property": NAME}), 0)

	def test_guided_setup_applies_modules_and_wants(self):
		self.setup(modules=["booking-engine", "fnb"], wants=["channel-manager", "bogus"])
		self.assertCountEqual(api.enabled_modules(NAME),
		                      ["booking-engine", "fnb", "front-desk", "admin"])
		self.assertEqual(frappe.db.get_value("Property", NAME, "setup_wants"), "channel-manager")

	def test_unknown_module_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.setup(modules=["time-travel"])

	def test_pos_setup_creates_outlets_stations_and_tills(self):
		out = self.setup(modules=["fnb", "finance"], pos={
			"outlets": [{"name": "Rooftop", "type": "Bar"}, {"name": "Cafe", "type": "Restaurant"}],
			"stations": ["Kitchen", "Bar", "Nonsense"],
			"tills": [{"name": "Cafe till", "kind": "Restaurant", "outlet": "Cafe"}],
			"cash_office": True,
		})["pos"]
		self.assertEqual(out, {"outlets": 2, "stations": 2, "tills": 2})
		printers = frappe.get_all("Kitchen Printer", {"property": NAME}, ["name", "prints_kots"])
		self.assertEqual(len(printers), 2)
		routes = frappe.get_all("Kitchen Printer Route", fields=["outlet", "prep_station"],
		                        filters={"parenttype": "Kitchen Printer",
		                                 "parent": ["in", [p.name for p in printers]]})
		self.assertEqual(len(routes), 4)  # 2 stations x 2 outlets
		till = frappe.get_doc("Cashier Terminal", {"property": NAME, "terminal_name": "Cafe till"})
		self.assertEqual(frappe.db.get_value("POS Outlet", till.outlet, "outlet_name"), "Cafe")
		self.assertEqual(frappe.db.get_value("Cashier Terminal",
		                                     {"property": NAME, "kind": "Cash Office"}, "terminal_name"),
		                 "Cash office")

	def test_checklist_follows_the_modules_and_progress(self):
		self.setup(modules=["fnb"], wants=["channel-manager"])
		keys = {i["key"]: i for i in onboarding.setup_checklist(NAME)["items"]}
		self.assertFalse(keys["room_types"]["done"])
		self.assertIn("outlets", keys)
		self.assertIn("channel", keys)
		self.assertNotIn("booking_engine", keys)  # that module is off
		frappe.get_doc({"doctype": "POS Outlet", "property": NAME, "outlet_name": "UT Cafe"}).insert()
		keys = {i["key"]: i for i in onboarding.setup_checklist(NAME)["items"]}
		self.assertTrue(keys["outlets"]["done"])

	def test_all_done_is_one_hundred_percent_shape(self):
		self.setup()
		out = onboarding.setup_checklist(NAME)
		self.assertEqual(out["total"], len(out["items"]))
		self.assertLessEqual(out["done"], out["total"])
