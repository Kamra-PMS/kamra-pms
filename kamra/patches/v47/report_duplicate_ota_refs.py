"""Fill ota_live_key for live non-group stays.

Duplicate (property, ota_ref) rows are reported and left in place. Only the
oldest of each set gets the key, so the unique index can be added and a new
delivery still collides with that stay. The others keep a blank key and are
not deleted.
"""

import frappe

from kamra.kamra.doctype.reservation.reservation import ota_live_key


def execute():
	if not frappe.db.has_column("Reservation", "ota_live_key"):
		return
	rows = frappe.db.sql(
		"""SELECT property, ota_ref,
		          GROUP_CONCAT(name ORDER BY creation SEPARATOR ',') AS names,
		          COUNT(*) AS n
		   FROM `tabReservation`
		   WHERE IFNULL(ota_ref, '') != ''
		     AND status != 'Cancelled'
		     AND IFNULL(group_booking, '') = ''
		   GROUP BY property, ota_ref
		   HAVING n > 1""",
		as_dict=True)
	extras = set()
	reported = []
	for row in rows:
		names = [n for n in (row.names or "").split(",") if n]
		if len(names) < 2:
			continue
		keeper, rest = names[0], names[1:]
		extras.update(rest)
		reported.append(f"{row.property} {row.ota_ref}: kept {keeper}, left {', '.join(rest)}")
		frappe.db.set_value("Reservation", keeper, "ota_live_key",
		                    ota_live_key(row.property, row.ota_ref),
		                    update_modified=False)
		for name in rest:
			frappe.db.set_value("Reservation", name, "ota_live_key", None,
			                    update_modified=False)
	singles = frappe.db.sql(
		"""SELECT name, property, ota_ref FROM `tabReservation`
		   WHERE IFNULL(ota_ref, '') != ''
		     AND status != 'Cancelled'
		     AND IFNULL(group_booking, '') = ''
		     AND IFNULL(ota_live_key, '') = ''""",
		as_dict=True)
	for row in singles:
		if row.name in extras:
			continue
		frappe.db.set_value("Reservation", row.name, "ota_live_key",
		                    ota_live_key(row.property, row.ota_ref),
		                    update_modified=False)
	# Cancelled stays and group rooming lists do not claim the key.
	frappe.db.sql(
		"""UPDATE `tabReservation`
		   SET ota_live_key = NULL
		   WHERE ota_live_key IS NOT NULL
		     AND (status = 'Cancelled' OR IFNULL(group_booking, '') != '')""")
	if reported:
		message = "Duplicate OTA references were left in place (not deleted):\n" + "\n".join(reported)
		print(message)
		frappe.log_error(title="Duplicate OTA references left in place", message=message)
