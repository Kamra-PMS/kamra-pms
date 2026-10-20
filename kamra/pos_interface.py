"""External POS interface - room charges from a third-party point of sale.

A restaurant, spa or bar running its own POS (not Kamra's) needs two calls:

    pos_room_lookup        is this room in house, and who is in it?
    pos_post_room_charge   put this ticket on their bill

Both are for a service user holding the "POS Integrator" role (or Kamra
Agent), limited to its property with a Property User Permission, calling
with its API key. Nothing here is a second way to bill: the charge goes
through api.post_stay_charge - the same path as the desk, housekeeping and
the AI agent - so the billing rules pick the folio, tax comes from the
country pack, and alcohol never lands on a Company or Group folio.

Every ticket is posted at most once: `ticket_id` (the POS's own check
number) is the idempotency key per property. Retrying a ticket returns the
first posting; reusing a ticket number for a different charge is refused.
"""

from __future__ import annotations

import hashlib

import frappe
from frappe import _
from frappe.utils import cint, flt

from kamra.authz import act_as, require_roles
from kamra.install import AGENT_EMAIL

POS_INTEGRATOR = "POS Integrator"
ROLES = (POS_INTEGRATOR, "Kamra Agent")
CHARGE = "External POS Charge"
# what an outlet sells; room nights, fees and allowances stay with the hotel
CHARGE_TYPES = ("Food & Beverage", "Minibar", "Laundry", "Spa", "Misc")


def _room_number(room: str | None) -> str | None:
	if not room:
		return None
	return frappe.db.get_value("Room", room, "room_number") or room.split("-")[-1]


def _resolve_room(property: str, room: str) -> str | None:
	"""Accept the Room id or the number printed on the door."""
	if frappe.db.exists("Room", room) and \
	   frappe.db.get_value("Room", room, "property") == property:
		return room
	return frappe.db.get_value("Room", {"property": property,
	                                    "room_number": str(room).strip()}, "name")


@frappe.whitelist()
@require_roles(*ROLES)
def pos_room_lookup(property: str, room: str | None = None,
                    last_name: str | None = None) -> list:
	"""In-house stays matching a room number and/or the guest's last name.
	Only checked-in guests, only this property, only what a cashier needs to
	confirm the charge: room, guest name, reservation and departure date.
	Ask with a room or a last name (2+ letters) - never the whole list."""
	last_name = (last_name or "").strip()
	if not room and len(last_name) < 2:
		frappe.throw(_("Look up by room number or by the guest's last name (2+ letters)."))
	filters = {"property": property, "status": "Checked In"}
	if room:
		name = _resolve_room(property, room)
		if not name:
			return []
		filters["room"] = name
	if last_name:
		filters["guest_name"] = ("like", f"%{last_name}%")
	rows = frappe.get_all("Reservation", filters=filters,
	                      fields=["name", "room", "guest_name", "check_out_date",
	                              "company"],
	                      order_by="room asc", limit=20)
	return [{
		"reservation": r.name,
		"room": r.room,
		"room_number": _room_number(r.room),
		"guest_name": r.guest_name,
		"check_out_date": str(r.check_out_date) if r.check_out_date else None,
		# so the POS can say "company pays food, drinks go to the guest"
		"corporate": bool(r.company),
	} for r in rows]


def _charge_name(property: str, ticket_id: str) -> str:
	"""One record per (property, ticket): the primary key itself refuses a
	second posting, even from two requests racing each other."""
	digest = hashlib.sha256(f"{property}\n{ticket_id}".encode()).hexdigest()[:24]
	return f"EPC-{digest}"


def _result(rec, duplicate: bool) -> dict:
	return {"ok": True, "duplicate": duplicate, "ticket_id": rec.ticket_id,
	        "reservation": rec.reservation, "room_number": _room_number(rec.room),
	        "folio": rec.folio,
	        "folio_type": frappe.db.get_value("Folio", rec.folio, "folio_type"),
	        "amount": flt(rec.amount), "balance": flt(rec.balance_after)}


