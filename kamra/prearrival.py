"""Pre-arrival self check-in outreach: a plain automation (not an agent).

For properties that switch on "auto-send check-in links", each day this looks
at who is arriving in the next couple of days and hasn't started their self
check-in, and sends them their link - so they reach the desk already
registered and signed. A property with no WhatsApp line connected is skipped:
there is nothing to send with, and an arrival is only marked once its link
has really gone out. Staff can always send the link by hand from the
arrivals board too."""

import frappe


def run_prearrival_outreach(horizon_days: int | None = None):
	"""Daily pass across every active property that opted in. Each property
	picks how far ahead to look (Settings -> Front Desk)."""
	from frappe.utils import add_days, nowdate

	from kamra.api import send_precheckin_link
	from kamra.settings import get_setting

	today = nowdate()
	sent = 0
	props = frappe.get_all(
		"Property", filters={"disabled": 0, "auto_send_checkin_links": 1},
		pluck="name")
	for prop in props:
		if not frappe.db.exists("Channel Provider Connection",
		                        {"property": prop, "channel": "WhatsApp", "active": 1}):
			continue
		days = horizon_days if horizon_days is not None else int(
			get_setting(prop, "prearrival_horizon_days"))
		horizon = add_days(today, days)
		arrivals = frappe.get_all(
			"Reservation",
			filters={"property": prop, "status": "Confirmed",
			         "check_in_date": ("between", [today, horizon]),
			         "precheckin_status": ("not in", ["Submitted", "Verified"]),
			         "precheckin_link_sent": ("is", "not set")},
			pluck="name")
		for r in arrivals:
			try:
				if send_precheckin_link(r, "WhatsApp").get("sent"):
					sent += 1
			except Exception:
				frappe.log_error(f"Pre-arrival outreach failed for {r}",
				                 "Pre-arrival agent")
	return {"processed": sent}
