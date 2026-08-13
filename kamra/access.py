# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Secure access-instruction release (ADR-012 / Phase 2B).

Access text is withheld until payment policy, deposit, and optional
pre-check-in gates pass.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime


def access_gates(reservation: str) -> dict:
	res = frappe.get_doc("Reservation", reservation)
	prop = frappe.get_cached_doc("Property", res.property)
	from kamra.deposit import deposit_satisfied

	gates = {
		"status_ok": res.status in ("Confirmed", "Checked In"),
		"deposit_ok": deposit_satisfied(res.name),
		"precheckin_ok": True,
	}
	if cint_prop(prop, "require_precheckin_for_access"):
		gates["precheckin_ok"] = (res.precheckin_status or "") in (
			"Submitted",
			"Verified",
		)
	gates["ready"] = all(gates.values())
	gates["access_released"] = bool(res.get("access_released"))
	return gates


def cint_prop(prop, field: str) -> int:
	return int(prop.get(field) or 0)


def release_access(reservation: str, *, force: int = 0) -> dict:
	res = frappe.get_doc("Reservation", reservation)
	gates = access_gates(reservation)
	if not force and not gates["ready"]:
		missing = [k for k, v in gates.items() if k.endswith("_ok") and not v]
		frappe.throw(
			_("Cannot release access yet. Failed gates: {0}").format(
				", ".join(missing)
			)
		)
	instructions = (
		frappe.db.get_value("Property", res.property, "access_instructions") or ""
	).strip()
	if not instructions:
		frappe.throw(_("Set access instructions on the Property first."))
	res.db_set("access_released", 1, update_modified=False)
	res.db_set("access_released_on", now_datetime(), update_modified=False)
	return {
		"reservation": res.name,
		"access_released": 1,
		"access_instructions": instructions,
		"gates": gates,
	}


def guest_access_info(token: str) -> dict:
	"""Public precheckin-token path for access instructions."""
	name = frappe.db.get_value("Reservation", {"precheckin_token": token})
	if not name:
		frappe.throw(_("Invalid link."))
	gates = access_gates(name)
	res = frappe.get_doc("Reservation", name)
	if not gates["ready"] or not res.access_released:
		return {
			"released": 0,
			"gates": gates,
			"message": "Access instructions are not available yet.",
		}
	text = frappe.db.get_value(
		"Property", res.property, "access_instructions"
	) or ""
	return {"released": 1, "access_instructions": text, "gates": gates}
