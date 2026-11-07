# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

from decimal import Decimal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


def _dec(val) -> Decimal:
	if val is None or val == "":
		return Decimal(0)
	return Decimal(str(val))


class HolidayPackage(Document):
	def validate(self):
		if getdate(self.start_date) > getdate(self.end_date):
			frappe.throw(_("Start Date cannot be after End Date."))

		if self.package_nights is None or self.package_nights == "":
			self.package_nights = self.minimum_nights if (self.minimum_nights is not None and self.minimum_nights != "") else 1
		if int(self.package_nights or 0) < 1:
			frappe.throw(_("Package Nights must be at least 1."))

		# Keep minimum_nights synchronized
		self.minimum_nights = self.package_nights

		if _dec(self.price_2_pax) <= 0:
			frappe.throw(_("Package Rate 2 Pax (Base) must be greater than zero."))

		pct_extra = float(self.get("extra_night_percent") or 0)
		if pct_extra and pct_extra < 0:
			frappe.throw(_("Extra Night Rate % cannot be negative."))

		if self.extra_night_price and _dec(self.extra_night_price) < 0:
			frappe.throw(_("Extra Night Fixed Override cannot be negative."))

		pct = float(self.get("advance_percent") or 0)
		if pct and not (0 <= pct <= 100):
			frappe.throw(_("Advance Deposit % must be between 0 and 100."))

		if self.ota_strategy == "Markup" and self.ota_daily_rate and _dec(self.ota_daily_rate) < 0:
			frappe.throw(_("OTA Daily Rate cannot be negative."))

	def package_price_for(self, adults: int, children: int = 0, nights: int | None = None) -> Decimal:
		"""Calculate the package total for the party size and stay duration.

		If nights is supplied and exceeds package_nights, extra nights are charged
		as a percentage of the package daily rate (extra_night_percent, e.g. 50% or 100%),
		or extra_night_price if a fixed override is configured.
		"""
		adults = max(1, int(adults or 2))
		children = max(0, int(children or 0))

		if adults == 1 and self.price_1_pax:
			base = _dec(self.price_1_pax)
		elif adults == 2 or (adults == 1 and not self.price_1_pax):
			base = _dec(self.price_2_pax)
		elif adults == 3 and self.price_3_pax:
			base = _dec(self.price_3_pax)
		elif adults == 4 and self.price_4_pax:
			base = _dec(self.price_4_pax)
		elif adults == 5 and self.price_5_pax:
			base = _dec(self.price_5_pax)
		else:
			# adults beyond the highest configured tier
			if adults >= 5 and self.price_5_pax:
				top = _dec(self.price_5_pax)
				top_tier = 5
			elif adults >= 4 and self.price_4_pax:
				top = _dec(self.price_4_pax)
				top_tier = 4
			elif adults >= 3 and self.price_3_pax:
				top = _dec(self.price_3_pax)
				top_tier = 3
			else:
				top = _dec(self.price_2_pax)
				top_tier = 2
			extras = adults - top_tier
			base = top + Decimal(extras) * _dec(self.extra_adult_price)

		if children and self.child_price:
			base += Decimal(children) * _dec(self.child_price)

		pkg_nights = int(getattr(self, "package_nights", None) or getattr(self, "minimum_nights", None) or 1)
		if nights is not None and nights > pkg_nights:
			extra_n = nights - pkg_nights
			package_daily = (base / Decimal(pkg_nights)).quantize(Decimal("0.01"))

			fixed_extra = _dec(getattr(self, "extra_night_price", 0))
			pct_raw = getattr(self, "extra_night_percent", None)
			pct_extra = float(pct_raw) if (pct_raw is not None and pct_raw != "") else 100.0

			if fixed_extra > 0:
				extra_rate = fixed_extra
			else:
				extra_rate = (package_daily * Decimal(str(pct_extra)) / Decimal(100)).quantize(Decimal("0.01"))

			base += Decimal(extra_n) * extra_rate

		return base
