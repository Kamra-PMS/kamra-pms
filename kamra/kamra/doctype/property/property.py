# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document

SHORT_CODE = re.compile(r"^[A-Z0-9]{2,6}$")


def default_short_code(name: str, exclude: str | None = None) -> str:
	"""The property's initials (2-3 letters or digits), with a digit added
	when another property already holds them: "Sunrise Residency" -> SR,
	a second one -> SR2."""
	words = re.findall(r"[A-Z0-9]+", (name or "").upper())
	base = "".join(w[0] for w in words)[:3]
	if len(base) < 2:
		base = "".join(words)[:3]
	if len(base) < 2:
		base = "PR"
	taken = set(frappe.get_all("Property", filters={"name": ("!=", exclude or "")},
	                           pluck="short_code"))
	if base not in taken:
		return base
	for n in range(2, 100):
		code = f"{base[:6 - len(str(n))]}{n}"
		if code not in taken:
			return code
	frappe.throw(_("Pick a short code for this property."))


class Property(Document):
	def validate(self):
		self._validate_short_code()
		# A kind switch in Settings (or Desk) gets the new kind's preset,
		# the same way setup_property applies it at creation. Only empty
		# preset fields are filled, so explicit admin values survive.
		if not self.is_new() and self.has_value_changed("property_kind"):
			from kamra.property_presets import apply_kind_change
			apply_kind_change(self)

	def _validate_short_code(self):
		# Numbers allowance vouchers (ALW-<code>-YY-#####). The series key
		# holds the code, so a new code starts a new series and never
		# reuses a number. Invoice numbering does not use it.
		code = (self.short_code or "").strip().upper()
		if not code:
			code = default_short_code(self.property_name or self.name,
			                          exclude=self.name)
		if not SHORT_CODE.match(code):
			frappe.throw(_("Short code: 2 to 6 letters (A-Z) or digits."))
		if frappe.db.exists("Property", {"short_code": code,
		                                 "name": ("!=", self.name or "")}):
			frappe.throw(_("Short code {0} is already used by another property.").format(code))
		self.short_code = code

	def after_insert(self):
		# A new property starts with allowances signed off by a Hotel Admin,
		# every amount. Existing properties keep the registry default (Off),
		# so an upgrade changes nothing.
		from kamra.settings import clear_cache, write_kv
		write_kv(self.name, "allowance_approval", "Hotel Admin")
		write_kv(self.name, "allowance_approval_above", 0)
		clear_cache(self.name)

	def on_update(self):
		# Single-site tenants: keep Frappe's site clock aligned with the
		# property so night audit / now_datetime follow hotel local time.
		# Multi-property sites with different zones should leave System
		# Settings alone (only sync when this is the sole property).
		tz = (self.timezone or "").strip()
		if not tz or not self.has_value_changed("timezone"):
			return
		if frappe.db.count("Property") > 1:
			return
		current = frappe.db.get_single_value("System Settings", "time_zone")
		if current == tz:
			return
		frappe.db.set_single_value("System Settings", "time_zone", tz)
		frappe.clear_cache()
