"""What the model sees of the audit checklist and the desk board."""

import unittest

from kamra import assistant


class AgentViewsTestCase(unittest.TestCase):
	def test_only_open_blockers_are_listed_as_blocking(self):
		view = assistant._audit_for_agent({
			"blockers": ["tills"],
			"checks": [
				{"key": "tills", "title": "Open tills", "severity": "block", "count": 3},
				{"key": "bills", "title": "Open bills", "severity": "block", "count": 0},
				{"key": "rates", "title": "Rate variance", "severity": "warn", "count": 2},
			],
		})
		self.assertEqual([c["key"] for c in view["blocking"]], ["tills"])
		self.assertEqual([c["key"] for c in view["warnings"]], ["rates"])
		self.assertEqual(view["clear"], ["Open bills"])
		self.assertNotIn("checks", view)

	def test_overpaid_guest_is_a_credit_not_a_debt(self):
		view = assistant._desk_for_agent({
			"arrivals": [], "departures": [],
			"in_house": [{"balance_due": -2060.0}, {"balance_due": 500.0}, {"balance_due": 0}],
		})
		over, owes, clear = view["in_house"]
		self.assertEqual((over["balance_due"], over["credit"]), (0, 2060.0))
		self.assertEqual(owes["balance_due"], 500.0)
		self.assertNotIn("credit", clear)
