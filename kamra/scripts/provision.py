"""Stand up one customer's property - the application half of provisioning.

The demo seeds exist to make screenshots look alive. A paying customer
must get none of that: no Kamra Demo Palace, no invented reservations, no
sample laundry. What they get is their own property, their own login, the
modules they actually bought, and nothing else.

Run from the infra script, or by hand:

    bench --site ewa.kamrapms.com execute kamra.scripts.provision.setup \\
      --kwargs "{'property_name': 'EWA Stays', 'city': 'Bengaluru',
                 'owner_email': 'owner@ewa.com', 'owner_name': 'A Owner',
                 'modules': 'front-desk,housekeeping,finance,booking-engine'}"
"""

import secrets
import string

import frappe

# Every role Kamra ships. A tenant gets the ones its modules need.
ROLES = ("Hotel Admin", "Front Desk", "Housekeeping", "Finance",
         "Revenue Manager", "Kamra Agent")

# What a property must have before anyone can take a booking on it.
MODULE_ROLES = {
	"front-desk": ("Front Desk",),
	"housekeeping": ("Housekeeping",),
	"operations": ("Front Desk",),
	"fnb": ("Front Desk", "Finance"),
	"events": ("Front Desk", "Revenue Manager"),
	"revenue": ("Revenue Manager",),
	"finance": ("Finance",),
	"booking-engine": ("Revenue Manager",),
	"admin": ("Hotel Admin",),
}


def _password(n: int = 16) -> str:
	"""A password a human can retype off a screen once, then change."""
	alphabet = string.ascii_letters + string.digits + "!@#$%"
	return "".join(secrets.choice(alphabet) for _ in range(n))


def _ensure_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role,
			                "desk_access": 0}).insert(ignore_permissions=True)


def setup(property_name: str, city: str = "", country: str = "India",
          currency: str = "", state: str = "", gstin: str = "",
          phone: str = "", email: str = "", timezone: str = "",
          owner_email: str = "", owner_name: str = "",
          owner_password: str | None = None,
          modules: str = "", smtp: dict | None = None) -> dict:
	"""Create a live property and its first user. Idempotent: running it
	twice updates rather than duplicating, so a half-finished provision
	can simply be run again."""
	_ensure_roles()

	existing = frappe.db.get_value("Property", {"property_name": property_name})
	doc = (frappe.get_doc("Property", existing) if existing
	       else frappe.new_doc("Property"))
	doc.update({
		"property_name": property_name,
		"city": city or doc.get("city"),
		"state": state or doc.get("state"),
		"country": country or doc.get("country") or "India",
		"phone": phone or doc.get("phone"),
		"email": email or doc.get("email"),
		"gstin": gstin or doc.get("gstin"),
		"timezone": timezone or doc.get("timezone"),
		"enabled_modules": modules or doc.get("enabled_modules"),
	})
	if currency:
		doc.currency = currency
	doc.save(ignore_permissions=True)

	created_user, password = None, None
	if owner_email:
		roles = {"Hotel Admin"}
		for m in (modules or "").split(","):
			roles.update(MODULE_ROLES.get(m.strip(), ()))
		if not frappe.db.exists("User", owner_email):
			password = owner_password or _password()
			parts = (owner_name or owner_email.split("@")[0]).split(" ", 1)
			frappe.get_doc({
				"doctype": "User", "email": owner_email,
				"first_name": parts[0],
				"last_name": parts[1] if len(parts) > 1 else None,
				"enabled": 1, "user_type": "System User",
				"send_welcome_email": 0,
				"new_password": password,
				"roles": [{"role": r} for r in sorted(roles)],
			}).insert(ignore_permissions=True)
			created_user = owner_email
		else:
			user = frappe.get_doc("User", owner_email)
			have = {r.role for r in user.roles}
			for r in sorted(roles - have):
				user.append("roles", {"role": r})
			user.save(ignore_permissions=True)

		# scope them to this property, so a second tenant on the same site
		# is never visible to the first
		if not frappe.db.exists("User Permission", {
			"user": owner_email, "allow": "Property", "for_value": doc.name}):
			frappe.get_doc({
				"doctype": "User Permission", "user": owner_email,
				"allow": "Property", "for_value": doc.name,
				"apply_to_all_doctypes": 1,
			}).insert(ignore_permissions=True)

	if smtp:
		configure_smtp(**smtp)

	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- provisioning script runs outside the request cycle; the caller needs the record to exist before it prints credentials
	return {
		"property": doc.name,
		"modules": doc.enabled_modules or "all",
		"user": created_user,
		"password": password,
		"note": ("Password shown once - it is not stored anywhere readable."
		         if password else "User already existed; password unchanged."),
	}


