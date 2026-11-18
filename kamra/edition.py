# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Kamra edition gate.

Community is the default and stays complete: every feature that shipped
before Enterprise still runs with the edition left on Community.

Enterprise is an opt-in on the same codebase. It adds the brochure suite
(forecast-driven pricing, guest offers, anomaly alerts, SMS, surveys,
ERPNext sync, the property website, the HTTP key encoder, arrival-priority
housekeeping and preventive maintenance). It does not remove or lock a
community feature.

Turn it on for one property under Settings -> Enterprise, or for every
property on a site with site_config `kamra_edition` = `Enterprise`.
There is no licence key. The AGPL source includes both editions.
"""

from __future__ import annotations

import frappe
from frappe import _


def edition_of(property: str | None) -> str:
	"""Community or Enterprise for this property."""
	if not property:
		return "Community"
	try:
		if (frappe.conf.get("kamra_edition") or "") == "Enterprise":
			return "Enterprise"
	except Exception:
		pass
	try:
		from kamra.settings import get_setting
		value = get_setting(property, "ent_edition", "Community") or "Community"
	except Exception:
		return "Community"
	return "Enterprise" if value == "Enterprise" else "Community"


def is_enterprise(property: str | None) -> bool:
	return edition_of(property) == "Enterprise"


def require_enterprise(property: str | None) -> None:
	"""Refuse an Enterprise-only call while the property is on Community."""
	if not is_enterprise(property):
		frappe.throw(
			_("Kamra Enterprise is off for this property. "
			  "Turn it on under Settings, Enterprise. "
			  "Community features keep working either way."),
			title=_("Enterprise"),
		)


def feature_on(property: str | None, key: str) -> bool:
	"""True when the property is Enterprise and the named check setting is on."""
	if not is_enterprise(property):
		return False
	from kamra.settings import get_setting
	return bool(get_setting(property, key))
