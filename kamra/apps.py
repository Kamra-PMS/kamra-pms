"""Connected apps: connect an add-on in one step.

1. IT opens Marketplace and enters the app's address. Core fetches
   `<address>/kamra-app.json`, checks its signature against the trusted
   publisher keys (or IT has allowed unsigned, self-hosted apps) and shows
   the scopes the app asks for.
2. IT approves some or all of those scopes and picks properties. Core
   creates a service account with exactly those, registers the app in the
   App Registry (Kamra App, which the app switcher reads), allows the app's
   OAuth redirect address and shows a one-time pairing code: 10 minutes,
   single use, stored hashed.
3. The app calls `kamra.apps.pair(code, app_id)` once and receives its key
   and secret, the site URL, the granted scopes and the property list.

The service account is for background reads only. Anything a person does
in the app goes through core's MCP OAuth 2.1 (kamra/mcp_oauth.py) with that
person's own token, so it runs as the signed-in staff member with their
roles. Disconnect revokes the service account, the redirect address, the
staff tokens issued through it and the tile."""

from __future__ import annotations

import base64
import json
import re
import secrets
from urllib.parse import urlencode, urlparse

import frappe
import requests
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_to_date, get_url, now_datetime

from kamra import service_accounts as sa
from kamra.authz import ADMIN, require_it_admin, require_roles
from kamra.mcp_oauth import hash_token

MANIFEST = "kamra-app.json"
# site-wide trust: Ed25519 public keys (base64) of app publishers, and
# whether IT accepts unsigned manifests (self-hosted apps)
KEYS_KEY = "kamra_app_signing_keys"
UNSIGNED_KEY = "kamra_trust_unsigned_apps"
CODE_TTL_MINUTES = 10
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I
APP_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
MAX_MANIFEST_BYTES = 64 * 1024
# staff roles that may read a property's profile; every read scope's
# service account carries one of them (scope_roles)
READ_ROLES = ("Front Desk", "Finance", "Revenue Manager", "Night Auditor",
              "Housekeeping", "Kamra Agent")


# --- trust ------------------------------------------------------------------------


def trusted_keys() -> list[str]:
	raw = frappe.db.get_default(KEYS_KEY)
	try:
		items = json.loads(raw) if raw else []
	except (TypeError, ValueError):
		return []
	return [k for k in items if isinstance(k, str)]


def unsigned_allowed() -> bool:
	return frappe.db.get_default(UNSIGNED_KEY) == "1"


def canonical(manifest: dict) -> bytes:
	"""The bytes a publisher signs: the manifest without `signature`, keys
	sorted, no spaces, UTF-8."""
	body = {k: v for k, v in manifest.items() if k != "signature"}
	return json.dumps(body, sort_keys=True, separators=(",", ":"),
	                  ensure_ascii=False).encode("utf-8")


def signed_by_trusted_key(manifest: dict) -> bool:
	from cryptography.exceptions import InvalidSignature
	from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

	sig = manifest.get("signature")
	if not isinstance(sig, str) or not sig:
		return False
	try:
		raw = base64.b64decode(sig, validate=True)
	except ValueError:
		return False
	body = canonical(manifest)
	for key in trusted_keys():
		try:
			Ed25519PublicKey.from_public_bytes(base64.b64decode(key)).verify(raw, body)
			return True
		except (InvalidSignature, ValueError):
			continue
	return False


# --- the manifest -------------------------------------------------------------------


def _https(url, what: str) -> str:
	url = str(url or "").strip()
	parsed = urlparse(url)
	if (parsed.scheme != "https" or not parsed.hostname or parsed.username
			or parsed.password or "#" in url or len(url) > 500):
		frappe.throw(_("{0}: use a full https:// address.").format(what))
	return url


def manifest_url(app_url: str) -> str:
	app_url = _https(app_url, _("App address"))
	if app_url.split("?")[0].endswith("/" + MANIFEST):
		return app_url
	return app_url.rstrip("/") + "/" + MANIFEST


