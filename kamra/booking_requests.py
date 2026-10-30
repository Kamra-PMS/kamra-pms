# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Request to Book: the staff inbox and the accept / decline decision.

A stay lands as Requested from the booking engine in Request-to-Book mode
(public_api.book) or from an OTA sale the channel manager could not place
(retained as a request for staff to resolve). A Requested stay does NOT
hold inventory (reservation_state.NON_INVENTORY): the room is only taken
when someone accepts it, and accept re-runs every inventory rule a fresh
booking runs - overlap guard, villa <-> room lockout, category capacity and
group-block holds. So a request can find its dates sold by then; accept
then refuses and the request is declined instead.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate

from kamra.authz import require_perm

# an existing cancellation reason, so reports and the cancellation letter
# need nothing new; the note carries "Request declined: <why>"
DECLINE_REASON = "Other"


def _availability(res) -> dict:
	"""Can this request be accepted right now? {rooms_free, can_accept,
	blocker}. Read-only: the same checks accept enforces."""
	from kamra.api import available_rooms
	from kamra.kamra.doctype.reservation.reservation import (
		uses_member_rooms, villa_lockout_conflict)

	ci, co = str(res.check_in_date), str(res.check_out_date)
	if getdate(ci) < getdate(nowdate()):
		return {"rooms_free": 0, "can_accept": False,
		        "blocker": _("The arrival date has passed.")}
	conflict = villa_lockout_conflict(res.property, res.room_type, ci, co,
	                                  exclude=res.name)
	if conflict:
		return {"rooms_free": 0, "can_accept": False,
		        "blocker": _("Villa lockout: {0} is booked for these dates.").format(
			        conflict)}
	if uses_member_rooms(res.property, res.room_type):
		return {"rooms_free": 1, "can_accept": True, "blocker": None}
	free = available_rooms(res.property, res.room_type, ci, co,
	                       group_booking=res.get("group_booking"))
	if not free:
		return {"rooms_free": 0, "can_accept": False,
		        "blocker": _("No {0} room is free for these dates.").format(
			        frappe.db.get_value("Room Type", res.room_type,
			                            "room_type_name") or res.room_type)}
	return {"rooms_free": len(free), "can_accept": True, "blocker": None}


@frappe.whitelist()
@require_perm("Reservation", "handle_stays")
def booking_requests(property: str):
	"""Pending Request-to-Book stays (status Requested), oldest first, each
	with whether it can be accepted right now. Requests hold no inventory
	until accepted - rooms_free is live availability, not a reservation."""
	rows = frappe.get_all(
		"Reservation",
		filters={"property": property, "status": "Requested"},
		fields=["name", "property", "guest", "guest_name", "room_type",
		        "check_in_date",
		        "check_out_date", "nights", "adults", "children", "source",
		        "channel", "ota_ref", "amount_after_tax", "special_requests",
		        "group_booking", "creation"],
		order_by="creation asc",
	)
	rt_names = {}
	for r in rows:
		if r.room_type not in rt_names:
			rt_names[r.room_type] = frappe.db.get_value(
				"Room Type", r.room_type, "room_type_name") or r.room_type
		r["room_type_name"] = rt_names[r.room_type]
		g = frappe.db.get_value("Guest", r.guest, ["phone", "email"],
		                        as_dict=True) or {}
		r["phone"] = g.get("phone")
		r["email"] = g.get("email")
		r["check_in_date"] = str(r.check_in_date)
		r["check_out_date"] = str(r.check_out_date)
		r["creation"] = str(r.creation)
		r.update(_availability(r))
	return {"holds_inventory": False, "count": len(rows), "requests": rows}


def _load_request(reservation: str):
	res = frappe.get_doc("Reservation", reservation)
	if res.status != "Requested":
		frappe.throw(
			_("{0} is {1}, not a pending request.").format(res.name, res.status),
			title=_("Not a booking request"))
	return res


@frappe.whitelist(methods=["POST"])
@require_perm("Reservation", "handle_stays")
def accept_booking_request(reservation: str, room: str | None = None):
	"""Accept a Request-to-Book stay: confirm it and take the inventory,
	assigning a free room of its type (or `room`). Every booking rule runs
	again - double-booking guard, villa <-> room lockout, category capacity,
	group-block holds - so a request whose dates sold in the meantime is
	refused with the reason; decline it instead."""
	from kamra.api import agent_channel, available_rooms
	from kamra.kamra.doctype.reservation.reservation import (
		InventoryRefused, uses_member_rooms, villa_lockout_conflict)
	from kamra.reservation_state import lock_sius_for_booking

	res = _load_request(reservation)
	ci, co = str(res.check_in_date), str(res.check_out_date)
	if getdate(ci) < getdate(nowdate()):
		frappe.throw(_("The arrival date of {0} has passed - decline it.").format(
			res.name), title=_("Request expired"))
	lock_sius_for_booking(res.property, res.room_type)
	# serialize against a booking of the same category landing right now
	frappe.db.get_value("Room Type", res.room_type, "name", for_update=True)

	conflict = villa_lockout_conflict(res.property, res.room_type, ci, co,
	                                  exclude=res.name)
	if conflict:
		frappe.throw(
			_("Can't accept {0}: the villa and its rooms can't both be sold, "
			  "and {1} is already booked for these dates. Decline the "
			  "request or offer other dates.").format(res.name, conflict),
			title=_("No inventory left"), exc=InventoryRefused)

	room = room or res.room
	if not room and not uses_member_rooms(res.property, res.room_type):
		free = available_rooms(res.property, res.room_type, ci, co,
		                       group_booking=res.get("group_booking"))
		if not free:
			frappe.throw(
				_("Can't accept {0}: no {1} room is free for {2} to {3} any "
				  "more. Decline the request, or move it to another room "
				  "type first.").format(
					res.name,
					frappe.db.get_value("Room Type", res.room_type,
					                    "room_type_name") or res.room_type,
					ci, co),
				title=_("No inventory left"), exc=InventoryRefused)
		room = free[0]["name"]

	res.room = room or None
	res.status = "Confirmed"
	res.hold_expires_on = None
	frappe.flags.kamra_status_transition = True
	try:
		# validate() re-runs the overlap guard, villa lockout and capacity
		# (with group holds): the request takes inventory only if it is there
		res.save(ignore_permissions=True)
	finally:
		frappe.flags.kamra_status_transition = False

	try:
		from kamra.deposit import ensure_deposit_for_reservation
		ensure_deposit_for_reservation(res)
	except Exception:
		frappe.log_error(title="Security deposit ensure on accept failed")

	from kamra.savings import log_action
	room_no = (res.room or "").split("-")[-1]
	log_action(
		"booking_request_accepted", "Reservation", res.name, res.property,
		minutes_saved=3,
		rationale=f"Accepted request {res.name} for {res.guest_name}: "
		          f"{res.room_type} {ci}→{co}"
		          + (f", room {room_no}" if room_no else ""),
		channel=agent_channel() or "Desk",
	)
	# WhatsApp confirmation goes out from Reservation.on_update
	# (Requested -> Confirmed); email here when the property sends mail
	notified = _notify_guest(res, accepted=True)
	return {"reservation": res.name, "status": res.status, "room": res.room,
	        "notified": notified}


