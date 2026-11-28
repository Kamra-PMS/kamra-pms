"""The agreed extra-guest charge when the property's rates include tax: the
quote reads the typed figure with the tax inside, so the folio must bill it the
same way instead of adding the tax again."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, nowdate

from kamra.api import create_booking, get_quote
from kamra.folio import post_room_night

NIGHTS = 2
# (country, currency, room price, extra-guest charge): 0, 2 and 3 decimals
HOTELS = (
	("Indonesia", "IDR", 389000, 150000),
	("Japan", "JPY", 11000, 2200),
	("India", "INR", 3000, 700),
	("United Arab Emirates", "AED", 300, 45.5),
	("Kuwait", "KWD", 45.125, 12.375),
)
# (rates include tax, rates include the levy, levy %)
SETTINGS = ((1, 0, 0), (1, 0, 10), (1, 1, 10), (0, 0, 0), (0, 0, 10), (0, 1, 10))


class TestExtraGuestTax(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- test fixture
		frappe.local.lang = "en"
		self.dates = [str(add_days(nowdate(), 10 + i)) for i in range(NIGHTS + 1)]

	def hotel(self, country="Indonesia", currency="IDR", room=389000,
	          tax_in=1, levy_in=0, levy=0):
		prop = frappe.get_doc({"doctype": "Property",
			"property_name": "TEST EXTRA TAX " + frappe.generate_hash(length=8),
			"country": country, "currency": currency,
			"rates_include_tax": tax_in, "rates_include_levy": levy_in,
			"room_levy_percent": levy}).insert(ignore_permissions=True).name
		rt = frappe.get_doc({"doctype": "Room Type", "property": prop, "room_type_code": "STD",
			"room_type_name": "Standard", "base_price": room, "tax_percent": 10,
			"adults_capacity": 2, "max_extra_beds": 1}).insert(ignore_permissions=True).name
		frappe.get_doc({"doctype": "Room", "property": prop, "room_type": rt,
			"room_number": "101"}).insert(ignore_permissions=True)
		return prop, rt

	def book(self, prop, rt, extra):
		name = create_booking(prop, rt, self.dates[0], self.dates[-1], "Extra Guest",
		                      adults=2, over_capacity_guests=1, over_capacity_charge=extra,
		                      over_capacity_reason="Agreed at the desk")["reservation"]
		return frappe.get_doc("Reservation", name)

	def bill(self, res):
		"""(everything billed, the extra-guest lines) after posting every night."""
		for night in self.dates[:-1]:
			post_room_night(frappe.get_doc("Reservation", res.name), night)
		lines = frappe.get_all("Folio Charge", filters={"reservation": res.name},
		                       fields=["charge_type", "amount", "gst_rate", "total"])
		return (sum(flt(r.total) for r in lines),
		        [r for r in lines if r.charge_type == "Extra Guests"])

	def set_inclusive(self, prop, value):
		frappe.db.set_value("Property", prop, "rates_include_tax", value)
		frappe.clear_document_cache("Property", prop)

	def test_the_bill_equals_the_quote(self):
		for country, currency, room, extra in HOTELS:
			for tax_in, levy_in, levy in SETTINGS:
				with self.subTest(currency=currency, tax_in=tax_in, levy_in=levy_in,
				                  levy=levy):
					prop, rt = self.hotel(country, currency, room, tax_in, levy_in, levy)
					q = get_quote(prop, rt, self.dates[0], self.dates[-1], adults=2,
					              over_capacity_charge=extra)
					res = self.book(prop, rt, extra)
					billed, beds = self.bill(res)
					# a levy added on top is posted in whole cents, a night at a time
					self.assertAlmostEqual(billed, q["amount_after_tax"], delta=0.011 * NIGHTS)
					self.assertEqual(len(beds), NIGHTS)
					for bed in beds:
						shown = extra if tax_in else extra * (1 + flt(bed.gst_rate) / 100)
						self.assertAlmostEqual(flt(bed.total), shown, places=5)

	def test_a_booking_quoted_before_the_setting_changed_bills_its_quote(self):
		for before, after in ((0, 1), (1, 0)):
			with self.subTest(before=before, after=after):
				prop, rt = self.hotel(tax_in=before)
				res = self.book(prop, rt, 150000)
				self.set_inclusive(prop, after)
				billed, _beds = self.bill(res)
				self.assertAlmostEqual(billed, flt(res.amount_after_tax), places=2)

	def test_a_booking_without_a_quote_follows_the_setting(self):
		for tax_in, shown in ((1, 150000), (0, 165000)):
			with self.subTest(tax_in=tax_in):
				prop, rt = self.hotel(tax_in=tax_in)
				res = self.book(prop, rt, 150000)
				frappe.db.set_value("Reservation", res.name, "quote_snapshot", None)
				_billed, beds = self.bill(res)
				self.assertEqual([round(flt(b.total), 3) for b in beds], [shown] * NIGHTS)