def _download(url: str) -> bytes:
	# ponytail: IT-only and https-only; private addresses stay allowed so a
	# self-hosted app on the hotel's network can connect
	try:
		r = requests.get(url, timeout=8, allow_redirects=False, stream=True,
		                 headers={"Accept": "application/json"})
		body = r.raw.read(MAX_MANIFEST_BYTES + 1, decode_content=True)
	except requests.RequestException:
		frappe.throw(_("Couldn't reach {0}.").format(url))
	if r.status_code != 200:
		frappe.throw(_("{0} answered {1}, not the app manifest.").format(url, r.status_code))
	if len(body) > MAX_MANIFEST_BYTES:
		frappe.throw(_("The app manifest is too large."))
	return body


def read_manifest(app_url: str) -> frappe._dict:
	"""Fetch, check and normalise an app's kamra-app.json."""
	url = manifest_url(app_url)
	try:
		m = json.loads(_download(url))
	except ValueError:
		m = None
	if not isinstance(m, dict):
		frappe.throw(_("{0} is not a valid app manifest.").format(url))
	host = urlparse(url).hostname

	def same_host(value, what):
		value = _https(value, what)
		if urlparse(value).hostname != host:
			frappe.throw(_("{0} must be on {1}, where the manifest is.").format(what, host))
		return value

	app_id = str(m.get("id") or "")
	if not APP_ID.match(app_id):
		frappe.throw(_("The manifest needs an id: lowercase letters, digits and dashes."))
	name = str(m.get("name") or "").strip()[:80]
	if not name:
		frappe.throw(_("The manifest needs a name."))
	redirect = str(m.get("redirect_uri") or "").strip()
	if redirect:
		from kamra.mcp_access import redirect_uri_problem
		problem = redirect_uri_problem(redirect)
		if problem:
			frappe.throw(problem)
		same_host(redirect, "redirect_uri")
	scopes = sa._parse(m.get("scopes"))
	unknown = [s for s in scopes if s not in sa.SCOPES]
	if not scopes or unknown:
		frappe.throw(_("The manifest asks for unknown scopes: {0}").format(
			", ".join(unknown) or _("(none)")))
	roles = m.get("roles") or []
	if not isinstance(roles, list):
		frappe.throw(_("The manifest's roles must be a list."))
	signed = signed_by_trusted_key(m)
	if not signed and not unsigned_allowed():
		frappe.throw(_("This app's manifest is not signed by a trusted publisher. "
		               "IT can allow unsigned, self-hosted apps in Marketplace."))
	return frappe._dict(
		app_id=app_id, name=name, manifest_url=url, signed=signed,
		url=same_host(m.get("url"), "url"),
		icon=_https(m["icon"], "icon") if m.get("icon") else "",
		redirect_uri=redirect,
		pair_url=same_host(m["pair_url"], "pair_url") if m.get("pair_url") else "",
		scopes=scopes, roles=sorted({str(r) for r in roles if str(r).strip()}),
		raw=m,
	)


# --- pairing codes ------------------------------------------------------------------


def _new_code() -> str:
	raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(16))  # 80 bits
	return "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def _code_hash(code) -> str:
	return hash_token(re.sub(r"[^A-Z0-9]", "", str(code or "").upper()))


def _code_values(code: str) -> dict:
	return {"code_hash": _code_hash(code),
	        "code_expires": add_to_date(now_datetime(), minutes=CODE_TTL_MINUTES)}


def _code_reply(doc, code: str, pair_url: str = "") -> dict:
	out = {"app_id": doc.name, "code": code, "expires_at": str(doc.code_expires)}
	if pair_url:
		# the app can take the admin straight back with the code filled in
		out["pair_link"] = pair_url + ("&" if "?" in pair_url else "?") + urlencode(
			{"code": code, "app_id": doc.name, "site": get_url()})
	return out