def mail_ready() -> dict:
	"""Can this site actually send?

	On Frappe Cloud the Email Delivery Service app does outgoing mail with
	no configuration at all, so a site with it installed needs no SMTP
	from us - and setting one up anyway would just fight it. Everywhere
	else we need a real SMTP account."""
	eds = "email_delivery_service" in (frappe.get_installed_apps() or [])
	account = frappe.db.get_value("Email Account", {"default_outgoing": 1},
	                              ["email_id", "smtp_server"], as_dict=True)
	return {
		"can_send": bool(eds or account),
		"via": "Frappe Cloud Email Delivery Service" if eds
		       else (f"SMTP {account.smtp_server}" if account else None),
		"needs_smtp": not eds and not account,
	}


def configure_smtp(host: str, port: int = 587, login: str = "",
                   password: str = "", from_address: str = "",
                   from_name: str = "", use_tls: int = 1,
                   use_ssl: int = 0) -> dict:
	"""Outgoing mail for this tenant.

	Without it the product silently can't send a booking confirmation, a
	payment link or a self-check-in invitation - and nothing tells anyone
	until a guest complains they never got the email.

	Kamra Cloud outbound mail is usually Resend SMTP
	(``smtp.resend.com:465``, username ``resend``, password = API key).
	Port 465 needs ``use_ssl=1`` (implicit TLS) and ``use_tls=0``.
	Other providers (Brevo, Hostinger, Cloudflare Email Sending, custom)
	work the same path — pass host/port/login/password and the matching
	TLS flags.
	"""
	name = frappe.db.get_value("Email Account", {"default_outgoing": 1})
	doc = (frappe.get_doc("Email Account", name) if name
	       else frappe.new_doc("Email Account"))
	ssl = 1 if int(use_ssl or 0) else 0
	# Port 465 with Cloudflare is always implicit SSL; don't also set STARTTLS.
	tls = 0 if ssl else (1 if int(use_tls or 0) else 0)
	doc.update({
		"email_account_name": doc.get("email_account_name") or "Outgoing",
		"email_id": from_address or login,
		"smtp_server": host, "smtp_port": int(port),
		"use_tls": tls,
		"use_ssl_for_outgoing": ssl,
		"login_id": login or from_address,
		"login_id_is_different": bool(login and login != from_address),
		"enable_outgoing": 1, "default_outgoing": 1,
		"always_use_account_email_id_as_sender": 1,
	})
	if password:
		doc.password = password
	if from_name:
		doc.name_of_sender = from_name
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- provisioning script runs outside the request cycle
	return {"ok": True, "outgoing": doc.email_id,
	        "smtp": f"{host}:{port}", "ssl": bool(ssl)}


def status(property_name: str | None = None) -> dict:
	"""What this site actually has on it - the check to run before handing
	over credentials."""
	props = frappe.get_all("Property", fields=["name", "property_name",
	                                           "city", "enabled_modules"])
	mail = mail_ready()
	demo = frappe.db.exists("Property", "Kamra Demo Palace")
	return {
		"properties": props,
		"room_types": frappe.db.count("Room Type"),
		"rooms": frappe.db.count("Room"),
		"users": frappe.db.count("User", {"user_type": "System User"}),
		"outgoing_mail": mail,
		"demo_data_present": bool(demo),
		"warnings": [w for w in [
			"Demo data is on this site - a customer site should have none."
			if demo else None,
			"No outgoing mail; confirmations, payment links and check-in "
			"invitations will fail silently. On Frappe Cloud add the Email "
			"Delivery Service app; elsewhere set an SMTP account."
			if mail["needs_smtp"] else None,
			"No rooms yet - the property can't take a booking."
			if not frappe.db.count("Room") else None,
		] if w],
	}
