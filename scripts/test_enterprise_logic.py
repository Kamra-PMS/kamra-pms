# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Enterprise helpers that do not need a site."""

from __future__ import annotations

import unittest
from decimal import Decimal

from kamra.enterprise_logic import (
	apply_open_band,
	auth_header,
	build_journal,
	clamp_rate,
	deviation,
	facilities_from_amenities,
	minutes_from_eta,
	parse_provider_json,
	predict_occupancy_pct,
	premium_for_occupancy,
	priority_for_arrival,
	recommend_for_guest,
	staffing_hint,
	valid_score,
	weekday_samples,
)


class ForecastTests(unittest.TestCase):
	def test_never_below_on_the_books_and_caps_at_100(self):
		self.assertEqual(predict_occupancy_pct(100, 40, 0, 0, 80, 20), 100)
		self.assertLessEqual(predict_occupancy_pct(10, 40, 30, 5, 90, 21), 100)

	def test_empty_history_uses_a_70_percent_house(self):
		# 30 days out, no pace: 70% left * 0.70 share = 49
		self.assertEqual(predict_occupancy_pct(0, 20, 0, 0, None, 30), 49.0)

	def test_no_rooms_returns_on_the_books(self):
		self.assertEqual(predict_occupancy_pct(40, 0, 5, 5, 90, 3), 40.0)

	def test_open_band(self):
		self.assertEqual(premium_for_occupancy(100), 25)
		self.assertEqual(premium_for_occupancy(50), 0)
		self.assertEqual(premium_for_occupancy(30), -8)

	def test_guardrail_clamps_the_band(self):
		rate, effective = apply_open_band(Decimal("1000"), 100, Decimal("900"), Decimal("1100"))
		self.assertEqual(rate, Decimal("1100"))
		self.assertEqual(effective, 10.0)
		soft, effective = apply_open_band(Decimal("1000"), 20, Decimal("950"), Decimal("0"))
		self.assertEqual(soft, Decimal("950"))
		self.assertLess(effective, 0)

	def test_clamp_ignores_unset_sides(self):
		self.assertEqual(clamp_rate(Decimal("10"), Decimal(0), Decimal(0)), Decimal("10"))


class AnomalyTests(unittest.TestCase):
	def test_needs_four_points(self):
		self.assertIsNone(deviation(100, [1, 2, 3]))

	def test_flat_history_is_quiet(self):
		self.assertIsNone(deviation(100, [100, 100, 100, 100]))

	def test_spike_alerts(self):
		found = deviation(400, [100, 110, 90, 100])
		self.assertIsNotNone(found)
		self.assertEqual(found["direction"], "above")
		self.assertGreater(found["z"], 2)

	def test_weekday_samples_skip_later_dates(self):
		# 2031-03-11 is a Wednesday. 2031-03-18 is the next Wednesday.
		series = [("2031-03-04", 10), ("2031-03-11", 99), ("2031-03-18", 50), ("2031-03-12", 7)]
		self.assertEqual(weekday_samples(series, "2031-03-11"), [10])


