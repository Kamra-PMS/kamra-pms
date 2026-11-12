"""Guest offers - perks for repeat and high-value guests (#565).

An offer is a structured record: a guest, optionally one stay, a kind
(early check-in, late check-out, upgrade, complimentary service, discount),
what it is worth, and until when. It moves Proposed -> Approved (or
Declined) -> Delivered -> Redeemed, or Expired once valid_to passes.

- Anyone at the desk, or an AI agent, may propose. Only staff approve, on
  screen; an agent never approves, whatever the user behind it may do.
- The property's limits (Settings -> Front Desk -> Guest offers: kinds
  allowed, most per offer, most per month) are checked when the offer is
  proposed and again when it is approved. An offer over a limit can't be
  approved.
- Redeeming posts through the paths that already exist, never a new
  writer: a discount is an allowance (its own approval rules apply), an
  upgrade is a room move that keeps what the guest pays, a complimentary
  service is a zero-priced experience add-on, an early check-in or late
  check-out is the stay's own flag with an instruction for the desk.
  Redeeming twice does nothing the second time.
- offer.approved and offer.redeemed webhooks are sent from here, once.

Core stores the offer only; any wording sent to the guest belongs to
whoever delivers it.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, getdate, now_datetime, nowdate

from kamra.authz import require_roles

DOCTYPE = "Guest Offer"
KINDS = ("Early check-in", "Late check-out", "Upgrade", "Complimentary service",
         "Discount")
LIVE = ("Proposed", "Approved", "Delivered")
# offers that count against the month's total
COUNTED = ("Approved", "Delivered", "Redeemed")
APPROVERS = ("Hotel Admin", "Finance")

_FIELDS = ["name", "code", "property", "guest", "guest_name", "reservation", "kind",
           "value", "experience", "room_type", "valid_to", "reason", "status",
           "proposed_by", "proposed_on", "channel", "approved_by", "approved_on",
           "decision_note", "delivered_on", "redeemed_on", "redeemed_reservation",
           "redeemed_by", "redemption"]


def _is_agent() -> bool:
	from kamra.credit import _is_agent as is_agent
	return is_agent()


def _channel() -> str:
	from kamra.api import agent_channel
	return agent_channel() or "Desk"


def _may_approve(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return not _is_agent() and (user == "Administrator" or bool(
		set((*APPROVERS, "System Manager")) & set(frappe.get_roles(user))))


def limits(property: str) -> dict:
	"""The property's offer limits. 0 means no cap."""
	from kamra.settings import get_setting, list_setting
	kinds = [k for k in KINDS if k.casefold() in
	         {x.casefold() for x in list_setting(property, "offer_kinds")}]
	return {"kinds": kinds or list(KINDS),
	        "max_value": flt(get_setting(property, "offer_max_value")),
	        "max_month": flt(get_setting(property, "offer_max_month"))}


def month_total(property: str, exclude: str | None = None) -> float:
	"""What the offers approved this calendar month are worth."""
	filters = {"property": property, "status": ("in", COUNTED),
	           "approved_on": (">=", get_first_day(nowdate()))}
	if exclude:
		filters["name"] = ("!=", exclude)
	return flt(sum(frappe.get_all(DOCTYPE, filters=filters, pluck="value")))


def _over_limit(property: str, kind: str, value: float,
                offer: str | None = None, month: bool = False) -> str | None:
	"""Why this offer is over the property's limits, or None."""
	from kamra.localization import money_text
	lim = limits(property)
	if kind not in lim["kinds"]:
		return _("{0} offers are not allowed here (Settings, Front Desk, Guest offers).").format(_(kind))
	if lim["max_value"] and value > lim["max_value"] + 0.005:
		return _("An offer here can be worth at most {0}.").format(
			money_text(property, lim["max_value"]))
	if month and lim["max_month"]:
		used = month_total(property, exclude=offer)
		if used + value > lim["max_month"] + 0.005:
			return _("This month's offers would come to {0}, over the limit of {1}.").format(
				money_text(property, used + value), money_text(property, lim["max_month"]))
	return None


def _expire(property: str | None = None, name: str | None = None) -> None:
	"""Offers past valid_to that were never redeemed are Expired."""
	cond, params = "", {"today": nowdate(), "live": LIVE}
	if property:
		cond += " AND property = %(property)s"
		params["property"] = property
	if name:
		cond += " AND name = %(name)s"
		params["name"] = name
	frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- cond is built from constants; values are parameterized
		f"""UPDATE `tabGuest Offer` SET status = 'Expired', modified = NOW()
		   WHERE valid_to < %(today)s AND status IN %(live)s{cond}""", params)


