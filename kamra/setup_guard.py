"""Keep Frappe's own setup wizard shut on Kamra sites.

Kamra is set up in /kamra (Finish setup, kamra.api.setup_property), never in
Frappe's /app/setup-wizard. Left open, that wizard is the first screen any
signed-in user lands on in Desk, and its two write endpoints only check that
setup is not finished yet: they set the site's settings and create or update
a user with the System Manager role. So the wizard is marked done on install
and on every migrate, and its write endpoints need a System Manager.
"""

import frappe
from frappe.desk.page.setup_wizard import setup_wizard


def close_frappe_setup_wizard():
	"""Mark Frappe's wizard complete (idempotent). Kamra's own onboarding is
	unaffected: it never reads these flags."""
	if not frappe.db.table_exists("Installed Application"):
		return
	if not frappe.db.get_value("Installed Application", {"app_name": "frappe"},
	                           "is_setup_complete"):
		frappe.db.set_value("Installed Application", {"app_name": "frappe"},
		                    "is_setup_complete", 1)
	if not frappe.db.get_single_value("System Settings", "setup_complete"):
		frappe.db.set_single_value("System Settings", "setup_complete", 1)
	frappe.clear_cache(doctype="System Settings")


@frappe.whitelist()
def setup_complete(args: str | dict):
	frappe.only_for("System Manager")
	return setup_wizard.setup_complete(args)


@frappe.whitelist()
def initialize_system_settings_and_user(system_settings_data: str | dict, user_data: str | dict):
	frappe.only_for("System Manager")
	return setup_wizard.initialize_system_settings_and_user(system_settings_data, user_data)
