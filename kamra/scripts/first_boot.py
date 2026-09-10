# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""WordPress-style first boot for a fresh Kamra site.

Called after ``bench new-site … --install-app kamra`` (install.sh, cloud-init,
DigitalOcean/Linode 1-click). Safe to re-run: it only fills blanks.

Env (optional, read once then left alone — install.sh wipes ADMIN_PASSWORD):

* ``KAMRA_ADMIN_EMAIL`` — set on the Administrator user
* ``KAMRA_SITE_URL`` — https://pms.example.com → ``host_name``
"""

from __future__ import annotations

import os

import frappe


def execute():
	"""Entry: ``bench --site <site> execute kamra.scripts.first_boot.execute``."""
	frappe.connect()
	_set_home_to_kamra()
	_set_admin_email()
	_set_host_name()
	_ensure_scheduler()
	frappe.clear_cache()
	print("kamra first_boot: ok")


def _set_home_to_kamra():
	"""Land visitors on /kamra, not empty Frappe Desk."""
	ws = frappe.get_doc("Website Settings")
	changed = False
	if not ws.favicon:
		ws.favicon = "/assets/kamra/kamra-mark.svg"
		changed = True
	# Frappe serves www/kamra.py at /kamra; home_page is the route name.
	if (ws.home_page or "").strip() in ("", "login", "me", "index"):
		ws.home_page = "kamra"
		changed = True
	if changed:
		ws.flags.ignore_mandatory = True
		ws.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- first-boot site wiring; intentional


def _set_admin_email():
	email = (os.environ.get("KAMRA_ADMIN_EMAIL") or "").strip()
	if not email or "@" not in email:
		return
	user = frappe.get_doc("User", "Administrator")
	if (user.email or "").lower() == email.lower():
		return
	user.email = email
	user.flags.ignore_password_policy = True
	user.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- first-boot admin email; intentional


def _set_host_name():
	url = (os.environ.get("KAMRA_SITE_URL") or "").strip().rstrip("/")
	if not url:
		return
	if not url.startswith("http"):
		url = "https://" + url
	frappe.db.set_single_value("System Settings", "host_name", url)
	# also site_config for get_url()
	frappe.conf.host_name = url
	from frappe.installer import update_site_config

	update_site_config("host_name", url)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- first-boot host_name; intentional


def _ensure_scheduler():
	try:
		from frappe.utils.scheduler import enable_scheduler

		enable_scheduler()
	except Exception:
		# Older benches: flag on site config is enough for the scheduler container.
		from frappe.installer import update_site_config

		update_site_config("pause_scheduler", 0)
