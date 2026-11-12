"""Documented response and payload keys in the public contract (#580).

`docs-site/gen_contract.py` writes these into `contract.json`, and CI
fails a PR that drops one (`scripts/contract_check.py`). List only keys the
code really returns: `kamra/tests/test_contract_keys.py` calls each method
and fires each event on a site and checks every key below is there.

Adding a key is safe. Removing one is a breaking change: deprecate it in
`contract-deprecations.json` first (see docs-site/api-stability.md).
"""

from __future__ import annotations

# Read methods connected apps use most: dotted path -> top-level keys
RESPONSE_KEYS: dict[str, tuple[str, ...]] = {
	"api.get_folio": (
		"name", "property", "folio_type", "reservation", "guest", "guest_name",
		"status", "charges", "payments", "charges_total", "tax_total",
		"grand_total", "payments_total", "balance", "invoice_number",
	),
	"api.folio_invoice": (
		"folio", "property", "guest", "stay", "bill_to", "document", "lines",
		"summary_by_head", "tax_summary", "gst_summary", "statutory",
	),
	"api.property_locale": (
		"currency", "currency_symbol", "locale", "tax_label", "tax_id_label",
		"tax_rates", "payment_modes", "integrations", "fnb_tax_rate",
		"sells_alcohol",
	),
	"cashier.list_sessions": ("sessions", "business_date"),
	"cashier.session_report": (
		"name", "property", "cashier", "cashier_id", "user", "business_date",
		"status", "opening_float", "system_cash", "expected_cash",
		"counted_cash", "variance", "opened_at", "closed_at", "transactions",
		"totals",
	),
	"reports.manager_flash": (
		"date", "from_date", "total_rooms", "today", "mtd", "movement",
		"collections", "trend", "outlook",
	),
}

# Every webhook delivery wraps its data in this envelope (webhooks._queue)
WEBHOOK_ENVELOPE_KEYS: tuple[str, ...] = (
	"id", "event", "api_version", "created_at", "property", "data",
)

_RESERVATION = (
	"reservation", "status", "source", "channel", "ota_ref", "guest_name",
	"room_type", "room", "room_number", "check_in_date", "check_out_date",
	"nights", "adults", "children", "meal_plan", "rate_plan",
	"amount_after_tax", "currency", "company", "group_booking",
	"actual_check_in", "actual_check_out", "cancellation_number",
)

# event -> top-level keys of `data`. An event in webhooks.EVENTS that is not
# listed here is in the contract with no documented keys yet.
WEBHOOK_PAYLOAD_KEYS: dict[str, tuple[str, ...]] = {
	"reservation.created": _RESERVATION,
	"reservation.modified": (*_RESERVATION, "changes"),
	"reservation.cancelled": (*_RESERVATION, "changes"),
	"guest.checked_in": (*_RESERVATION, "changes"),
	"guest.checked_out": (*_RESERVATION, "changes"),
	"folio.posted": ("folio", "folio_type", "reservation", "charge", "balance"),
	"night_audit.closed": (
		"audit", "status", "business_date", "next_business_date",
		"room_charges_posted", "amount_posted", "no_shows_flagged", "exceptions",
	),
}
