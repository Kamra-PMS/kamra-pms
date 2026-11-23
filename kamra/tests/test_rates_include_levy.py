"""Displayed rates include tax and / or the room levy, to the exact amount.

A hotel that shows its guests one price (tax in it, and the levy in it) types
that price into Kamra and expects the bill to come to exactly that price.
Kamra backs the tax (and the levy) out of the price to get the room's
pre-tax rate. That rate is almost never a whole number of cents, so storing
it to 2 decimals made the bill drift by a fraction of a cent per night (100
at 10% tax stored as 90.91 bills 100.001).

These tests pin, with hand-worked figures (Indonesia's room tax is a flat
10%, the levy is 10%):

* both toggles off: nothing changes, to the cent;
* tax included: the room rate keeps 6 decimals, the levy stays whole cents;
* levy included: the levy is backed out of the price and shown as its own line;
* the OTA path, the channel push, the move-a-line-to-another-folio path and
  the rate screens follow the same rule.
"""

from __future__ import annotations

import frappe

from kamra import api, ledger
from kamra import folio as folio_mod
from kamra.channel_manager import _one_night_rate, lock_channel_rates
from kamra.pricing import quote
from kamra.rates import rate_calendar, rate_options
from kamra.tests.audit_fixtures import (
	TODAY,
	AuditTestCase,
	d,
	guest_folio,
	make_property,
	make_reservation,
	make_room,
	make_room_type,
)

PROP = "UT Exact Rates"