class GuestAndOpsTests(unittest.TestCase):
	def test_recommendations(self):
		offers = recommend_for_guest({
			"vip": 1,
			"dietary_notes": "No nuts",
			"special_occasions": "Anniversary 14 Mar",
			"preferred_view": "Sea",
			"current_room_type": "STD",
			"room_types": [
				{"name": "STD", "room_type_name": "Standard", "base_price": 100},
				{"name": "DLX", "room_type_name": "Deluxe", "base_price": 200},
			],
			"stays": [{"room_type": "STD", "nights": 5}],
			"charges": [{"charge_type": "Spa"}, {"charge_type": "Laundry"}],
		})
		codes = {row["code"] for row in offers}
		self.assertTrue({"dietary", "occasion", "vip_welcome", "view", "upgrade", "spa", "laundry", "late_checkout"} <= codes)
		upgrade = next(row for row in offers if row["code"] == "upgrade")
		self.assertEqual(upgrade["room_type"], "DLX")

	def test_no_upgrade_when_already_top(self):
		offers = recommend_for_guest({
			"vip": 1,
			"current_room_type": "DLX",
			"room_types": [
				{"name": "STD", "room_type_name": "Standard", "base_price": 100},
				{"name": "DLX", "room_type_name": "Deluxe", "base_price": 200},
			],
			"stays": [],
			"charges": [],
		})
		self.assertFalse(any(row["code"] == "upgrade" for row in offers))

	def test_arrival_priority_and_eta(self):
		self.assertEqual(priority_for_arrival(True, True, 18 * 60), "Urgent")
		self.assertEqual(priority_for_arrival(True, False, 10 * 60), "Urgent")
		self.assertEqual(priority_for_arrival(True, False, 16 * 60), "High")
		self.assertEqual(priority_for_arrival(False, True, 8 * 60), "Medium")
		self.assertEqual(minutes_from_eta("14:30"), 14 * 60 + 30)
		self.assertEqual(minutes_from_eta("late night"), 22 * 60)
		self.assertEqual(minutes_from_eta(""), 14 * 60)

	def test_staffing_hint(self):
		hint = staffing_hint(20, 14, 14)
		self.assertEqual(hint["attendants"], 2)
		self.assertEqual(hint["cleans"], 28)
		self.assertEqual(staffing_hint(0, 0, 0)["attendants"], 0)

	def test_facilities_and_score(self):
		groups = facilities_from_amenities(["Pool: heated", "Spa", "Pool: kids"])
		self.assertEqual(groups[0], {"area": "Pool", "items": ["heated", "kids"]})
		self.assertEqual(groups[1]["area"], "Resort")
		self.assertEqual(valid_score("5"), 5)
		self.assertIsNone(valid_score(0))
		self.assertIsNone(valid_score("no"))


class AdapterTests(unittest.TestCase):
	def test_auth_header_adds_bearer(self):
		self.assertEqual(auth_header("Authorization", "abc"), {"Authorization": "Bearer abc"})
		self.assertEqual(auth_header("Authorization", "Bearer abc"), {"Authorization": "Bearer abc"})
		self.assertEqual(auth_header("X-Api-Key", "abc"), {"X-Api-Key": "abc"})
		self.assertEqual(auth_header("Authorization", ""), {})

	def test_provider_json(self):
		ok = parse_provider_json(200, '{"key_ids":["A"]}', ok_message="Key encoded.")
		self.assertTrue(ok["ok"])
		self.assertEqual(ok["ids"], ["A"])
		refused = parse_provider_json(200, '{"ok": false, "message": "no card"}', ok_message="x")
		self.assertFalse(refused["ok"])
		plain = parse_provider_json(202, "accepted", ok_message="SMS accepted.")
		self.assertTrue(plain["ok"])
		down = parse_provider_json(0, "timed out", ok_message="x")
		self.assertFalse(down["ok"])

	def test_journal_balances_and_refuses_without_accounts(self):
		missing = build_journal([{"lines": [{"description": "Room", "taxable": 10, "total_tax": 1}]}], {})
		self.assertFalse(missing["ok"])
		built = build_journal(
			[{"lines": [
				{"description": "Room", "taxable": 100, "total_tax": 12},
				{"description": "Restaurant", "taxable": 40, "total_tax": 4},
			]}],
			{"debtors": "Debtors", "room": "Room income", "fnb": "F&B income", "tax": "VAT"},
		)
		self.assertTrue(built["ok"])
		debits = sum(line["debit"] for line in built["lines"])
		credits = sum(line["credit"] for line in built["lines"])
		self.assertEqual(debits, credits)
		self.assertEqual(debits, 156.0)

	def test_tax_folds_into_revenue_when_no_tax_account(self):
		built = build_journal(
			[{"lines": [{"description": "Room", "taxable": 100, "total_tax": 12}]}],
			{"debtors": "Debtors", "room": "Room income"},
		)
		self.assertEqual(sum(line["credit"] for line in built["lines"]), 112.0)


if __name__ == "__main__":
	unittest.main()
