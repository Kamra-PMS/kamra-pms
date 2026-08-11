# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Unit tests for reservation status machine + Instant status (ADR-006).

resolve_instant_status(advance_due=0) needs no frappe; advance path needs
hold_expiry which imports frappe.utils — skip that path without frappe.
"""

from kamra.reservation_state import (
	LIVE_STATUSES,
	TRANSITIONS,
	holds_inventory,
	resolve_instant_status,
)


def test_live_statuses_include_holds():
	assert "Held" in LIVE_STATUSES
	assert "Pending Payment" in LIVE_STATUSES
	assert "Requested" not in LIVE_STATUSES
	assert "Inquiry" not in LIVE_STATUSES


def test_instant_pay_at_property_confirms():
	status, expiry = resolve_instant_status(advance_due=0)
	assert status == "Confirmed"
	assert expiry is None


def test_confirmed_cannot_jump_to_inquiry():
	assert "Inquiry" not in TRANSITIONS["Confirmed"]


def test_pending_payment_can_confirm_or_cancel():
	assert TRANSITIONS["Pending Payment"] == frozenset({"Confirmed", "Cancelled"})


def test_holds_inventory_helper():
	assert holds_inventory("Held")
	assert holds_inventory("Confirmed")
	assert not holds_inventory("Requested")
	assert not holds_inventory("Quoted")
