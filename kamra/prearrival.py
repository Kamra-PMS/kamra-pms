"""Pre-arrival self check-in outreach: a plain automation (not an agent).

For properties that switch on "auto-send check-in links", each day this looks
at who is arriving in the next couple of days and hasn't started their self
check-in, and sends them their link - so they reach the desk already
registered and signed. When no messaging channel is connected the link is
simply generated and marked, so nothing is sent by surprise. Staff can always
send the link by hand from the arrivals board too."""

import frappe


def run_prearrival_outreach(horizon_days: int = 2):
	"""Daily pass across every active property that opted in."""
	from frappe.utils import add_days, nowdate

	from kamra.api import send_precheckin_link

	today = nowdate()
	horizon = add_days(today, horizon_days)
	sent = 0
	props = frappe.get_all(
		"Property", filters={"disabled": 0, "auto_send_checkin_links": 1},
		pluck="name")
	for prop in props:
		arrivals = frappe.get_all(
			"Reservation",
			filters={"property": prop, "status": "Confirmed",
			         "check_in_date": ("between", [today, horizon]),
			         "precheckin_status": ("not in", ["Submitted", "Verified"]),
			         "precheckin_link_sent": ("is", "not set")},
			pluck="name")
		for r in arrivals:
			try:
				send_precheckin_link(r, "WhatsApp")
				sent += 1
			except Exception:
				frappe.log_error(f"Pre-arrival outreach failed for {r}",
				                 "Pre-arrival agent")
	return {"processed": sent}
