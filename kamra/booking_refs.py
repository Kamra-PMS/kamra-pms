"""Resolve the room type / meal plan / rate plan a caller names to its ID.

Records are named ``{property}-{code}`` (e.g. ``Kamra Demo Palace-DLX``),
but an AI agent (MCP or the in-app copilot) talks the way staff do:
"Deluxe", "breakfast", "BAR". Every booking and quote endpoint runs its
arguments through here, so the desk, REST, MCP and the copilot share one
resolver and one set of rules:

1. an exact ID that belongs to this property;
2. else an exact code (case-insensitive) at this property;
3. else an exact display name (case-insensitive) at this property.

Anything else - unknown, ambiguous, or another property's record - is
refused with the list of valid options. The resolver never guesses
(no prefix or fuzzy matching): a wrong room type is a wrong price.
"""

from __future__ import annotations

import frappe

# doctype -> (human label, code field, display-name field)
_KINDS: dict[str, tuple[str, str, str]] = {
	"Room Type": ("room type", "room_type_code", "room_type_name"),
	"Meal Plan": ("meal plan", "code", "label"),
	"Rate Plan": ("rate plan", "code", "rate_plan_name"),
}


def _norm(value) -> str:
	return " ".join(str(value or "").split()).casefold()


def _options(doctype: str, property: str, code_f: str, name_f: str) -> list[dict]:
	return frappe.get_all(
		doctype,
		filters={"property": property, "disabled": 0},
		fields=["name", f"{code_f} as code", f"{name_f} as title"],
		order_by="name asc",
	)


def _describe(rows: list[dict]) -> str:
	return "; ".join(
		f"{r.title or r.code} (code {r.code}, id {r.name})" if r.code
		else f"{r.title} (id {r.name})"
		for r in rows
	) or "none configured"


def resolve(doctype: str, property: str, value: str | None,
            *, required: bool = False) -> str | None:
	"""Return the record ID for ``value`` at ``property``, or refuse.

	Empty values return None (an optional meal / rate plan) unless
	``required``. Raises frappe.ValidationError with the valid options when
	the value is unknown or ambiguous.
	"""
	label, code_f, name_f = _KINDS[doctype]
	raw = str(value or "").strip()
	if not raw:
		if required:
			frappe.throw(f"A {label} is required.", frappe.ValidationError)
		return None

	# 1. exact ID, scoped to the property (an ID stays valid even if the
	#    record was disabled later - the desk may be editing an old stay)
	owner = frappe.db.get_value(doctype, raw, "property")
	if owner == property:
		return raw

	rows = _options(doctype, property, code_f, name_f)
	wanted = _norm(raw)
	# 2. code, then 3. display name - each must match exactly one record
	for field, what in (("code", "code"), ("title", "name")):
		hits = [r for r in rows if r.get(field) and _norm(r.get(field)) == wanted]
		if len(hits) == 1:
			return hits[0].name
		if len(hits) > 1:
			frappe.throw(
				f'"{raw}" matches more than one {label} {what} at {property}: '
				f"{_describe(hits)}. Pass the id instead.",
				frappe.ValidationError,
			)

	if owner:
		problem = f'{label.capitalize()} "{raw}" belongs to another property, not {property}.'
	else:
		problem = f'Unknown {label} "{raw}" at {property}.'
	frappe.throw(
		f"{problem} Valid {label}s: {_describe(rows)}. "
		"Pass the id, the code, or the exact name.",
		frappe.ValidationError,
	)
	return None  # unreachable: frappe.throw raises


def resolve_room_type(property: str, value: str | None) -> str:
	return resolve("Room Type", property, value, required=True)


def resolve_meal_plan(property: str, value: str | None) -> str | None:
	return resolve("Meal Plan", property, value)


def resolve_rate_plan(property: str, value: str | None) -> str | None:
	return resolve("Rate Plan", property, value)
