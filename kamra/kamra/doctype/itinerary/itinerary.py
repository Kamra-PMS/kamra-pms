# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class Itinerary(Document):
	# ponytail: the legs are ordinary Reservations pointing here
	# (Reservation.itinerary); status and totals are read from them in
	# kamra.crs, never stored twice
	pass
