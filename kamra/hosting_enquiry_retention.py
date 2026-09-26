"""Retention and access for Hosting Enquiry leads (kamrapms.com forms).

Website enquiries hold names, emails and phones. Keep them only as long as
sales needs them, then delete. Converted leads (status Won) stay — they are
the customer record trail.

Retention months come from site_config ``hosting_enquiry_retention_months``
(default 24). Set to 0 to disable automatic deletion.
"""

from __future__ import annotations

DEFAULT_RETENTION_MONTHS = 24
# Won = converted to a customer / signed; keep those indefinitely.
KEEP_STATUSES = ("Won",)


def retention_months() -> int:
	import frappe
	from frappe.utils import cint

	return cint(frappe.conf.get("hosting_enquiry_retention_months", DEFAULT_RETENTION_MONTHS))


def purge_expired_hosting_enquiries(limit: int = 200) -> dict:
	"""Daily: delete Hosting Enquiry rows past the retention window.

	Skips status Won. Uses creation date. Returns counts for the scheduler log.
	"""
	import frappe
	from frappe.utils import add_months, now_datetime

	months = retention_months()
	if months <= 0:
		return {"deleted": 0, "skipped": "retention disabled"}

	cutoff = add_months(now_datetime(), -months)
	names = frappe.get_all(
		"Hosting Enquiry",
		filters={
			"creation": ("<", cutoff),
			"status": ("not in", list(KEEP_STATUSES)),
		},
		pluck="name",
		limit=limit,
		order_by="creation asc",
	)
	deleted = 0
	for name in names:
		frappe.delete_doc(
			"Hosting Enquiry", name,
			ignore_permissions=True, force=True, delete_permanently=True,
		)
		deleted += 1
		if deleted % 50 == 0:
			frappe.db.commit()  # nosemgrep: frappe-manual-commit -- scheduler batch: one delete must not roll back the rest
	if deleted:
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- scheduler: persist retention purge
	return {"deleted": deleted, "cutoff": str(cutoff), "months": months}