# --- redirect addresses (the existing MCP extra-redirects list) -----------------------


def _allow_redirect(uri: str):
	from kamra.mcp_access import extra_redirect_uris, set_extra_redirect_uris
	current = extra_redirect_uris()
	if uri not in current:
		set_extra_redirect_uris([*current, uri])


def _drop_redirect(uri: str, app_id: str):
	from kamra.mcp_access import extra_redirect_uris, set_extra_redirect_uris
	shared = frappe.db.exists("Kamra App", {"redirect_uri": uri, "name": ["!=", app_id],
	                                        "status": ["in", ["Pending", "Paired"]]})
	current = extra_redirect_uris()
	if not shared and uri in current:
		set_extra_redirect_uris([u for u in current if u != uri])
	# staff who signed in through the app lose their tokens now too
	for grant in frappe.get_all("MCP OAuth Grant", {"redirect_uri": uri, "revoked": 0},
	                            pluck="name"):
		frappe.db.set_value("MCP OAuth Grant", grant, "revoked", 1)


def _log(action: str, app: str | None, rationale: str, rejected: bool = False,
         properties=None):
	from kamra.savings import log_action
	props = sa._parse(properties)
	log_action(action, "Kamra App" if app else None, app,
	           property=props[0] if len(props) == 1 else None,
	           rationale=rationale[:1000], channel="API",
	           approval_status="Rejected" if rejected else "Executed")


# --- IT: connect, new code, disconnect, trust -----------------------------------------


def _properties() -> list[dict]:
	return frappe.get_all("Property", filters={"disabled": 0},
	                      fields=["name", "property_name"], order_by="property_name asc")


@frappe.whitelist()
@require_it_admin
def preview(app_url: str) -> dict:
	"""The consent step: what the app is and what it asks for."""
	m = read_manifest(app_url)
	labels = {k: v["label"] for k, v in sa.SCOPES.items()}
	return {
		"app_id": m.app_id, "name": m.name, "icon": m.icon, "url": m.url,
		"manifest_url": m.manifest_url, "signed": m.signed,
		"redirect_uri": m.redirect_uri, "roles": m.roles,
		"scopes": [{"scope": s, "label": labels[s]} for s in m.scopes],
		"properties": _properties(),
		"status": frappe.db.get_value("Kamra App", m.app_id, "status"),
	}


@frappe.whitelist(methods=["POST"])
@require_it_admin
def connect(app_url: str, scopes: str | list, properties: str | list) -> dict:
	"""Approve an app: a service account with exactly these scopes and
	properties, a registry entry, its redirect address, and a one-time
	pairing code (shown once)."""
	m = read_manifest(app_url)  # fetched again: never trust the browser's copy
	scopes = sa._parse(scopes)
	extra = [s for s in scopes if s not in m.scopes]
	if extra:
		frappe.throw(_("The app didn't ask for: {0}").format(", ".join(extra)))
	status = frappe.db.get_value("Kamra App", m.app_id, "status")
	if status in ("Pending", "Paired"):
		frappe.throw(_("{0} is already connected. Disconnect it first.").format(m.name))

	# the secret is issued once, at pairing; this one is never shown
	acct = sa.create_service_account(m.name, scopes, properties)
	if m.redirect_uri:
		_allow_redirect(m.redirect_uri)
	code = _new_code()
	values = {
		"app_name": m.name, "status": "Pending", "url": m.url, "icon": m.icon,
		"manifest_url": m.manifest_url, "redirect_uri": m.redirect_uri,
		"roles": json.dumps(m.roles), "scopes": json.dumps(acct["scopes"]),
		"properties": json.dumps(acct["properties"]), "signed": int(m.signed),
		"service_account": acct["name"], "paired_on": None,
		"manifest": json.dumps(m.raw, indent=1), **_code_values(code),
	}
	if status:
		doc = frappe.get_doc("Kamra App", m.app_id)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({"doctype": "Kamra App", "app_id": m.app_id, **values}).insert(
			ignore_permissions=True)
	_log("app.connected", doc.name,
	     f"{m.name} ({'signed' if m.signed else 'unsigned, trusted by IT'}): "
	     f"{', '.join(acct['scopes'])} at {', '.join(acct['properties'])}",
	     properties=acct["properties"])
	return _code_reply(doc, code, m.pair_url)