@frappe.whitelist(methods=["POST"])
@require_perm("Reservation", "handle_stays")
def decline_booking_request(reservation: str, reason: str):
	"""Decline a Request-to-Book stay with a reason (required). The stay is
	cancelled with no cancellation fee - a request was never confirmed - and
	any room it pointed at is freed. The guest is told by WhatsApp / email
	when the property has them set up; otherwise the decline is just logged.
	An OTA request must also be declined on the OTA's side."""
	from kamra.api import agent_channel
	from frappe.model.naming import make_autoname

	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Give a reason for declining the request."),
		             title=_("Reason required"))
	res = _load_request(reservation)
	res.status = "Cancelled"
	res.cancellation_reason = DECLINE_REASON
	res.cancellation_note = f"Request declined: {reason}"[:1000]
	res.cancellation_number = make_autoname("CXL-.YYYY.-.#####")
	res.cancellation_fee = 0
	res.cancelled_on = now_datetime()
	res.room = None
	frappe.flags.kamra_cancelling = True
	try:
		res.save(ignore_permissions=True)
	finally:
		frappe.flags.kamra_cancelling = False

	notified = _notify_guest(res, accepted=False, reason=reason)
	from kamra.savings import log_action
	log_action(
		"booking_request_declined", "Reservation", res.name, res.property,
		minutes_saved=3,
		rationale=f"Declined request {res.name} for {res.guest_name}: {reason}"
		          + (f" · guest told by {', '.join(notified)}" if notified
		             else " · guest not notified (no WhatsApp / email set up)"),
		channel=agent_channel() or "Desk",
	)
	out = {"reservation": res.name, "status": res.status,
	       "cancellation_number": res.cancellation_number, "fee": 0,
	       "notified": notified}
	if float(res.get("advance_paid") or 0) > 0:
		out["refund_due"] = float(res.advance_paid)
	if res.source == "OTA":
		out["note"] = _("Decline it on the OTA's extranet too ({0}).").format(
			res.get("channel") or "OTA")
	return out


# ---------------------------------------------------------------------------
# Guest notification - best-effort, never blocks the decision
# ---------------------------------------------------------------------------


def _email_ready() -> bool:
	return bool(frappe.db.exists(
		"Email Account", {"enable_outgoing": 1, "default_outgoing": 1}))


def _notify_guest(res, *, accepted: bool, reason: str | None = None) -> list[str]:
	"""Tell the guest by the paths the property has configured. Returns the
	channels used. OTA guests are the OTA's to message - skipped."""
	if res.source == "OTA":
		return []
	g = frappe.db.get_value("Guest", res.guest, ["phone", "email"],
	                        as_dict=True) or {}
	prop_name = frappe.db.get_value(
		"Property", res.property, "property_name") or res.property
	ci, co = str(res.check_in_date), str(res.check_out_date)
	if accepted:
		subject = _("Your stay at {0} is confirmed").format(prop_name)
		body = _("Good news, {0}: {1} accepted your booking request for "
		         "{2} to {3}. Reference {4}.").format(
			res.guest_name or _("Guest"), prop_name, ci, co, res.name)
	else:
		subject = _("Your booking request at {0}").format(prop_name)
		body = _("Sorry, {0}: {1} can't accept your booking request for "
		         "{2} to {3}. Reason: {4}. Reference {5}.").format(
			res.guest_name or _("Guest"), prop_name, ci, co, reason, res.name)
	used = []
	# WhatsApp: the accept confirmation already goes out as the booking
	# confirmation template (Reservation.on_update); a decline goes out here
	if not accepted and g.get("phone"):
		from kamra import whatsapp
		if whatsapp.has_connection(res.property):
			frappe.enqueue(
				"kamra.agents_channels.send_outbound", queue="short",
				enqueue_after_commit=True, property=res.property,
				channel="WhatsApp", to=g["phone"], body=body)
			used.append("whatsapp")
	if g.get("email") and _email_ready():
		try:
			frappe.sendmail(
				recipients=[g["email"]], subject=subject,
				message=frappe.utils.escape_html(body),
				reference_doctype="Reservation", reference_name=res.name)
			used.append("email")
		except Exception:
			frappe.log_error(title=f"Booking request email failed: {res.name}")
	return used

