"""Unit tests for scripts/contract_check.py (no site needed).

    python3 -m unittest scripts/test_contract_check.py
"""

from __future__ import annotations

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contract_check import check

BASE = {
	"version": "2.7.8",
	"tools": {
		"get_folio": {"target": "kamra.api.get_folio", "inputs": {"reservation": "string"},
		              "required": ["reservation"], "mutating": False},
	},
	"methods": {
		"kamra.api.get_folio": {"params": {"reservation": {"default": False}},
		                        "response_keys": ["balance", "charges", "name"]},
	},
	"scopes": {"cashier.read": {"tools": ["get_folio"], "rest": []}},
	"webhooks": {"envelope": ["data", "event", "id"],
	             "events": {"folio.posted": {"payload_keys": ["balance", "folio"]}}},
}


def head(**edits):
	h = copy.deepcopy(BASE)
	for fn in edits.values():
		fn(h)
	return h


def rename(h):
	h["tools"]["folio"] = h["tools"].pop("get_folio")


DEP = {"item": "tool:get_folio", "replacement": "folio", "remove_in": "2.9.0"}


class ContractCheckTest(unittest.TestCase):
	def test_unchanged_passes(self):
		self.assertTrue(check(BASE, head(), [])[0])

	def test_rename_fails(self):
		ok, lines = check(BASE, head(r=rename), [])
		self.assertFalse(ok)
		self.assertIn("BREAKING  tool:get_folio", "\n".join(lines))
		self.assertIn("added     tool:folio", "\n".join(lines))

	def test_alias_with_deprecation_passes(self):
		ok, lines = check(BASE, head(r=rename), [DEP])
		self.assertTrue(ok, lines)
		self.assertIn("deprecated tool:get_folio", "\n".join(lines))

	def test_deprecation_needs_two_minor_releases_and_a_replacement(self):
		self.assertFalse(check(BASE, head(r=rename), [{**DEP, "remove_in": "2.8.5"}])[0])
		self.assertFalse(check(BASE, head(r=rename), [{**DEP, "replacement": ""}])[0])
		self.assertFalse(check(BASE, head(r=rename), [{**DEP, "remove_in": "soon"}])[0])

	def test_new_optional_input_passes(self):
		def add(h):
			h["tools"]["get_folio"]["inputs"]["folio"] = "string"
			h["methods"]["kamra.api.get_folio"]["params"]["folio"] = {"default": True}
		self.assertTrue(check(BASE, head(a=add), [])[0])

	def test_new_required_input_fails(self):
		def add(h):
			h["tools"]["get_folio"]["inputs"]["folio"] = "string"
			h["tools"]["get_folio"]["required"].append("folio")
		self.assertFalse(check(BASE, head(a=add), [])[0])

	def test_new_required_parameter_fails(self):
		def add(h):
			h["methods"]["kamra.api.get_folio"]["params"]["folio"] = {"default": False}
		self.assertFalse(check(BASE, head(a=add), [])[0])

	def test_removed_parameter_fails(self):
		def drop(h):
			h["methods"]["kamra.api.get_folio"]["params"].clear()
		self.assertFalse(check(BASE, head(d=drop), [])[0])

	def test_removed_response_key_fails(self):
		def drop(h):
			h["methods"]["kamra.api.get_folio"]["response_keys"].remove("balance")
		ok, lines = check(BASE, head(d=drop), [])
		self.assertFalse(ok)
		self.assertIn("method:kamra.api.get_folio:response:balance", "\n".join(lines))

	def test_new_response_key_passes(self):
		def add(h):
			h["methods"]["kamra.api.get_folio"]["response_keys"].append("currency")
		self.assertTrue(check(BASE, head(a=add), [])[0])

	def test_removed_payload_key_event_and_scope_fail(self):
		def drop_key(h):
			h["webhooks"]["events"]["folio.posted"]["payload_keys"].remove("balance")
		def drop_event(h):
			h["webhooks"]["events"].clear()
		def drop_scope(h):
			h["scopes"].clear()
		def narrow_scope(h):
			h["scopes"]["cashier.read"]["tools"].clear()
		for fn in (drop_key, drop_event, drop_scope, narrow_scope):
			self.assertFalse(check(BASE, head(x=fn), [])[0], fn.__name__)

	def test_new_tool_and_event_pass(self):
		def add(h):
			h["tools"]["x"] = copy.deepcopy(h["tools"]["get_folio"])
			h["webhooks"]["events"]["folio.voided"] = {"payload_keys": []}
		self.assertTrue(check(BASE, head(a=add), [])[0])


if __name__ == "__main__":
	unittest.main()