def _row(doc) -> dict:
	row = {f: doc.get(f) for f in _FIELDS}
	row["value"] = flt(row["value"])
	for f in ("valid_to", "proposed_on", "approved_on", "delivered_on", "redeemed_on"):
		row[f] = str(row[f]) if row[f] else None
	row["redemption"] = json.loads(row["redemption"]) if row["redemption"] else None
	return row


def _payload(doc) -> dict:
	"""Webhook data: the offer, never the guest's contact details."""
	from kamra.webhooks import _currency
	row = _row(doc)
	return {"offer": row["name"], "code": row["code"], "status": row["status"],
	        "guest": row["guest"], "guest_name": row["guest_name"],
	        "reservation": row["reservation"], "kind": row["kind"],
	        "value": round(row["value"], 2), "currency": _currency(doc.property),
	        "experience": row["experience"], "room_type": row["room_type"],
	        "valid_to": row["valid_to"], "proposed_by": row["proposed_by"],
	        "channel": row["channel"], "approved_by": row["approved_by"],
	        "approved_on": row["approved_on"],
	        "redeemed_reservation": row["redeemed_reservation"],
	        "redeemed_on": row["redeemed_on"], "redemption": row["redemption"]}


def _log(action: str, doc, rationale: str, **kw):
	from kamra.savings import log_action
	log_action(action, DOCTYPE, doc.name, doc.property, rationale=rationale,
	           channel=_channel(), **kw)


def _save(doc):
	doc.flags.kamra_offer = True
	doc.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Kamra Agent")
def list_offers(property: str, status: str | None = None, guest: str | None = None,
                reservation: str | None = None) -> dict:
	"""Guest offers at a property, newest first. reservation lists the offers
	for that stay and the guest's offers not tied to a stay. Also returns
	the property's limits, what this month's approved offers come to, and
	can_approve for the caller (never true for an agent)."""
	from kamra.crs import assert_property_access
	assert_property_access(property)
	_expire(property)
	filters = {"property": property}
	or_filters = None
	if status:
		filters["status"] = status
	if guest:
		filters["guest"] = guest
	if reservation:
		res_guest = frappe.db.get_value("Reservation", reservation, "guest")
		filters["guest"] = res_guest or ""
		or_filters = [["reservation", "=", reservation], ["reservation", "is", "not set"]]
	rows = frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, fields=_FIELDS,
	                      order_by="creation desc", limit_page_length=200)
	return {"offers": [_row(r) for r in rows], "limits": limits(property),
	        "month_total": month_total(property), "can_approve": _may_approve()}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Revenue Manager", "Kamra Agent")
def propose_offer(property: str, guest: str, kind: str, value: float, valid_to: str,
                  reservation: str | None = None, experience: str | None = None,
                  room_type: str | None = None, reason: str | None = None,
                  idempotency_key: str | None = None) -> dict:
	"""Propose an offer for a guest. It waits as Proposed until staff approve
	it. Complimentary service names an experience; an upgrade names the
	room type. A retry with the same idempotency_key returns the first
	offer (idempotent_replay) instead of proposing it twice."""
	from kamra.crs import assert_property_access
	assert_property_access(property)
	key = (idempotency_key or "").strip() or None
	if key:
		existing = frappe.db.get_value(DOCTYPE, {"idempotency_key": key}, "name")
		if existing:
			doc = frappe.get_doc(DOCTYPE, existing)
			if (doc.property, doc.guest, doc.kind) != (property, guest, kind):
				frappe.throw(_("This idempotency_key ({0}) was already used for a different "
				               "offer.").format(key))
			return {**_row(doc), "idempotent_replay": True}
	if kind not in KINDS:
		frappe.throw(_("Pick one of: {0}.").format(", ".join(_(k) for k in KINDS)))
	if not frappe.db.exists("Guest", guest):
		frappe.throw(_("Guest {0} not found.").format(guest))
	value = round(flt(value), 2)
	if value < 0 or (kind == "Discount" and value <= 0):
		frappe.throw(_("Enter what the offer is worth."))
	if getdate(valid_to) < getdate(nowdate()):
		frappe.throw(_("The offer's last day is already past."))
	if reservation:
		r = frappe.db.get_value("Reservation", reservation, ["property", "guest"], as_dict=True)
		if not r or r.property != property or r.guest != guest:
			frappe.throw(_("That stay is not this guest's at this property."))
	if kind == "Complimentary service":
		if not experience or frappe.db.get_value(
				"Experience", experience, "property") != property:
			frappe.throw(_("Pick the experience this property gives at no charge."))
	else:
		experience = None
	if kind == "Upgrade":
		if not room_type or frappe.db.get_value("Room Type", room_type, "property") != property:
			frappe.throw(_("Pick the room type the stay is upgraded to."))
	else:
		room_type = None
	why = _over_limit(property, kind, value)
	if why:
		frappe.throw(why)
	doc = frappe.get_doc({
		"doctype": DOCTYPE, "code": "GO-" + frappe.generate_hash(length=8).upper(),
		"property": property, "guest": guest, "reservation": reservation or None,
		"kind": kind, "value": value, "experience": experience, "room_type": room_type,
		"valid_to": valid_to, "reason": (reason or "").strip()[:500] or None,
		"status": "Proposed", "proposed_by": frappe.session.user,
		"proposed_on": now_datetime(), "channel": _channel(), "idempotency_key": key,
	})
	doc.flags.kamra_offer = True
	doc.insert(ignore_permissions=True)
	from kamra.localization import money_text
	_log("offer_proposed", doc, f"{doc.code}: {kind} worth {money_text(property, value)} "
	     f"for {doc.guest_name or guest}", approval_status="Pending")
	return _row(doc)