@frappe.whitelist(methods=["POST"])
@require_roles(*ROLES)
def pos_post_room_charge(property: str, ticket_id: str, amount: float,
                         description: str, room: str | None = None,
                         reservation: str | None = None,
                         charge_type: str = "Food & Beverage",
                         is_alcohol: int = 0, tax_rate: float = 0,
                         outlet_name: str | None = None) -> dict:
	"""Post one POS ticket to an in-house guest's bill.

	`ticket_id` is the idempotency key: the same ticket again returns the
	first posting with duplicate=true. Name the stay by room (number or id)
	and/or reservation. The billing rules choose the folio; anything with
	alcohol (is_alcohol=1) always goes to the guest's own folio, never the
	company's. Tax is the hotel's rule for the charge type, not the POS's."""
	ticket_id = (ticket_id or "").strip()
	if not ticket_id or len(ticket_id) > 140:
		frappe.throw(_("ticket_id is required (the POS check number, up to 140 characters)."))
	if charge_type not in CHARGE_TYPES:
		frappe.throw(_("charge_type must be one of: {0}.").format(", ".join(CHARGE_TYPES)))
	description = (description or "").strip()
	if not description:
		frappe.throw(_("Describe the charge (e.g. 'Rooftop bar - check 1042')."))
	is_alcohol = 1 if cint(is_alcohol) else 0
	# the posting path checks this again; checking first means a bad ticket
	# never claims its ticket number
	from kamra.api import _check_charge_amount_and_tax
	_check_charge_amount_and_tax(property, amount, tax_rate)
	amount = flt(amount)

	key = _charge_name(property, ticket_id)
	if frappe.db.exists(CHARGE, key):
		rec = frappe.get_doc(CHARGE, key)
		same = (abs(flt(rec.amount) - amount) < 0.005
		        and (not reservation or reservation == rec.reservation))
		if not same:
			frappe.throw(_("POS ticket {0} was already posted with a different "
			               "amount or stay. Use a new ticket number.").format(ticket_id))
		return _result(rec, duplicate=True)

	room_id = _resolve_room(property, room) if room else None
	if room and not room_id:
		frappe.throw(_("Room {0} is not a room of this property.").format(room))
	from kamra.pos import _in_house_stay
	room_id, reservation = _in_house_stay(property, room_id, reservation)
	if not reservation:
		frappe.throw(_("Name the room or the reservation to charge."))

	from kamra.settings import get_setting
	limit = flt(get_setting(property, "pos_room_charge_limit"))
	if limit and amount > limit:
		frappe.throw(_("{0} is over this property's limit for one POS room "
		               "charge ({1}). Settle it at the outlet or ask the front "
		               "desk.").format(amount, limit))

	# claim the ticket first: a concurrent retry now waits on this row and
	# then sees the duplicate, instead of posting a second time
	rec = frappe.get_doc({
		"doctype": CHARGE, "name": key, "property": property,
		"ticket_id": ticket_id, "outlet_name": (outlet_name or "").strip()[:140] or None,
		"posted_by": frappe.session.user, "reservation": reservation,
		"room": room_id, "charge_type": charge_type,
		"description": description[:140], "amount": amount,
		"is_alcohol": is_alcohol,
	})
	try:
		rec.insert(ignore_permissions=True)  # role + property checked above
	except frappe.DuplicateEntryError:
		frappe.clear_messages()
		return _result(frappe.get_doc(CHARGE, key), duplicate=True)

	# the one write path; the integrator was authorised above and is limited
	# to room-chargeable types, the same pattern as housekeeping's minibar
	from kamra.api import post_stay_charge
	text = f"{description} (POS {ticket_id})"[:140]
	with act_as(AGENT_EMAIL):
		out = post_stay_charge(reservation, charge_type, text, amount,
		                       gst_rate=flt(tax_rate), is_alcohol=is_alcohol)
	rec.db_set({"folio": out.get("folio"), "balance_after": flt(out.get("balance"))},
	           update_modified=False)

	from kamra.savings import log_action
	log_action("pos_room_charge", "Folio", out.get("folio"), property,
	           rationale=f"{outlet_name or 'External POS'} ticket {ticket_id}: "
	                     f"{charge_type} {amount} -> {out.get('folio')}"
	                     f" by {frappe.session.user}",
	           channel="API")
	return _result(rec, duplicate=False)
