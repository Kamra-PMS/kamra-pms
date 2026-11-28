"""Correct the meal plan locked on bookings quoted with tax inside the price.

With Rates Include Tax on, the quote took the F&B tax out of the meal price but
the booking's nights kept the whole price, which the folio then billed with the
tax on top. For each live booking, a night not yet on a bill is corrected to
the booking's own saved quote when what it holds is exactly that figure plus
the tax. The property's current setting is not consulted, so a booking quoted
before tax is left alone whatever the setting says now. Nights already billed
are not touched. Every booking changed, and every one that could not be checked
(no saved quote), is listed in the Error Log. Safe to run again.
"""

import json

import frappe
from frappe.utils import flt


def execute():
	from kamra.folio import _charge_posted, _fnb_gst

	rows = frappe.db.sql(
		"""SELECT n.name, n.stay_date, n.meal_amount, r.name AS reservation,
		          r.property, r.quote_snapshot
		   FROM `tabReservation Night Rate` n
		   JOIN `tabReservation` r ON r.name = n.parent
		    AND n.parenttype = 'Reservation'
		   WHERE n.meal_amount > 0
		     AND r.status IN ('Confirmed', 'Checked In', 'Held', 'Pending Payment')
		   ORDER BY r.name, n.stay_date""", as_dict=True)
	changed, unchecked = {}, set()
	for row in rows:
		if _charge_posted(row.reservation, "Meal Plan", str(row.stay_date)):
			continue
		quoted = _quoted_meal_per_night(row.quote_snapshot)
		if quoted is None:
			unchecked.add(row.reservation)
			continue
		tax = flt(_fnb_gst(row.property))
		held = flt(row.meal_amount)
		if not tax or abs(held - quoted * (1 + tax / 100)) > max(held * 1e-6, 1e-5):
			continue
		frappe.db.set_value("Reservation Night Rate", row.name, "meal_amount",
		                    round(quoted, 6), update_modified=False)
		changed.setdefault(row.reservation, []).append(
			f"{row.stay_date}: {held} -> {round(quoted, 6)}")
	if changed:
		frappe.log_error(
			title="Meal plan nights corrected (tax was counted twice)",
			message="\n".join(f"{name}: {'; '.join(lines)}"
			                  for name, lines in changed.items()))
	if unchecked:
		frappe.log_error(
			title="Meal plan nights to check by hand (no saved quote)",
			message="\n".join(sorted(unchecked)))


def _quoted_meal_per_night(snapshot: str | None) -> float | None:
	"""The meal plan before tax for one night, as the saved quote had it."""
	try:
		q = json.loads(snapshot or "")
		return float(q["meal_total"]) / max(len(q.get("nightly") or []), 1)
	except (ValueError, TypeError, KeyError):
		return None