class RatesIncludeLevyTestCase(AuditTestCase):
	properties = (PROP,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP, country="Indonesia", currency="IDR", business_date=TODAY)
		self.rt = make_room_type(PROP, "STD", base_price=100)
		self.room = make_room(PROP, self.rt, "101")

	# -- helpers ------------------------------------------------------------

	def rates(self, price, *, tax=0, levy_included=0, levy=10, levy_taxable=1):
		"""The price the desk typed and which parts of it are inside."""
		frappe.db.set_value("Property", PROP, {
			"rates_include_tax": tax, "rates_include_levy": levy_included,
			"room_levy_percent": levy, "room_levy_taxable": levy_taxable})
		frappe.db.set_value("Room Type", self.rt, "base_price", price)
		frappe.clear_document_cache("Property", PROP)

	def stay(self, nights=1):
		"""A booking whose nights are all posted to the guest folio."""
		res = make_reservation(PROP, self.rt, d(0), d(nights))
		folio_mod.open_folio(res)
		for i in range(nights):
			folio_mod.post_room_night(res, d(i))
		return res

	def lines(self, res, charge_type):
		return [round(float(a), 6) for a in frappe.get_all(
			"Folio Charge", filters={"reservation": res.name, "charge_type": charge_type},
			order_by="posting_date asc, creation asc", pluck="amount")]

	def bill(self, res):
		return float(frappe.db.get_value("Folio", guest_folio(res.name), "grand_total"))

	def night(self, q, i=0):
		return q["nightly"][i]

	# -- both toggles off: nothing changes ---------------------------------

	def test_with_both_toggles_off_nothing_changes(self):
		"""Guards the promise to every hotel that has not switched anything on:
		a rate keeps its cents and the levy is rounded to whole cents."""
		self.rates(99.94)  # levy 10% taxable, nothing included
		res = self.stay()
		self.assertEqual(round(float(res.night_rates[0].rate), 6), 99.94)
		self.assertEqual(self.lines(res, "Room Levy"), [9.99])  # 9.994 -> 9.99

	def test_a_discounted_night_stays_whole_cents_when_nothing_is_included(self):
		"""A 10% rate plan takes 99.94 to 89.946 a night. A property that shows
		prices before tax and levy has always stored 89.95."""
		self.rates(99.94)
		plan = frappe.get_doc({
			"doctype": "Rate Plan", "property": PROP, "rate_plan_name": "Corp",
			"code": "CORP", "modifier_type": "Percent", "modifier_value": -10,
		}).insert(ignore_permissions=True).name
		res = make_reservation(PROP, self.rt, d(0), d(1), rate_plan=plan)
		self.assertEqual(round(float(res.night_rates[0].rate), 6), 89.95)

	# -- tax included -------------------------------------------------------

	def test_tax_included_bills_exactly_the_displayed_price(self):
		"""100 with 10% tax inside: 100 / 1.10 = 90.909091. Stored as 90.91 it
		billed 100.001."""
		self.rates(100, tax=1, levy=0)
		res = self.stay()
		self.assertEqual(round(float(res.night_rates[0].rate), 6), 90.909091)
		self.assertAlmostEqual(self.bill(res), 100, places=5)

	def test_the_levy_stays_whole_cents_when_only_tax_is_included(self):
		"""The levy is a separate charge on top of the price, real money in
		cents; only a levy that is inside the price needs the exact figure."""
		self.rates(99.94, tax=1)  # 99.94 / 1.10 = 90.854545; levy 9.0854545
		res = self.stay()
		self.assertEqual(self.lines(res, "Room Levy"), [9.09])

	# -- levy included ------------------------------------------------------

	def test_a_levy_included_price_is_split_into_room_and_levy(self):
		"""110 before tax with the 10% levy inside: 100 room + 10 levy, then
		10% tax on both = 121."""
		self.rates(110, levy_included=1)
		q = quote(PROP, self.rt, d(0), d(1), 2, 0)
		self.assertEqual(round(self.night(q)["rate"], 6), 100)
		self.assertEqual(round(q["room_levy"], 6), 10)
		self.assertEqual(round(q["amount_after_tax"], 6), 121)
		res = self.stay()
		self.assertEqual(self.lines(res, "Room"), [100.0])
		self.assertEqual(self.lines(res, "Room Levy"), [10.0])
		self.assertAlmostEqual(self.bill(res), 121, places=5)

	def test_tax_and_levy_included_bill_exactly_the_displayed_price(self):
		"""330 with 10% levy and 10% tax on both inside: 330 / 1.21."""
		self.rates(330, tax=1, levy_included=1)
		q = quote(PROP, self.rt, d(0), d(1), 2, 0)
		self.assertEqual(round(self.night(q)["rate"], 6), 272.727273)
		self.assertEqual(round(q["room_levy"], 6), 27.272727)
		self.assertAlmostEqual(q["amount_after_tax"], 330, places=5)
		res = self.stay()
		self.assertEqual(self.lines(res, "Room"), [272.727273])
		self.assertEqual(self.lines(res, "Room Levy"), [27.272727])
		self.assertAlmostEqual(self.bill(res), 330, places=5)

	def test_a_levy_that_is_not_taxed_changes_the_split(self):
		"""320 with tax and an untaxed 10% levy inside: the price is
		net x (1 + 10% tax + 10% levy), so net = 320 / 1.20."""
		self.rates(320, tax=1, levy_included=1, levy_taxable=0)
		res = self.stay()
		self.assertEqual(self.lines(res, "Room"), [266.666667])
		self.assertEqual(self.lines(res, "Room Levy"), [26.666667])
		self.assertAlmostEqual(self.bill(res), 320, places=5)

	def test_several_nights_add_up_to_the_displayed_prices(self):
		self.rates(331, tax=1, levy_included=1)
		res = self.stay(nights=3)
		self.assertAlmostEqual(self.bill(res), 993, places=5)

	def test_the_tax_slab_reads_the_price_without_the_levy(self):
		"""India's slab picks 5% under 7,500 a night and 18% above. 8,000 with a
		10% levy inside is a 7,272.73 room: the 5% slab, not 18%."""
		make_property(PROP, country="India", currency="INR", business_date=TODAY,
		              gst_mode="Slab", gst_slab_threshold=7500,
		              gst_rate_low=5, gst_rate_high=18)
		self.rates(8000, tax=1, levy_included=1)
		q = quote(PROP, self.rt, d(0), d(1), 2, 0)
		self.assertEqual(self.night(q)["gst_rate"], 5)
		self.assertEqual(round(self.night(q)["rate"], 6), 6926.406926)  # 8000 / (1.10 x 1.05)

	# -- the other ways a price reaches the bill ----------------------------

	def test_an_ota_total_backs_out_the_levy_and_keeps_six_decimals(self):
		"""An OTA sold 2 nights at 330 and 331 (661, all-in). The folio must
		bill that: 330 / 1.21 and 331 / 1.21."""
		self.rates(1, tax=1, levy_included=1)
		res = make_reservation(PROP, self.rt, d(0), d(2))
		lock_channel_rates(res, 661, nightly=[
			{"date": d(0), "amount": 330}, {"date": d(1), "amount": 331}])
		self.assertEqual([round(float(r.rate), 6) for r in res.night_rates],
		                 [272.727273, 273.553719])
		self.assertEqual([float(r.gst_rate) for r in res.night_rates], [10.0, 10.0])

	def test_an_ota_night_keeps_six_decimals_when_tax_is_included(self):
		self.rates(1, tax=1)
		res = make_reservation(PROP, self.rt, d(0), d(1))
		lock_channel_rates(res, 331)
		self.assertEqual([round(float(r.rate), 6) for r in res.night_rates], [300.909091])

	def test_the_channel_push_carries_the_levy_inside_the_price(self):
		"""An OTA adds its own tax to the pushed price but knows no levy, so the
		levy goes into the pushed price: 272.727273 + 27.272727 = 300; with an
		untaxed levy the OTA's tax would also land on the levy, so it is
		pushed as 266.666667 + 26.666667 / 1.10 = 290.91."""
		self.rates(330, tax=1, levy_included=1)
		self.assertEqual(_one_night_rate(PROP, self.rt, d(0), d(1)), 300.0)
		self.rates(320, tax=1, levy_included=1, levy_taxable=0)
		self.assertEqual(_one_night_rate(PROP, self.rt, d(0), d(1)), 290.91)
		# a levy that is not inside the price is not the channel's business
		self.rates(330, tax=1)
		self.assertEqual(_one_night_rate(PROP, self.rt, d(0), d(1)), 300.0)

	def test_an_untaxed_levy_inside_the_price_is_not_taxed_by_the_channel(self):
		"""Tax on top, levy inside the displayed price, levy not taxed.

		Room 100, levy 10%, tax 10%: the guest pays 120, tax on the room
		only. The channel adds its own 10% to the price it is given, so the
		push is 100 + 10/1.10 = 109.09 and the channel shows 120. Pushing the
		full 110 would show 121, and locking that 121 back would split the
		room as 100.833333 instead of the desk's 100. A taxed levy is the
		channel's to tax: 110 pushed, 121 on the channel, same as the bill.
		"""
		self.rates(110, levy_included=1, levy_taxable=0)
		self.assertEqual(_one_night_rate(PROP, self.rt, d(0), d(1)), 109.09)
		res = self.stay()
		self.assertEqual(self.lines(res, "Room"), [100.0])
		self.assertEqual(self.lines(res, "Room Levy"), [10.0])
		self.assertAlmostEqual(self.bill(res), 120, places=5)
		# 109.09 with the channel's 10% on top comes back as 120, the desk's rate
		lock_channel_rates(res, 120)
		self.assertEqual([round(float(r.rate), 6) for r in res.night_rates], [100.0])

		self.rates(110, levy_included=1, levy_taxable=1)
		self.assertEqual(_one_night_rate(PROP, self.rt, d(0), d(1)), 110.0)
		q = quote(PROP, self.rt, d(0), d(1), 2, 0)
		self.assertAlmostEqual(q["amount_after_tax"], 121, places=5)

	def test_a_charged_night_correction_posts_the_exact_rate(self):
		"""The reversal is the exact charged rate. Rounding the replacement
		or the credit to cents puts the drift back: 273.553719 corrected to
		272.727273 must not post 272.73, and the credit is -0.826446, not -0.83.
		"""
		from kamra.settings import clear_cache, write_kv

		self.rates(331, tax=1, levy_included=1)
		res = self.stay()
		self.rates(330, tax=1, levy_included=1)
		frappe.clear_document_cache("Room Type", self.rt)
		rows = res.quote_night_rows(res.requote())

		corrected = res.hold_charged_nights(rows, correct=True)
		self.assertEqual([round(line["amount"], 6) for line in corrected["lines"]],
		                 [-273.553719, 272.727273])
		self.assertEqual(round(corrected["nights"][0]["new"], 6), 272.727273)

		write_kv(PROP, "charged_night_rate_change", "Credit the difference")
		clear_cache(PROP)
		credited = res.hold_charged_nights(rows, correct=False)
		self.assertEqual([round(line["amount"], 6) for line in credited["lines"]],
		                 [-0.826446])
		self.assertEqual(round(credited["nights"][0]["new"], 6), 272.727273)

	def test_moving_a_night_to_another_folio_leaves_nothing_on_the_ledger(self):
		"""A room line billed to a company folio leaves the guest's ledger. The
		reversal used to be rounded to whole cents, leaving a fraction behind."""
		self.rates(331, tax=1, levy_included=1)
		res = self.stay()
		src = guest_folio(res.name)
		row = frappe.db.get_value("Folio Charge", {"parent": src, "charge_type": "Room"}, "name")
		extra = api.split_folio(res.name, "Extra")["folio"]
		folio_mod.transfer_charges(src, [row], extra)
		self.assertAlmostEqual(ledger._charge_ledger_net(src, row), 0, places=6)

	def test_extending_a_part_charged_stay_keeps_the_charged_night_exact(self):
		"""A night already on the folio keeps the rate it was charged at, to the
		same decimals; re-quoting the stay must not round it back to cents."""
		self.rates(331, tax=1, levy_included=1)
		res = make_reservation(PROP, self.rt, d(0), d(3))
		folio_mod.open_folio(res)
		folio_mod.post_room_night(res, d(0))
		api.amend_stay(res.name, d(0), d(4), confirm_price=1)
		res.reload()
		self.assertEqual(round(float(res.night_rates[0].rate), 6), 273.553719)

	# -- the screens --------------------------------------------------------

	def test_the_rate_screens_are_told_the_levy_is_included(self):
		self.rates(330, tax=1, levy_included=1)
		self.assertTrue(rate_options(PROP, self.rt, d(0), d(1))["levy_inclusive"])
		self.assertTrue(rate_calendar(PROP, d(0), 1)["levy_inclusive"])
		# no levy to be inside of
		self.rates(330, tax=1, levy_included=1, levy=0)
		self.assertFalse(rate_options(PROP, self.rt, d(0), d(1))["levy_inclusive"])
		self.assertFalse(rate_calendar(PROP, d(0), 1)["levy_inclusive"])
