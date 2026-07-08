"""Pre-arrival concierge (MAYA): get guests checked in before they arrive.

Every day MAYA looks at who is arriving in the next couple of days and hasn't
started their self check-in, and sends them their link - so they reach the
desk already registered, signed, and ready for their key. When no messaging
channel is connected the link is simply generated and marked, so nothing is
sent by surprise; connect HeyKoala WhatsApp and the same pass starts delivering
it. This answers "which guests get a link": every upcoming arrival, without a
staff member remembering to send it."""

import frappe


def run_prearrival_outreach(horizon_days: int = 2):
	"""MAYA's daily pass across every active property."""
	from frappe.utils import add_days, nowdate
	from kamra.api import send_precheckin_link

	today = nowdate()
	horizon = add_days(today, horizon_days)
	sent = 0
	for prop in frappe.get_all("Property", filters={"disabled": 0}, pluck="name"):
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
