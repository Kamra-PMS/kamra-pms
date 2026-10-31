"""Today screen layout - which panels each person sees, and in what order.

Today is a set of widgets in two columns under an optional KPI strip.
Each person can hide, show and reorder them. Their layout is a user
default (frappe.defaults, per user, server side, so it follows them to
any device). A Hotel Admin can save a layout as the hotel's default
(a Property Setting row); people who never customised see that, and
everyone else sees the built-in layout, which is the classic Today.

Resolution: the user's own layout, else the property default, else the
built-in default. Every stored layout is cleaned on the way in and out:
unknown widgets are dropped, duplicates removed, and a widget added in
a later release shows up in its home column.
"""

import json

import frappe
from frappe import _

from kamra.authz import ADMIN, assert_property_access, require_perm

USER_KEY = "kamra_today_layout"
PROPERTY_KEY = "today_layout"

# id -> home column. "top" is the full-width strip above the columns.
WIDGETS = {
	"kpis": "top",
	"booking_requests": "left",
	"arrivals": "left",
	"departures": "left",
	"room_board": "right",
	"in_house": "right",
	"housekeeping": "right",
	"open_tasks": "right",
}
COLUMNS = ("top", "left", "right")

# the classic Today: nothing changes for anyone who never customises.
# Open tasks is new, so it starts hidden.
DEFAULT_LAYOUT = {
	"top": ["kpis"],
	"left": ["booking_requests", "arrivals", "departures"],
	"right": ["room_board", "in_house", "housekeeping", "open_tasks"],
	"hidden": ["open_tasks"],
}

# anyone who can open the desk may keep their own layout
_ANY_STAFF = ("Front Desk", "Night Auditor", "Housekeeping", "Finance",
              "Revenue Manager", "Kamra Agent")


def normalize(layout) -> dict:
	"""A clean layout from whatever was stored or sent. Never raises."""
	if isinstance(layout, str):
		try:
			layout = json.loads(layout or "{}")
		except (TypeError, ValueError):
			layout = {}
	if not isinstance(layout, dict):
		layout = {}
	seen: set = set()
	out: dict = {c: [] for c in COLUMNS}
	for col in COLUMNS:
		for wid in layout.get(col) or []:
			if not isinstance(wid, str) or wid not in WIDGETS or wid in seen:
				continue
			# the KPI strip stays on top; panels stay in the columns
			if (col == "top") != (WIDGETS[wid] == "top"):
				continue
			out[col].append(wid)
			seen.add(wid)
	hidden = [w for w in (layout.get("hidden") or [])
	          if isinstance(w, str) and w in WIDGETS]
	# a widget the stored layout does not know (added later): its home
	# column, visible unless the built-in default hides it
	for wid, home in WIDGETS.items():
		if wid not in seen:
			out[home].append(wid)
			if wid in DEFAULT_LAYOUT["hidden"] and wid not in hidden:
				hidden.append(wid)
	out["hidden"] = sorted(set(hidden), key=list(WIDGETS).index)
	return out


def _user_layout(user: str | None = None):
	raw = frappe.defaults.get_user_default(USER_KEY, user=user or frappe.session.user)
	return normalize(raw) if raw else None


def _property_layout(property: str | None):
	if not property:
		return None
	from kamra.settings import read_kv
	raw = read_kv(property, PROPERTY_KEY)
	return normalize(raw) if raw else None


def _is_admin() -> bool:
	return frappe.session.user == "Administrator" or bool(set(ADMIN) & set(frappe.get_roles()))


@frappe.whitelist()
@require_perm("Property", "use_console")
def get_today_layout(property: str | None = None) -> dict:
	"""The layout this person sees on Today, and where it came from
	("user", "property" or "default")."""
	if property:
		assert_property_access(property)
	prop = _property_layout(property)
	mine = _user_layout()
	if mine:
		layout, source = mine, "user"
	elif prop:
		layout, source = prop, "property"
	else:
		layout, source = normalize(DEFAULT_LAYOUT), "default"
	return {
		"layout": layout,
		"source": source,
		"property_default": prop or normalize(DEFAULT_LAYOUT),
		"built_in": normalize(DEFAULT_LAYOUT),
		"widgets": [{"id": k, "home": v} for k, v in WIDGETS.items()],
		"can_set_default": _is_admin(),
	}


@frappe.whitelist(methods=["POST"])
@require_perm("Property", "use_console")
def save_today_layout(layout, property: str | None = None) -> dict:
	"""Save this person's own Today layout."""
	clean = normalize(layout)
	frappe.defaults.set_user_default(USER_KEY, json.dumps(clean))
	return get_today_layout(property)


@frappe.whitelist(methods=["POST"])
@require_perm("Property", "use_console")
def reset_today_layout(property: str | None = None) -> dict:
	"""Drop this person's own layout: back to the hotel default."""
	frappe.defaults.clear_user_default(USER_KEY)
	return get_today_layout(property)


@frappe.whitelist(methods=["POST"])
@require_perm("Property", "configure")
def save_today_layout_default(property: str, layout=None) -> dict:
	"""Hotel Admin: the layout everyone at this property sees until they
	customise their own. Pass no layout to go back to the built-in one."""
	assert_property_access(property)
	if not frappe.db.exists("Property", property):
		frappe.throw(_("Unknown property."))
	from kamra.savings import log_action
	from kamra.settings import clear_cache, write_kv
	before = _property_layout(property)
	clean = normalize(layout) if layout else None
	write_kv(property, PROPERTY_KEY, clean)
	clear_cache(property)
	log_action("settings_changed", "Property", property, property=property,
	           rationale="Today layout default " + ("saved" if clean else "reset"),
	           before_snapshot=before, after_snapshot=clean)
	return get_today_layout(property)
