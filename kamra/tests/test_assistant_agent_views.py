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


class AgentToolsTestCase(unittest.TestCase):
	def test_every_tool_param_reaches_its_endpoint(self):
		import inspect
		for name, (fn_name, _d, params, inject, _m) in assistant.TOOLS.items():
			fn = assistant._resolve(fn_name)
			self.assertIsNotNone(fn, name)
			sig = inspect.signature(fn).parameters
			# record_payment turns `reservation` into the stay's folio first
			missing = [p for p in params if p not in sig
			           and (name, p) != ("record_payment", "reservation")]
			self.assertEqual(missing, [], name)
			if inject:
				self.assertIn("property", sig, name)

	def test_bank_transfer_advance_needs_the_transfer_number(self):
		import frappe
		with self.assertRaises(frappe.ValidationError) as e:
			assistant._run_tool("record_advance", {
				"reservation": "UT-NONE", "amount": 100, "mode": "Bank Transfer"}, "UT-PROP")
		self.assertIn("transfer number", str(e.exception))

	def test_empty_answer_is_retried_then_explained(self):
		import unittest.mock as mock

		def reply(text):
			r = mock.Mock(status_code=200)
			r.json.return_value = {"choices": [{"message": {"content": text}}]}
			return r
		with mock.patch.object(assistant, "_post_chat", return_value=reply("  ")):
			self.assertEqual(assistant._retry_text("b", {}, "m", []), assistant.EMPTY_REPLY)
		with mock.patch.object(assistant, "_post_chat", return_value=reply("12 rooms")):
			self.assertEqual(assistant._retry_text("b", {}, "m", []), "12 rooms")
