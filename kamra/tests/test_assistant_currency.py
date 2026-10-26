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

	def prompt(self, currency, **fields):
		prop = frappe._dict(property_name="Test Hotel", currency=currency, **fields)
		with (
			patch.object(assistant.frappe, "get_cached_doc", return_value=prop) as get_property,
		):
			text = assistant._system_prompt("P-NI", self.settings)
			get_property.assert_called_once_with("Property", "P-NI")
			return text

	def test_configured_currencies_are_used_without_a_fixed_rupee_sign(self):
		for currency in ("NIO", "INR", "USD", "SAR", "EUR", "IDR", "KWD"):
			with self.subTest(currency=currency):
				text = self.prompt(currency)
				self.assertIn(f"The property's currency is {currency}.", text)
				self.assertNotIn("₹", text)
				self.assertIn("Do not convert amounts", text)

	def test_property_name_date_and_extra_instructions_are_preserved(self):
		self.settings.extra_instructions = "Responde en español. Example: {amount}."
		text = self.prompt("NIO")
		self.assertIn("assistant for Test Hotel", text)
		self.assertIn("Today is 2031-03-12", text)
		self.assertTrue(text.endswith(self.settings.extra_instructions))

	def test_name_falls_back_to_the_property_id(self):
		prop = frappe._dict(property_name="", currency="NIO")
		with patch.object(assistant.frappe, "get_cached_doc", return_value=prop):
			self.assertIn("assistant for P-NI", assistant._system_prompt("P-NI", self.settings))

	def test_configured_currency_takes_precedence_over_country_defaults(self):
		with patch("kamra.localization.pack_for") as pack_for:
			self.assertIn("currency is USD.", self.prompt("USD", country="India"))
			pack_for.assert_not_called()

	def test_missing_currency_uses_the_existing_country_pack_fallback(self):
		for currency in ("INR", "USD", "SAR"):
			with self.subTest(currency=currency), patch("kamra.localization.pack_for") as pack_for:
				pack_for.return_value.locale.return_value = {"currency": currency}
				self.assertIn(f"currency is {currency}.", self.prompt(None))
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
		with patch.object(assistant.frappe, "get_cached_doc", side_effect=lambda _dt, name: properties[name]):
			self.assertIn("currency is NIO.", assistant._system_prompt("P-NI", self.settings))
			self.assertIn("currency is INR.", assistant._system_prompt("P-IN", self.settings))

	def check_chat_path(self, streamed):
		settings = SimpleNamespace(
			enabled=True, extra_instructions="", base_url="https://provider.example.test/v1",
			model="test-model", get_password=Mock(return_value="test-key"),
		)
		history = [{"role": "assistant", "content": "Earlier answer: ₹2,520"},
		           {"role": "user", "content": "¿Cuánto es el total?"}]
		response = Mock(status_code=200)
		response.json.return_value = {"choices": [{"message": {"content": "NIO 2,520"}}]}
		stream = Mock(status_code=200)
		stream.iter_lines.return_value = [
			("data: " + json.dumps({"choices": [{"delta": {"content": "NIO 2,520"}}]})).encode(),
			b"data: [DONE]",
		]
		with ExitStack() as stack:
			frappe_mock = stack.enter_context(patch.object(assistant, "frappe"))
			frappe_mock.get_cached_doc.return_value = frappe._dict(property_name="Test Hotel", currency="NIO")
			stack.enter_context(patch.object(assistant, "_settings", return_value=settings))
			stack.enter_context(patch.object(assistant, "_tool_defs", return_value=[]))
			stack.enter_context(patch.object(assistant, "_turn_cards", return_value=[]))
			stack.enter_context(patch.object(assistant, "_missing_refs", return_value=""))
			post = stack.enter_context(patch.object(assistant, "_post_chat", side_effect=[response, stream]))
			if streamed:
				# Exercise the request and generator without Frappe's HTTP/role wrappers.
				result = unwrap(assistant.ask_stream)("P-NI", history)
				self.assertIn("NIO 2,520", result.get_data(as_text=True))
				self.assertEqual(post.call_count, 2)
			else:
				result = unwrap(assistant.ask)("P-NI", history)
				self.assertEqual(result["reply"], "NIO 2,520")
				self.assertEqual(post.call_count, 1)
			for call in post.call_args_list:
				messages = call.args[2]["messages"]
				self.assertIn("currency is NIO.", messages[0]["content"])
				self.assertNotIn("₹", messages[0]["content"])
				self.assertIn("Never infer currency", messages[0]["content"])
				self.assertEqual(messages[1:1 + len(history)], history)

	def test_regular_chat_sends_the_property_currency_to_the_provider(self):
		self.check_chat_path(streamed=False)

	def test_streaming_chat_sends_the_property_currency_to_both_provider_calls(self):
		self.check_chat_path(streamed=True)
