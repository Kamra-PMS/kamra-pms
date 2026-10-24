"""Keep visitors out of the public demo while it rebuilds.

The nightly reset (kamra.scripts.reset_demo) wipes the demo and replays
weeks of history day by day; partway through, the hotel sits on a past
business date. During that window web requests get Frappe's maintenance
page instead of a half-built hotel.

The flag is a timestamp, not an on/off switch: past REBUILD_MINUTES it is
ignored, so a reset that dies halfway can never leave the demo shut.
Real tenants never set it; for them this is one cached default lookup.
"""

from __future__ import annotations

import frappe
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds

FLAG = "kamra_demo_rebuilding"
REBUILD_MINUTES = 20


def start_rebuild() -> None:
	frappe.db.set_default(FLAG, str(now_datetime()))
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- visitors must see the flag before the wipe starts


def end_rebuild() -> None:
	frappe.db.set_default(FLAG, "")
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- reopen the demo as soon as it is built


def rebuilding() -> bool:
	since = frappe.db.get_default(FLAG)
	if not since:
		return False
	try:
		age = time_diff_in_seconds(now_datetime(), get_datetime(since))
	except Exception:
		return False
	return 0 <= age < REBUILD_MINUTES * 60


def block_while_rebuilding() -> None:
	"""before_request: the maintenance page while the demo rebuilds."""
	if getattr(frappe.local, "request", None) is None:
		return
	if rebuilding():
		raise frappe.SessionStopped("The demo is resetting. Back in a minute.")
