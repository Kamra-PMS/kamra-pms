"""Anonymous install heartbeat and opt-in property registration (#657).

Heartbeat: once a day, a small anonymous POST to kamrapms.com so we can
count installs and live installs (check-ins in the last 30 days). On by
default, one click off in Settings → Usage reporting, and off whenever
`KAMRA_TELEMETRY=0`, `DO_NOT_TRACK=1` or site config `kamra_telemetry: 0`.
It sends exactly `payload()` - nothing about guests, the hotel's name,
domain, revenue or people - and fails silently: it never blocks the app.

Registration: a separate, explicit opt-in. The hotel sends its name, city,
country, room count and a contact email, and may tick "list us on
kamrapms.com". It can be edited or removed (removal asks the server to
delete it). Registration does not depend on the heartbeat switch.

State is install-wide (global defaults), not per property.
"""

from __future__ import annotations

import json
import os
import uuid

import frappe
from frappe import _
from frappe.utils import add_days, now_datetime

from kamra.authz import require_roles

BASE = "https://kamrapms.com/api"
TIMEOUT = 5  # seconds; never hold a worker longer
OFF_VALUES = ("0", "false", "no", "off")

ID_KEY = "kamra_install_id"
OFF_KEY = "kamra_telemetry_off"
REG_KEY = "kamra_registration"
REG_FIELDS = ("property_name", "city", "country", "room_count",
              "contact_email", "list_publicly")


def _url(kind: str) -> str:
	# site config kamra_telemetry_url overrides the base (staging, tests)
	return f"{(frappe.conf.get('kamra_telemetry_url') or BASE).rstrip('/')}/{kind}"


def disabled_by_config() -> bool:
	"""Off from the environment or site config, whatever the Settings switch says."""
	if os.environ.get("KAMRA_TELEMETRY", "").strip().lower() in OFF_VALUES:
		return True
	if os.environ.get("DO_NOT_TRACK", "").strip().lower() not in ("", *OFF_VALUES):
		return True
	conf = frappe.conf.get("kamra_telemetry")
	return conf is not None and str(conf).strip().lower() in OFF_VALUES


def enabled() -> bool:
	return not disabled_by_config() and frappe.db.get_default(OFF_KEY) != "1"


def install_id() -> str:
	"""A random id made once per install; never derived from the site or domain."""
	value = frappe.db.get_default(ID_KEY)
	if not value:
		value = str(uuid.uuid4())
		frappe.db.set_default(ID_KEY, value)
	return value


def _rooms_bucket(n: int) -> str:
	for top, label in ((0, "0"), (10, "1-10"), (50, "11-50"), (200, "51-200")):
		if n <= top:
			return label
	return "200+"


def _country() -> str | None:
	rows = frappe.db.sql(
		"""SELECT country, COUNT(*) n FROM `tabProperty`
		   WHERE IFNULL(country, '') != '' GROUP BY country ORDER BY n DESC LIMIT 1""")
	return rows[0][0] if rows else None


def payload() -> dict:
	"""Everything the heartbeat sends. Keep this the only source - Settings
	shows it, the docs list it, the test checks nothing else slips in."""
	from kamra import __version__ as kamra_version
	week_ago = add_days(now_datetime(), -7)
	return {
		"install_id": install_id(),
		"kamra_version": kamra_version,
		"frappe_version": frappe.__version__,
		"rooms": _rooms_bucket(frappe.db.count("Room")),
		"country": _country(),
		"deployment": "docker" if os.path.exists("/.dockerenv") else "bench",
		"checkins_last_7_days": bool(frappe.db.exists(
			"Reservation", {"actual_check_in": (">=", week_ago)})),
	}


def send_heartbeat() -> bool:
	"""Scheduler (daily). True when it was sent; any failure is swallowed."""
	if not enabled():
		return False
	try:
		import requests
		requests.post(_url("heartbeat"), json=payload(), timeout=TIMEOUT)
		return True
	except Exception:
		return False


def _registration() -> dict | None:
	raw = frappe.db.get_default(REG_KEY)
	try:
		return json.loads(raw) if raw else None
	except ValueError:
		return None


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager")
def telemetry_status() -> dict:
	"""For Settings → Usage reporting: the switch, why it is off, and the
	exact heartbeat payload ("see exactly what we send")."""
	return {
		"enabled": enabled(),
		"disabled_by_config": disabled_by_config(),
		"endpoint": _url("heartbeat"),
		"payload": payload(),
		"registration": _registration(),
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def set_telemetry(enabled: int = 1) -> dict:
	frappe.db.set_default(OFF_KEY, "0" if frappe.utils.cint(enabled) else "1")
	return telemetry_status()


def _send_registration(method: str, body: dict) -> bool:
	try:
		import requests
		r = requests.request(method, _url("register"), json=body, timeout=TIMEOUT)
		return r.status_code < 400
	except Exception:
		return False


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def save_registration(property_name: str, contact_email: str,
                      city: str = "", country: str = "", room_count: int = 0,
                      list_publicly: int = 0) -> dict:
	"""Register (or update) this property with kamrapms.com. Kept here too,
	so Settings can show and edit it. `sent` is False when kamrapms.com
	could not be reached; saving again retries."""
	from frappe.utils import cint, validate_email_address
	name = (property_name or "").strip()[:140]
	email = (contact_email or "").strip()
	if not name:
		frappe.throw(_("Enter the property name."))
	if not validate_email_address(email):
		frappe.throw(_("Enter a valid contact email."))
	reg = {
		"property_name": name, "city": (city or "").strip()[:140],
		"country": (country or "").strip()[:140],
		"room_count": max(cint(room_count), 0), "contact_email": email,
		"list_publicly": bool(cint(list_publicly)),
	}
	sent = _send_registration("POST", {"install_id": install_id(), **reg})
	frappe.db.set_default(REG_KEY, json.dumps(reg))
	return {"registration": reg, "sent": sent}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def remove_registration() -> dict:
	"""Withdraw the registration: ask kamrapms.com to delete it, and forget
	it here. If the delete does not reach the server, the registration is
	kept here (`sent` False) so the admin can try again."""
	if not _send_registration("DELETE", {"install_id": install_id()}):
		return {"registration": _registration(), "sent": False}
	frappe.db.set_default(REG_KEY, "")
	return {"registration": None, "sent": True}
