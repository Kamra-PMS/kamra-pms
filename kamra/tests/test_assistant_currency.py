"""Property currency in both chat paths; provider and database calls are mocked."""

import json
import unittest
from contextlib import ExitStack
from inspect import unwrap
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe

from kamra import assistant


class AssistantCurrencyTestCase(unittest.TestCase):
	def setUp(self):
		self.settings = SimpleNamespace(extra_instructions="")
		clock = patch.object(assistant, "nowdate", return_value="2031-03-12")
		clock.start()
		self.addCleanup(clock.stop)

	def prompt(self, currency, symbol=None, **fields):
		prop = frappe._dict({"property_name": "Test Hotel", "currency": currency, **fields})
		with patch.object(assistant, "frappe") as frappe_mock:
			frappe_mock.get_cached_doc.return_value = prop
			frappe_mock.db.get_value.return_value = symbol
			text = assistant._system_prompt("P-NI", self.settings)
			frappe_mock.get_cached_doc.assert_called_once_with("Property", "P-NI")
			if currency:
				frappe_mock.db.get_value.assert_called_once_with("Currency", currency, "symbol")
			return text

	def test_configured_currency_symbols_come_from_the_frappe_currency_record(self):
		for currency, symbol in (("NIO", "C$"), ("INR", "₹"), ("USD", "$"),
		                         ("SAR", "ر.س"), ("EUR", "€"), ("IDR", "Rp"), ("KWD", "د.ك")):
			with self.subTest(currency=currency):
				text = self.prompt(currency, symbol)
				self.assertIn(f"The property's currency is {currency}.", text)
				self.assertIn(f"Its display label is {symbol}.", text)
				if currency != "INR":
					self.assertNotIn("₹", text)
				self.assertIn("Do not convert amounts", text)

	def test_missing_or_blank_symbols_fall_back_to_the_currency_code(self):
		for symbol in (None, "", "   "):
			with self.subTest(symbol=symbol):
				text = self.prompt("NIO", symbol)
				self.assertIn("Its display label is NIO.", text)
				self.assertNotIn("₹", text)

	def test_customized_symbol_is_respected(self):
		self.assertIn("Its display label is US$.", self.prompt("USD", "US$"))

	def test_property_name_date_and_extra_instructions_are_preserved(self):
		self.settings.extra_instructions = "Responde en español. Example: {amount}."
		text = self.prompt("NIO")
		self.assertIn("assistant for Test Hotel", text)
		self.assertIn("Today is 2031-03-12", text)
		self.assertTrue(text.endswith(self.settings.extra_instructions))

	def test_name_falls_back_to_the_property_id(self):
		self.assertIn("assistant for P-NI", self.prompt("NIO", "C$", property_name=""))

	def test_configured_currency_takes_precedence_over_country_defaults(self):
		with patch("kamra.localization.pack_for") as pack_for:
			text = self.prompt("USD", "$", country="India")
			self.assertIn("currency is USD.", text)
			self.assertIn("Its display label is $.", text)
			self.assertNotIn("₹", text)
			pack_for.assert_not_called()

	def test_missing_currency_uses_the_existing_country_pack_fallback(self):
		for currency, symbol in (("INR", "₹"), ("USD", "$"), ("SAR", "ر.س")):
			with self.subTest(currency=currency), patch("kamra.localization.pack_for") as pack_for:
				pack_for.return_value.locale.return_value = {"currency": currency}
				text = self.prompt(None, symbol)
				self.assertIn(f"currency is {currency}.", text)
				self.assertIn(f"Its display label is {symbol}.", text)
				pack_for.assert_called_once_with("P-NI")

	def test_unknown_currency_is_not_guessed(self):
		with patch("kamra.localization.pack_for") as pack_for:
			pack_for.return_value.locale.return_value = {}
			text = self.prompt(None)
			self.assertIn("currency is unspecified.", text)
			self.assertIn("ask rather than guess", text)
			self.assertNotIn("₹", text)

	def test_switching_properties_does_not_reuse_the_previous_currency(self):
		properties = {
			"P-NI": frappe._dict(property_name="Nicaragua Hotel", currency="NIO"),
			"P-IN": frappe._dict(property_name="India Hotel", currency="INR"),
		}
		symbols = {"NIO": "C$", "INR": "₹"}
		with patch.object(assistant, "frappe") as frappe_mock:
			frappe_mock.get_cached_doc.side_effect = lambda _dt, name: properties[name]
			frappe_mock.db.get_value.side_effect = lambda _dt, currency, _field: symbols[currency]
			for name, currency in (("P-NI", "NIO"), ("P-IN", "INR")):
				text = assistant._system_prompt(name, self.settings)
				self.assertIn(f"currency is {currency}.", text)
				self.assertIn(f"Its display label is {symbols[currency]}.", text)

	def check_chat_path(self, streamed):
		settings = SimpleNamespace(
			enabled=True, extra_instructions="", base_url="https://provider.example.test/v1",
			model="test-model", get_password=Mock(return_value="test-key"),
		)
		history = [{"role": "assistant", "content": "Earlier answer: ₹2,520"},
		           {"role": "user", "content": "¿Cuánto es el total?"}]
		response = Mock(status_code=200)
		response.json.return_value = {"choices": [{"message": {"content": "C$2,520"}}]}
		stream = Mock(status_code=200)
		stream.iter_lines.return_value = [
			("data: " + json.dumps({"choices": [{"delta": {"content": "C$2,520"}}]})).encode(),
			b"data: [DONE]",
		]
		with ExitStack() as stack:
			frappe_mock = stack.enter_context(patch.object(assistant, "frappe"))
			frappe_mock.get_cached_doc.return_value = frappe._dict(property_name="Test Hotel", currency="NIO")
			frappe_mock.db.get_value.return_value = "C$"
			stack.enter_context(patch.object(assistant, "_settings", return_value=settings))
			stack.enter_context(patch.object(assistant, "_tool_defs", return_value=[]))
			stack.enter_context(patch.object(assistant, "_turn_cards", return_value=[]))
			stack.enter_context(patch.object(assistant, "_missing_refs", return_value=""))
			post = stack.enter_context(patch.object(assistant, "_post_chat", side_effect=[response, stream]))
			if streamed:
				# Exercise the request and generator without Frappe's HTTP/role wrappers.
				result = unwrap(assistant.ask_stream)("P-NI", history)
				self.assertIn("C$2,520", result.get_data(as_text=True))
				self.assertEqual(post.call_count, 2)
			else:
				result = unwrap(assistant.ask)("P-NI", history)
				self.assertEqual(result["reply"], "C$2,520")
				self.assertEqual(post.call_count, 1)
			for call in post.call_args_list:
				messages = call.args[2]["messages"]
				self.assertIn("currency is NIO.", messages[0]["content"])
				self.assertIn("Its display label is C$.", messages[0]["content"])
				self.assertNotIn("₹", messages[0]["content"])
				self.assertIn("Never infer currency", messages[0]["content"])
				self.assertEqual(messages[1:1 + len(history)], history)

	def test_regular_chat_sends_the_property_currency_to_the_provider(self):
		self.check_chat_path(streamed=False)

	def test_streaming_chat_sends_the_property_currency_to_both_provider_calls(self):
		self.check_chat_path(streamed=True)

	def test_quote_occupancy_instructions_and_tool_rules(self):
		"""Ensure the assistant rules explicitly tell the LLM to use `quote`
		with exact occupancy and prohibit quoting from booking_options base_price."""
		text = self.prompt("BRL", "R$")
		self.assertIn("Always call `quote` with the requested dates and exact adult/child occupancy", text)
		self.assertIn("Never quote prices using the base_price from `booking_options` or `availability`", text)

		tool_desc = assistant.TOOLS["booking_options"][1]
		self.assertIn("Do not use its base_price to quote stays", tool_desc)
		self.assertIn("call `quote` for actual pricing", tool_desc)

	def test_out_of_credit_is_said_plainly_on_every_chat_path(self):
		settings = SimpleNamespace(enabled=True, base_url="https://provider.example.test/v1",
		                           model="m", get_password=Mock(return_value="k"))
		broke = Mock(status_code=429, text=json.dumps(
			{"error": {"code": "insufficient_quota", "message": "You exceeded your current quota"}}))
		history = [{"role": "user", "content": "hi"}]
		with ExitStack() as stack:
			stack.enter_context(patch.object(assistant, "_settings", return_value=settings))
			stack.enter_context(patch.object(assistant, "_system_prompt", return_value="sys"))
			stack.enter_context(patch.object(assistant, "_tool_defs", return_value=[]))
			stack.enter_context(patch.object(assistant, "_post_chat", return_value=broke))
			with self.assertRaises(frappe.ValidationError) as err:
				unwrap(assistant.ask)("P", history)
			self.assertIn("out of credit", str(err.exception))
			for fn in (assistant.ask_stream, assistant.help_ask):
				body = unwrap(fn)("P", history).get_data(as_text=True)
				self.assertIn('"code": "out_of_credit"', body, fn.__name__)
				self.assertNotIn("AI provider error", body)
		# any other failure keeps the provider's own error
		self.assertIn("AI provider error (500)",
		              assistant._provider_error(Mock(status_code=500, text="boom")))
		self.assertTrue(assistant._out_of_credit(Mock(status_code=402, text="")))
