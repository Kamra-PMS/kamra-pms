"""Wipe play data on the public demo so it cannot be used as a live PMS.

The shared sandbox at demo.kamrapms.com (and nightly) is for trying Kamra,
not for running a hotel. This script deletes everything people created —
extra properties, users, bookings, folios, POS tickets, uploaded IDs,
pasted API keys — then reseeds the sample hotel.

Guarded: refuses unless ``kamra_demo_mode`` is on *and* the site is a
known playground. A real tenant can never trip this.

Run:
    bench --site demo.kamrapms.com execute kamra.scripts.reset_demo.execute

Scheduled daily at 04:15 site time via hooks.py.
"""

from __future__ import annotations

import frappe

from kamra.scripts.seed_users import USERS

# Public playgrounds only. Local benches with demo mode are allowed so
# developers can exercise the same path.
PLAYGROUND_SITES = {
	"demo.kamrapms.com",
	"nightly.kamrapms.com",
}

KEEP_USERS = {
	"Administrator",
	"Guest",
	*(spec["email"] for spec in USERS),
}

# Core Frappe clutter that accumulates when someone treats the demo as
# their hotel. Email Account is *not* in here — ops wires SMTP for us.
CORE_WIPE = (
	"Communication",
	"Contact",
	"Address",
	"ToDo",
	"Email Queue",
	"Email Queue Recipient",
	"Notification Log",
	"Activity Log",
	"Access Log",
	"Version",
	"View Log",
	"Deleted Document",
	"DocShare",
	"Comment",
	"Tag Link",
	"File",
	"Sessions",
)


def is_playground() -> bool:
	if frappe.db.get_default("kamra_demo_mode") != "1":
		return False
	site = frappe.local.site or ""
	return site in PLAYGROUND_SITES or site.endswith(".localhost")


def scheduled():
	"""Scheduler entry: no-op on real tenants, never throws."""
	if not is_playground():
		return
	reset()


def execute():
	"""Bench entry: refuse loudly if this is not a playground."""
	if not is_playground():
		frappe.throw(
			"Refusing to reset: this site is not a Kamra demo playground. "
			"Set kamra_demo_mode and use demo.kamrapms.com / nightly / localhost."
		)
	return reset()


def reset() -> dict:
	"""Wipe Kamra + leftover users, then reseed the sample hotel."""
	summary: dict = {"site": frappe.local.site, "wiped": {}}

	frappe.flags.ignore_permissions = True
	frappe.flags.in_import = True

	summary["wiped"]["kamra"] = _wipe_kamra_doctypes()
	summary["wiped"]["core"] = _wipe_core()
	summary["wiped"]["users"] = _wipe_extra_users()
	_reset_demo_passwords()

	frappe.clear_cache()
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- reset script runs outside the request cycle

	# seed_demo is idempotent *if* the property still exists; we just
	# deleted it, so this rebuilds rooms, guests, stays and showcase.
	from kamra.scripts.seed_demo import execute as seed_demo
	seed_demo()

	frappe.db.set_default("kamra_demo_mode", "1")
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persist demo flag after reseed
	frappe.clear_cache()

	msg = (
		f"Demo playground reset on {summary['site']}: "
		f"kamra={summary['wiped']['kamra']} core={summary['wiped']['core']} "
		f"users={summary['wiped']['users']}"
	)
	print(msg)
	summary["ok"] = True
	summary["message"] = msg
	return summary


def _wipe_kamra_doctypes() -> int:
	rows = frappe.get_all(
		"DocType",
		filters={"module": "Kamra"},
		fields=["name", "istable", "issingle"],
	)
	# Children first so parent deletes don't fight leftover rows.
	rows.sort(key=lambda r: (0 if r.istable else 1, r.name))
	total = 0
	try:
		frappe.db.sql("SET FOREIGN_KEY_CHECKS=0")
	except Exception:
		pass
	try:
		for row in rows:
			total += _empty_doctype(row.name, single=bool(row.issingle))
	finally:
		try:
			frappe.db.sql("SET FOREIGN_KEY_CHECKS=1")
		except Exception:
			pass
	return total


def _wipe_core() -> int:
	total = 0
	for doctype in CORE_WIPE:
		if not frappe.db.exists("DocType", doctype):
			continue
		# Keep the two File folder stubs Frappe expects.
		if doctype == "File":
			n = frappe.db.sql(
				"select count(*) from `tabFile` "
				"where name not in ('Home', 'Home/Attachments')"
			)[0][0]
			frappe.db.sql(
				"delete from `tabFile` where name not in ('Home', 'Home/Attachments')"
			)
			total += int(n or 0)
			continue
		total += _empty_doctype(doctype)
	return total


def _empty_doctype(doctype: str, single: bool = False) -> int:
	table = f"tab{doctype}"
	if not frappe.db.table_exists(doctype):
		if single:
			frappe.db.sql("delete from `tabSingles` where doctype=%s", doctype)
		return 0
	n = frappe.db.count(doctype)
	frappe.db.sql(f"delete from `{table}`")  # nosemgrep: frappe-sql-format-injection -- doctype name from DocType master, not user input
	if single:
		frappe.db.sql("delete from `tabSingles` where doctype=%s", doctype)
	return n


def _wipe_extra_users() -> int:
	removed = 0
	users = frappe.get_all("User", pluck="name")
	for name in users:
		if name in KEEP_USERS:
			continue
		try:
			frappe.delete_doc(
				"User", name, force=1, ignore_permissions=True,
				delete_permanently=True,
			)
			removed += 1
		except Exception:
			frappe.db.sql("delete from `tabHas Role` where parent=%s", name)
			frappe.db.sql("delete from `tabUser` where name=%s", name)
			removed += 1
	return removed


def _reset_demo_passwords():
	"""In case someone changed a printed demo password."""
	from frappe.utils.password import update_password

	for spec in USERS:
		if frappe.db.exists("User", spec["email"]):
			update_password(spec["email"], spec["password"])
			frappe.db.set_value("User", spec["email"], "enabled", 1)