@frappe.whitelist(methods=["POST"])
@require_roles(*APPROVERS)
def decide_offer(offer: str, approve: int = 1, note: str | None = None) -> dict:
	"""Approve or decline a proposed offer. Staff only, on screen: an AI agent
	can't decide, whatever the user behind it may do. Approving checks the
	property's limits again (kinds, most per offer, most per month) and
	refuses an offer over any of them. Approving sends offer.approved."""
	if _is_agent():
		frappe.throw(_("An AI agent can't approve or decline a guest offer. Ask a manager."),
		             frappe.PermissionError)
	if not _may_approve():
		frappe.throw(_("Approving guest offers needs: {0}.").format(
			", ".join(_(r) for r in APPROVERS)), frappe.PermissionError)
	_expire(name=offer)
	doc = frappe.get_doc(DOCTYPE, offer, for_update=True)
	if doc.status != "Proposed":
		frappe.throw(_("This offer is already {0}.").format(_(doc.status).lower()))
	if cint(approve):
		# the month's total is read under a property-wide lock so two
		# approvals at once can't both fit under the cap
		frappe.db.sql("SELECT name FROM `tabProperty` WHERE name = %s FOR UPDATE",
		              doc.property)
		why = _over_limit(doc.property, doc.kind, flt(doc.value), doc.name, month=True)
		if why:
			frappe.throw(why)
	doc.status = "Approved" if cint(approve) else "Declined"
	doc.approved_by = frappe.session.user
	doc.approved_on = now_datetime()
	doc.decision_note = (note or "").strip()[:500] or None
	_save(doc)
	_log("offer_" + doc.status.lower(), doc, f"{doc.code} {doc.status.lower()}"
	     + (f": {doc.decision_note}" if doc.decision_note else ""),
	     approver=frappe.session.user)
	if doc.status == "Approved":
		from kamra.webhooks import emit
		emit("offer.approved", doc.property, _payload(doc))
	return _row(doc)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def mark_offer_delivered(code: str) -> dict:
	"""Record that an approved offer reached the guest (the desk told them, or
	a messaging provider sent it after offer.approved)."""
	doc = _by_code(code)
	if doc.status == "Delivered":
		return {**_row(doc), "idempotent_replay": True}
	if doc.status != "Approved":
		frappe.throw(_("Only an approved offer can be delivered. This one is {0}.").format(
			_(doc.status).lower()))
	doc.status = "Delivered"
	doc.delivered_on = now_datetime()
	_save(doc)
	_log("offer_delivered", doc, f"{doc.code} delivered")
	return _row(doc)


def _by_code(code: str):
	name = frappe.db.get_value(DOCTYPE, {"code": (code or "").strip().upper()}, "name")
	if not name:
		frappe.throw(_("No guest offer with code {0}.").format(code))
	from kamra.crs import assert_property_access
	assert_property_access(frappe.db.get_value(DOCTYPE, name, "property"))
	_expire(name=name)
	return frappe.get_doc(DOCTYPE, name, for_update=True)


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def redeem_offer(code: str, reservation: str, room: str | None = None,
                 pin: str | None = None) -> dict:
	"""Use an approved (or delivered) offer on one of the guest's stays.

	- Discount: an allowance of the offer's value on the stay's open bill,
	  so the property's allowance approval still applies (the result may
	  say pending).
	- Upgrade: the stay moves to a free room of the offer's room type
	  (`room` picks one) and keeps what the guest pays. Refused when the
	  upgrade would cost more than the offer is worth.
	- Complimentary service: the experience is added to the stay at no
	  charge, and posted to the bill once it is open.
	- Early check-in / late check-out: the stay's flag is set, with an
	  instruction for the front desk.

	The code is its own idempotency key: redeeming a redeemed offer returns
	the first result (idempotent_replay) and posts nothing. Sends
	offer.redeemed once."""
	doc = _by_code(code)
	if doc.status == "Redeemed":
		return {**_row(doc), "idempotent_replay": True}
	if doc.status not in ("Approved", "Delivered"):
		frappe.throw(_("This offer is {0}; only an approved offer can be redeemed.").format(
			_(doc.status).lower()))
	res = frappe.get_doc("Reservation", reservation)
	if res.property != doc.property or res.guest != doc.guest:
		frappe.throw(_("That stay is not this guest's at this property."))
	if doc.reservation and doc.reservation != res.name:
		frappe.throw(_("This offer is for stay {0}.").format(doc.reservation))
	if res.status not in ("Confirmed", "Checked In"):
		frappe.throw(_("Only an upcoming or in-house stay can use an offer."))
	redemption = _REDEEM[doc.kind](doc, res, room=room, pin=pin)
	doc.status = "Redeemed"
	doc.redeemed_on = now_datetime()
	doc.redeemed_reservation = res.name
	doc.redeemed_by = frappe.session.user
	doc.redemption = json.dumps(redemption, default=str)
	_save(doc)
	_log("offer_redeemed", doc, f"{doc.code} ({doc.kind}) used on {res.name}")
	from kamra.webhooks import emit
	emit("offer.redeemed", doc.property, _payload(doc))
	return _row(doc)


