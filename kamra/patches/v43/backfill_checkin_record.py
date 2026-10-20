"""Guided check-in adds a check-in record to every stay: who checked the
guest in and when, who assigned the room, who issued the keys, and whether
the guest may charge outlets to the room.

Existing stays keep working exactly as before:
  - room charges stay allowed (the column defaults to 1; rows that came in
    NULL are set to 1 so POS keeps posting to rooms already in house);
  - checked_in_at copies the actual check-in time, and checked_in_by is
    taken from the activity log row that recorded the check-in, where one
    exists. Nothing is guessed.

Idempotent: only empty values are filled."""

import frappe


def execute():
	if not frappe.db.has_column("Reservation", "room_charges_allowed"):
		return
	frappe.db.sql(
		"""update `tabReservation` set room_charges_allowed = 1
		   where room_charges_allowed is null""")
	frappe.db.sql(
		"""update `tabReservation` set checked_in_at = actual_check_in
		   where checked_in_at is null and actual_check_in is not null""")
	if frappe.db.table_exists("Agent Action Log"):
		frappe.db.sql(
			"""update `tabReservation` r
			   join (
			     select reference_name, max(actor) as actor
			     from `tabAgent Action Log`
			     where action_type = 'check_in'
			       and reference_doctype = 'Reservation'
			       and ifnull(actor, '') != ''
			     group by reference_name
			   ) l on l.reference_name = r.name
			   set r.checked_in_by = l.actor
			   where r.checked_in_by is null
			     and r.actual_check_in is not null
			     and exists (select 1 from `tabUser` u where u.name = l.actor)""")
