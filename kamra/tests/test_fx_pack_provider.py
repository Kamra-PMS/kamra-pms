"""A country pack may supply the official exchange-rate source.

Some countries publish the rate a bill must use (a central bank's daily
quote), and the open market feed is the wrong number there. A pack that
declares market_rates(home) -> (rates, as_of) is asked instead of
ExchangeRate-API; everything around it - the margin, the Online source,
the Manual rate that wins, the hourly cache - stays the desk's own.
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import frappe

from kamra import ledger
from kamra.localization import generic
from kamra.tests.audit_fixtures import PROP_A, TODAY, AuditTestCase, make_property
from kamra.tests.test_multi_currency import _fake_api


def _pack(rates=None, fail=None):
	"""A country pack whose market_rates is a MagicMock; anything else it
	is asked for comes from the generic pack."""
	source = MagicMock(side_effect=fail, return_value=(
		rates or {"USD": 80.0, "EUR": 100.0}, "2031-03-11 (official)"))
	source.__module__ = "kamra_fake_fx_pack"
	pack = types.ModuleType("kamra_fake_fx_pack")
	pack.market_rates = source
	pack.__getattr__ = lambda name: getattr(generic, name)
	return pack


class PackRatesSourceTestCase(AuditTestCase):
	properties = (PROP_A,)

	def setUp(self):
		super().setUp()
		self.at(TODAY, "kamra.folio", "kamra.business_date", "kamra.ledger")
		make_property(PROP_A, business_date=TODAY, currency="INR")
		frappe.db.delete("Exchange Rate", {"property": PROP_A})
		frappe.db.delete("Property Setting", {"property": PROP_A, "setting_key": ["like", "fx_%"]})
		from kamra import settings
		settings.write_kv(PROP_A, "fx_currencies", "USD, EUR, GBP")
		settings.write_kv(PROP_A, "fx_margin_pct", 2)
		settings.clear_cache(PROP_A)
		self.addCleanup(settings.clear_cache, PROP_A)
		for k in ("kamra:fx_not_offered:", "kamra:fx_market:"):
			frappe.cache.delete_keys(k)
			self.addCleanup(frappe.cache.delete_keys, k)

	def row(self, cur):
		return frappe.db.get_value("Exchange Rate", {"property": PROP_A, "currency": cur},
		                           ["buy_rate", "sell_rate", "market_rate", "source"], as_dict=True)

	def test_pack_source_is_used_with_the_usual_margin(self):
		pack = _pack()
		with patch("kamra.localization.pack_for", return_value=pack), \
				patch("requests.get") as net:
			out = ledger.fetch_exchange_rates(PROP_A)
		net.assert_not_called()
		pack.market_rates.assert_called_once_with("INR")
		self.assertEqual(sorted(out["updated"]), ["EUR", "USD"])
		self.assertEqual(out["not_offered"], ["GBP"])
		self.assertEqual(out["as_of"], "2031-03-11 (official)")
		usd = self.row("USD")
		self.assertEqual((usd.market_rate, usd.buy_rate, usd.sell_rate, usd.source),
		                 (80.0, 78.4, 81.6, "Online"))

	def test_without_a_pack_source_the_open_feed_is_asked(self):
		self.assertIs(ledger._rates_source(PROP_A), ledger.market_rates)
		fake = _fake_api()
		with patch("requests.get", fake):
			out = ledger.fetch_exchange_rates(PROP_A)
		fake.assert_called_once()
		self.assertIn("/INR", fake.call_args.args[0])
		self.assertEqual(sorted(out["updated"]), ["EUR", "USD"])
		self.assertEqual(self.row("USD").source, "Online")

	def test_pack_source_is_chosen(self):
		pack = _pack()
		with patch("kamra.localization.pack_for", return_value=pack):
			self.assertIs(ledger._rates_source(PROP_A), pack.market_rates)

	def test_todays_manual_rate_is_kept(self):
		ledger.upsert_exchange_rate(PROP_A, "USD", 83.0, 84.0)
		with patch("kamra.localization.pack_for", return_value=_pack()), \
				patch("requests.get") as net:
			out = ledger.fetch_exchange_rates(PROP_A)
		net.assert_not_called()
		self.assertEqual(out["kept_manual"], ["USD"])
		self.assertEqual((self.row("USD").buy_rate, self.row("USD").source), (83.0, "Manual"))
		self.assertEqual(self.row("EUR").source, "Online")

	def test_pack_failure_leaves_rates_alone(self):
		ledger.upsert_exchange_rate(PROP_A, "USD", 83.0, 84.0)
		before = frappe.db.count("Exchange Rate", {"property": PROP_A})
		boom = frappe.ValidationError("Could not fetch exchange rates. Today's rates are unchanged.")
		with patch("kamra.localization.pack_for", return_value=_pack(fail=boom)), \
				self.assertRaises(frappe.ValidationError):
			ledger.fetch_exchange_rates(PROP_A)
		self.assertEqual(frappe.db.count("Exchange Rate", {"property": PROP_A}), before)

	def test_scheduled_fetch_caches_each_source_apart(self):
		from kamra import settings
		settings.write_kv(PROP_A, "fx_auto_fetch", 1)
		settings.clear_cache(PROP_A)
		pack = _pack({"USD": 70.0, "EUR": 100.0})
		with patch("kamra.localization.pack_for", return_value=pack), \
				patch("requests.get") as net, patch("frappe.db.commit"):
			ledger.auto_fetch_exchange_rates()
			frappe.cache.delete_keys("kamra:fx_not_offered:")
			ledger.auto_fetch_exchange_rates()  # GBP asked again, from the hour's reply
		net.assert_not_called()
		self.assertEqual(pack.market_rates.call_count, 1)
		self.assertEqual(self.row("USD").market_rate, 70.0)
		self.assertTrue(frappe.cache.get_value("kamra:fx_market:kamra_fake_fx_pack:INR"))
		# the open feed's hour is its own: a pack's reply is never served for it
		fake = _fake_api()
		with patch("requests.get", fake):
			mids, _ = ledger._market_rates_hourly("INR")
		fake.assert_called_once()
		self.assertEqual(mids["USD"], 80.0)  # 1 / 0.0125 from the open feed, not the pack's
		self.assertTrue(frappe.cache.get_value("kamra:fx_market:kamra.ledger:INR"))