@frappe.whitelist(methods=["POST"])
@require_it_admin
def new_pairing_code(app_id: str) -> dict:
	"""A fresh code for an app that has not paired yet; the old one stops."""
	doc = frappe.get_doc("Kamra App", app_id)
	if doc.status != "Pending":
		frappe.throw(_("{0} is not waiting to pair.").format(doc.app_name))
	code = _new_code()
	doc.db_set(_code_values(code))
	_log("app.pairing_code", doc.name, f"New pairing code for {doc.app_name}")
	pair_url = (json.loads(doc.manifest or "{}") or {}).get("pair_url") or ""
	return _code_reply(doc, code, pair_url)


@frappe.whitelist(methods=["POST"])
@require_it_admin
def disconnect(app_id: str) -> dict:
	"""Off at once: the service account is revoked, the redirect address and
	the staff tokens issued through it go, and the tile disappears."""
	doc = frappe.get_doc("Kamra App", app_id)
	if doc.service_account:
		sa.revoke_service_account(doc.service_account)
	if doc.redirect_uri:
		_drop_redirect(doc.redirect_uri, doc.name)
	doc.db_set({"status": "Disconnected", "code_hash": None, "code_expires": None})
	_log("app.disconnected", doc.name, f"Disconnected {doc.app_name}")
	return {"ok": True, "app_id": doc.name, "status": "Disconnected"}


@frappe.whitelist()
@require_it_admin
def list_apps() -> dict:
	rows = frappe.get_all(
		"Kamra App",
		fields=["name as app_id", "app_name", "status", "url", "icon", "scopes",
		        "properties", "roles", "signed", "paired_on", "code_expires"],
		order_by="app_name asc")
	for r in rows:
		for f in ("scopes", "properties", "roles"):
			r[f] = sa._parse(r[f])
	return {"apps": rows, "unsigned_allowed": unsigned_allowed(),
	        "trusted_keys": len(trusted_keys())}


@frappe.whitelist(methods=["POST"])
@require_it_admin
def set_trust(unsigned: int | str | None = None, keys: str | list | None = None) -> dict:
	"""IT: allow unsigned (self-hosted) apps, and/or replace the list of
	trusted publisher keys (base64 Ed25519 public keys)."""
	if unsigned is not None:
		frappe.db.set_default(UNSIGNED_KEY, "1" if str(unsigned) in ("1", "true", "True") else "0")
	if keys is not None:
		keys = sa._parse(keys)
		for k in keys:
			try:
				ok = len(base64.b64decode(k, validate=True)) == 32
			except ValueError:
				ok = False
			if not ok:
				frappe.throw(_("{0} is not a base64 Ed25519 public key.").format(k[:20]))
		frappe.db.set_default(KEYS_KEY, json.dumps(keys))
	_log("app.trust_changed", None,
	     f"unsigned apps {'allowed' if unsigned_allowed() else 'refused'}, "
	     f"{len(trusted_keys())} trusted key(s)")
	return {"unsigned_allowed": unsigned_allowed(), "trusted_keys": len(trusted_keys())}