def _redeem_discount(doc, res, pin=None, **_kw) -> dict:
	from kamra.api import post_allowance
	folio = frappe.db.get_value("Folio", {"reservation": res.name, "folio_type": "Guest",
	                                      "status": "Open"}, "name")
	if not folio:
		frappe.throw(_("A discount offer is used on the stay's open bill: redeem it "
		               "once the guest has checked in."))
	# an offer takes money off what the guest owes, never leaves them in credit
	if flt(frappe.db.get_value("Folio", folio, "balance")) < flt(doc.value) - 0.005:
		from kamra.localization import money_text
		frappe.throw(_("The bill is below the offer's {0}: redeem it once the stay's "
		               "charges are on the bill.").format(money_text(doc.property, doc.value)))
	out = post_allowance(folio, flt(doc.value), reason=_("Guest offer {0}").format(doc.code),
	                     pin=pin)
	return {"path": "allowance", "folio": folio, "serial": out.get("serial"),
	        "pending": bool(out.get("pending")), "request": out.get("request")}


def _redeem_upgrade(doc, res, room=None, **_kw) -> dict:
	from kamra import api
	if res.room_type == doc.room_type:
		frappe.throw(_("This stay is already in that room type."))
	if room:
		if frappe.db.get_value("Room", room, "room_type") != doc.room_type:
			frappe.throw(_("Room {0} is not the offer's room type.").format(room))
	else:
		free = [r["name"] for r in api.movable_rooms(res.name)
		        if r["room_type"] == doc.room_type and r["free"] and not r["current"]]
		if not free:
			frappe.throw(_("No room of that type is free for this stay."))
		room = free[0]
	pv = api.room_move_preview(res.name, room)
	if pv["difference"] > flt(doc.value) + 0.005:
		from kamra.localization import money_text
		frappe.throw(_("The upgrade costs {0} more, above what the offer is worth ({1}).").format(
			money_text(doc.property, pv["difference"]), money_text(doc.property, doc.value)))
	out = api.move_reservation(res.name, room, reason=_("Guest offer {0}").format(doc.code),
	                           rate_mode="source")
	return {"path": "room_move", "room": out["room"], "room_type": out["room_type"],
	        "upgrade_worth": round(max(flt(pv["difference"]), 0), 2),
	        "amount_after_tax": out["amount_after_tax"]}


def _redeem_service(doc, res, **_kw) -> dict:
	exp = frappe.db.get_value("Experience", doc.experience, "experience_name")
	res.append("addons", {"experience": doc.experience,
	                      "description": _("{0} (complimentary, offer {1})").format(exp, doc.code),
	                      "qty": 1, "rate": 0, "amount": 0, "gst_rate": 0})
	res.save(ignore_permissions=True)
	folio = frappe.db.get_value("Folio", {"reservation": res.name, "folio_type": "Guest",
	                                      "status": "Open"}, "name")
	if folio:
		from kamra.folio import _post_addons
		_post_addons(res, folio)
	return {"path": "addon", "experience": doc.experience, "folio": folio,
	        "posted": bool(folio)}


def _redeem_flag(doc, res, **_kw) -> dict:
	flag = "early_checkin" if doc.kind == "Early check-in" else "late_checkout"
	res.set(flag, 1)
	res.append("instructions", {"department": "Front Desk", "status": "Open",
	                            "instruction": _("{0} (complimentary, offer {1})").format(
		                            _(doc.kind), doc.code)})
	res.save(ignore_permissions=True)
	return {"path": "stay_flag", "flag": flag}


_REDEEM = {"Discount": _redeem_discount, "Upgrade": _redeem_upgrade,
           "Complimentary service": _redeem_service, "Early check-in": _redeem_flag,
           "Late check-out": _redeem_flag}
