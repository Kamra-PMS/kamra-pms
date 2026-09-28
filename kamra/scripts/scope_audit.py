"""Pre-upgrade check for the property-scope and webhook hardening.

Read-only. Run on a site before upgrading to the release that enforces
property scope and refuses unauthenticated webhooks:

    bench --site <site> execute kamra.scripts.scope_audit.report

It lists (1) users pinned to some properties by User Permissions, with the
properties they will stop seeing, and (2) active connections whose inbound
webhooks will be refused because no secret is configured. An empty report
means the upgrade changes nothing for this site.
"""

import frappe


def report() -> dict:
	props = set(frappe.get_all("Property", pluck="name"))
	scoped: dict[str, set] = {}
	for row in frappe.get_all(
			"User Permission", filters={"allow": "Property"},
			fields=["user", "for_value"]):
		scoped.setdefault(row.user, set()).add(row.for_value)
	users = [
		{"user": u, "keeps": sorted(allowed), "loses": sorted(props - allowed)}
		for u, allowed in sorted(scoped.items())
		if props - allowed and frappe.db.get_value("User", u, "enabled")
	]

	webhooks = []
	for c in frappe.get_all("Channel Manager Connection", {"active": 1},
	                        ["name", "property", "provider"]):
		doc = frappe.get_doc("Channel Manager Connection", c.name)
		if c.provider == "AioSell":
			ok = doc.api_username and doc.get_password(
				"api_key", raise_exception=False)
		else:
			ok = doc.get_password("webhook_secret", raise_exception=False)
		if not ok:
			webhooks.append({**c, "fix": "set webhook secret / AioSell creds"})
	for c in frappe.get_all("Channel Provider Connection", {"active": 1},
	                        ["name", "property", "channel", "provider"]):
		doc = frappe.get_doc("Channel Provider Connection", c.name)
		if not doc.get_password("webhook_secret", raise_exception=False) \
				and c.channel != "WhatsApp":
			webhooks.append({**c, "fix": "set webhook secret"})
		if c.channel == "WhatsApp" and c.provider == "Meta Business" and \
				not (doc.meta.has_field("app_secret")
				     and doc.get_password("app_secret", raise_exception=False)):
			webhooks.append({**c, "fix": "set Meta App Secret after upgrade"})
	for g in frappe.get_all("Payment Gateway Settings", {"enabled": 1},
	                        ["name", "property", "gateway"]):
		doc = frappe.get_doc("Payment Gateway Settings", g.name)
		if not doc.get_password("webhook_secret", raise_exception=False):
			webhooks.append({**g, "fix": "set gateway webhook secret"})

	out = {"properties": sorted(props), "users_losing_access": users,
	       "webhooks_to_fix": webhooks,
	       "safe_to_upgrade": not users and not webhooks}
	print(frappe.as_json(out))
	return out
