# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Reservation status machine (ADR-006) and inventory-live statuses.

Hotel desk bookings stay on Confirmed+. STR / Instant public bookings may use
Held and Pending Payment. Request-to-Book is stubbed via Property.booking_mode.
"""

from __future__ import annotations

# Statuses that consume sellable inventory (must stay in sync with
# kamra.siu.availability.LIVE_STATUSES).
LIVE_STATUSES = ("Confirmed", "Checked In", "Held", "Pending Payment")

NON_INVENTORY = (
	"Waitlist",
	"Inquiry",
	"Quoted",
	"Requested",
	"Cancelled",
	"No Show",
	"Checked Out",
)

# Allowed transitions. Missing edge = forbidden (except no-op same status).
# Cancelled / No Show are terminal from live states via dedicated APIs.
TRANSITIONS: dict[str, frozenset[str]] = {
	"Inquiry": frozenset({"Quoted", "Cancelled"}),
	"Quoted": frozenset({"Requested", "Held", "Pending Payment", "Confirmed", "Cancelled"}),
	"Requested": frozenset({"Held", "Pending Payment", "Confirmed", "Cancelled"}),
	"Held": frozenset({"Pending Payment", "Confirmed", "Cancelled"}),
	"Pending Payment": frozenset({"Confirmed", "Cancelled"}),
	"Waitlist": frozenset({"Confirmed", "Held", "Pending Payment", "Cancelled"}),
	"Confirmed": frozenset({"Checked In", "Cancelled", "No Show"}),
	"Checked In": frozenset({"Checked Out", "Cancelled"}),
	"Checked Out": frozenset(),
	"Cancelled": frozenset(),
	"No Show": frozenset(),
}

DEFAULT_HOLD_MINUTES = 120


def holds_inventory(status: str | None) -> bool:
	return (status or "") in LIVE_STATUSES


def assert_transition(old_status: str | None, new_status: str | None):
	"""Raise if moving between statuses is not allowed.

	Bypassed when ``frappe.flags.kamra_status_transition`` is set (APIs that
	own the transition) or during cancel via ``kamra_cancelling``.
	"""
	import frappe
	from frappe import _

	if frappe.flags.kamra_status_transition or frappe.flags.kamra_cancelling:
		return
	old = old_status or ""
	new = new_status or ""
	if not old or old == new:
		return
	allowed = TRANSITIONS.get(old)
	if allowed is None:
		return
	if new not in allowed:
		frappe.throw(
			_("Cannot move reservation from {0} to {1}.").format(old, new),
			title=_("Invalid status change"),
		)


def hold_expiry(minutes: int | None = None):
	from frappe.utils import add_to_date, now_datetime

	mins = int(minutes or DEFAULT_HOLD_MINUTES)
	if mins < 5:
		mins = 5
	return add_to_date(now_datetime(), minutes=mins)


def resolve_instant_status(
	*,
	advance_due: float,
	hold_minutes: int | None = None,
) -> tuple[str, object | None]:
	"""Instant-book initial status from payment terms.

	Pay-at-property (nothing due now) → Confirmed.
	Advance required → Pending Payment with hold expiry.
	"""
	if float(advance_due or 0) <= 0:
		return "Confirmed", None
	return "Pending Payment", hold_expiry(hold_minutes)


def lock_sius_for_booking(property: str, room_type: str) -> list[str]:
	"""Row-lock Sellable Units for this room type's competition group (ADR-007).

	Lock order: whole_property SIUs first, then individual/composite, by name,
	to avoid deadlocks across concurrent hybrid bookings.
	"""
	import frappe

	if not frappe.db.exists("DocType", "Sellable Unit"):
		return []
	units = frappe.get_all(
		"Sellable Unit",
		filters={"property": property, "room_type": room_type, "is_active": 1},
		fields=["name", "unit_kind", "competition_group"],
	)
	if not units:
		return []
	groups = list({u.competition_group for u in units if u.competition_group})
	siblings = frappe.get_all(
		"Sellable Unit",
		filters={"competition_group": ("in", groups), "is_active": 1}
		if groups
		else {"name": ("in", [u.name for u in units])},
		fields=["name", "unit_kind"],
	)
	# whole_property before individual/composite; then name for stability
	kind_rank = {"whole_property": 0, "composite": 1, "individual": 2}
	ordered = sorted(
		siblings,
		key=lambda r: (kind_rank.get(r.unit_kind, 9), r.name),
	)
	locked = []
	for row in ordered:
		frappe.db.get_value("Sellable Unit", row.name, "name", for_update=True)
		locked.append(row.name)
	return locked


def find_by_idempotency(property: str, key: str) -> str | None:
	import frappe

	if not key or not frappe.db.has_column("Reservation", "idempotency_key"):
		return None
	return frappe.db.get_value(
		"Reservation",
		{"property": property, "idempotency_key": key},
		"name",
	)


def expire_holds() -> dict:
	"""Release Held / Pending Payment reservations past hold_expires_on."""
	import frappe
	from frappe.utils import now_datetime

	if not frappe.db.has_column("Reservation", "hold_expires_on"):
		return {"expired": 0}
	now = now_datetime()
	rows = frappe.get_all(
		"Reservation",
		filters={
			"status": ("in", ["Held", "Pending Payment"]),
			"hold_expires_on": ("<", now),
		},
		pluck="name",
		limit=200,
	)
	expired = 0
	for name in rows:
		try:
			frappe.flags.kamra_status_transition = True
			frappe.flags.kamra_cancelling = True
			doc = frappe.get_doc("Reservation", name)
			doc.status = "Cancelled"
			doc.cancellation_reason = "Hold / payment window expired"
			doc.cancelled_on = now
			doc.hold_expires_on = None
			doc.save(ignore_permissions=True)
			expired += 1
		except Exception:
			frappe.log_error(title=f"Hold expiry failed for {name}")
		finally:
			frappe.flags.kamra_status_transition = False
			frappe.flags.kamra_cancelling = False
	# Scheduler commits at end of the job; do not frappe.db.commit() here.
	return {"expired": expired}