# --- the app: pair --------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=600)
def pair(code: str, app_id: str) -> dict:
	"""The one unauthenticated endpoint: the app trades its one-time code for
	its key and secret. Every attempt that gets past the rate limit is in the
	Agent Action Log. A refused attempt gets HTTP 403 and
	{"error": "invalid_code"}."""
	app_id = str(app_id or "")[:64]
	row = None
	if code:
		row = frappe.db.get_value(
			"Kamra App", {"code_hash": _code_hash(code)},
			["name", "app_name", "status", "code_expires", "service_account", "scopes",
			 "properties"], as_dict=True, for_update=True)
	why = None
	if not row or row.name != app_id:
		why = "unknown code"
	elif row.status != "Pending":
		why = "not waiting to pair"
	elif not row.code_expires or row.code_expires < now_datetime():
		why = "code expired"
	ip = getattr(frappe.local, "request_ip", None) or "?"
	_log("app.pair_attempt", row.name if row else None,
	     f"{app_id or '(no app id)'} from {ip}: {why or 'paired'}", rejected=bool(why),
	     properties=row.properties if row and not why else None)
	if why:
		# a 403 without throwing, so the request still commits and the
		# refused attempt stays in the log
		frappe.local.response.http_status_code = 403
		return {"error": "invalid_code", "error_description": _(
			"This pairing code is wrong, used or expired. Ask IT for a new one.")}

	user = frappe.db.get_value("Kamra Service Account", row.service_account, "user")
	keys = sa._new_secret(user)
	frappe.db.set_value("Kamra App", row.name, {
		"status": "Paired", "paired_on": now_datetime(), "code_hash": None,
		"code_expires": None})
	props = sa._parse(row.properties)
	names = dict(frappe.get_all("Property", filters={"name": ["in", props]},
	                            fields=["name", "property_name"], as_list=True))
	return {
		"app_id": row.name, "site_url": get_url(), "mcp_url": get_url("/mcp"),
		**keys, "scopes": sa._parse(row.scopes),
		"properties": [{"property": p, "property_name": names.get(p, p)} for p in props],
	}


# --- the switcher ---------------------------------------------------------------------


@frappe.whitelist()
def my_apps() -> list[dict]:
	"""Paired apps the signed-in person may see: admins see every one, staff
	the ones whose manifest names one of their roles."""
	roles = set(frappe.get_roles())
	admin = bool(roles & set(ADMIN))
	rows = frappe.get_all("Kamra App", filters={"status": "Paired"},
	                      fields=["name", "app_name", "icon", "url", "roles"],
	                      order_by="app_name asc")
	return [{"app_id": r.name, "name": r.app_name, "icon": r.icon, "url": r.url}
	        for r in rows if admin or roles & set(sa._parse(r.roles))]


# --- what a paired app may read -------------------------------------------------------


@frappe.whitelist()
@require_roles(*READ_ROLES)
def property_profile(property: str) -> dict:
	"""Read-only branding and locale for one property: name, logo, address,
	tax ID, currency, language, time zone, check-in and check-out times."""
	from kamra.localization import pack_for

	prop = frappe.get_cached_doc("Property", property)
	loc = pack_for(property).locale(prop)
	logo = prop.logo_url or ""
	return {
		"property": prop.name,
		"name": prop.property_name,
		"legal_name": prop.legal_name or prop.property_name,
		"logo_url": (logo if logo.startswith("http") else get_url(logo)) if logo else None,
		"address": {"line": prop.address_line, "city": prop.city, "state": prop.state,
		            "country": prop.country, "postal_code": prop.pincode},
		"phone": prop.phone, "email": prop.email, "website": prop.website,
		"tax_id": prop.gstin or None,
		"tax_id_label": loc.get("tax_id_label"),
		"currency": loc.get("currency") or prop.currency,
		"locale": loc.get("locale"),
		"language": prop.booking_language or (prop.locale or loc.get("locale") or "en").split("-")[0],
		"timezone": prop.timezone or frappe.utils.get_system_timezone(),
		"checkin_time": str(prop.checkin_time) if prop.checkin_time else None,
		"checkout_time": str(prop.checkout_time) if prop.checkout_time else None,
	}
