"""Kamra Connect, install side.

Links this Kamra to a Connect hub (hub.kamrapms.com by default), checks in
hourly, and runs the nightly encrypted offsite backup. Backups are
encrypted HERE with the recovery key before upload; the hub stores
ciphertext it cannot read.

Everything is optional and off until an owner links the install from
Settings → Kamra Connect.
"""

import json
import os
import shutil

import frappe
from frappe.utils import add_days, cint, flt, get_url, now_datetime, nowdate

from kamra.authz import require_roles
from kamra.connect import crypto

DEFAULT_HUB = "https://hub.kamrapms.com"
HUB_API = "kamra_hub.api"
KEY_HEADER = "X-Kamra-Connect-Key"

# Tests swap in an in-process hub: callable(name, key, json_body=None,
# params=None, data=None, raw=False) -> response body.
TRANSPORT = None


def _settings():
	return frappe.get_single("Kamra Connect Settings")


def _key(s) -> str:
	return s.get_password("connect_key", raise_exception=False) or ""


def _hub(s) -> str:
	return (s.hub_url or DEFAULT_HUB).rstrip("/")


def _error_message(resp) -> str:
	try:
		body = resp.json()
	except ValueError:
		return f"HTTP {resp.status_code}"
	msgs = body.get("_server_messages")
	if msgs:
		try:
			return "; ".join(json.loads(m).get("message", "") for m in json.loads(msgs))
		except (ValueError, AttributeError):
			pass
	return (body.get("exception") or f"HTTP {resp.status_code}").split(":", 1)[-1].strip()


def _call(name: str, s=None, *, key: str | None = None, json_body: dict | None = None,
          params: dict | None = None, data: bytes | None = None, raw: bool = False):
	s = s or _settings()
	key = _key(s) if key is None else key
	if TRANSPORT:
		return TRANSPORT(name, key, json_body=json_body, params=params, data=data, raw=raw)

	import requests

	headers = {KEY_HEADER: key}
	if data is not None:
		# raw chunk upload: arguments ride in the query string
		headers["Content-Type"] = "application/octet-stream"
		body = None
	else:
		# Frappe reads arguments from a JSON body and ignores the query
		# string when one is present, so everything goes in the body
		body = {**(json_body or {}), **(params or {})}
		params = None
	try:
		resp = requests.post(f"{_hub(s)}/api/method/{HUB_API}.{name}",
		                     json=body, data=data, params=params, headers=headers, timeout=120)
	except requests.RequestException as e:
		frappe.throw(f"Kamra Connect hub is unreachable: {e}")
	if resp.status_code >= 400:
		frappe.throw(f"Kamra Connect: {_error_message(resp)}")
	return resp.content if raw else resp.json().get("message")


# ---------------------------------------------------------------- facts

def _facts() -> dict:
	"""What a check-in reports. No guest data, ever: versions, health, and
	(only with share_benchmarks) yesterday's occupancy and ADR."""
	import kamra

	props = frappe.get_all("Property", fields=["name", "city", "country", "currency"],
	                       order_by="creation asc")
	rooms = frappe.db.count("Room")
	try:
		disk = shutil.disk_usage(frappe.get_site_path())
		disk_free_gb = round(disk.free / 1024 ** 3, 1)
	except OSError:
		disk_free_gb = None
	from frappe.utils.scheduler import is_scheduler_disabled

	return {
		"site_url": get_url(),
		"kamra_version": kamra.__version__,
		"frappe_version": frappe.__version__,
		"city": props[0].city if props else "",
		"country": props[0].country if props else "",
		"rooms": rooms,
		"health": {"disk_free_gb": disk_free_gb,
		           "scheduler": not is_scheduler_disabled(),
		           "properties": len(props)},
	}


def _metrics() -> dict | None:
	"""Yesterday, across all properties: occupancy % and ADR."""
	from kamra.reports import _day_stats

	day = add_days(nowdate(), -1)
	sold = total = revenue = 0
	currency = ""
	for p in frappe.get_all("Property", fields=["name", "currency"]):
		n = frappe.db.count("Room", {"property": p.name})
		if not n:
			continue
		st = _day_stats(p.name, day, n)
		sold += cint(st.get("rooms_sold"))
		total += n
		revenue += flt(st.get("adr")) * cint(st.get("rooms_sold"))
		currency = currency or (p.currency or "")
	if not total:
		return None
	return {"date": str(day), "occupancy": round(100 * sold / total, 1),
	        "adr": round(revenue / sold, 0) if sold else 0, "rooms": total,
	        "currency": currency}


def _store(s, summary: dict):
	"""Copy what the hub said about this install onto Settings."""
	s.linked = 1
	s.install_name = summary.get("install")
	s.owner_email = summary.get("owner_email")
	s.plan = summary.get("plan")
	s.plan_expires = summary.get("plan_expires")
	s.wallet_balance = flt(summary.get("wallet_balance"))
	s.monitor_state = summary.get("monitor_state")
	s.entitlements = json.dumps(summary.get("entitlements") or {})
	if "advisories" in summary:
		s.advisories = json.dumps(summary.get("advisories") or [])
	if "benchmark" in summary:
		s.benchmark = json.dumps(summary.get("benchmark"))


def _ensure_recovery_key(s):
	if not s.get_password("recovery_key", raise_exception=False):
		s.recovery_key = crypto.new_key()


# ---------------------------------------------------------------- linking

@frappe.whitelist()
@require_roles("System Manager", "Hotel Admin")
def status() -> dict:
	s = _settings()
	return {
		"linked": bool(s.linked), "hub_url": _hub(s), "install": s.install_name,
		"owner_email": s.owner_email, "plan": s.plan, "plan_expires": str(s.plan_expires or "") or None,
		"wallet_balance": flt(s.wallet_balance), "monitor_state": s.monitor_state,
		"backup_enabled": bool(s.backup_enabled), "share_benchmarks": bool(s.share_benchmarks),
		"last_heartbeat": str(s.last_heartbeat or "") or None,
		"last_backup": str(s.last_backup or "") or None,
		"last_backup_status": s.last_backup_status, "last_restore": s.last_restore,
		"has_recovery_key": bool(s.get_password("recovery_key", raise_exception=False)),
		"entitlements": json.loads(s.entitlements or "{}"),
		"advisories": json.loads(s.advisories or "[]"),
		"benchmark": json.loads(s.benchmark or "null"),
	}


@frappe.whitelist(methods=["POST"])
@require_roles("System Manager", "Hotel Admin")
def register(owner_email: str, hub_url: str | None = None) -> dict:
	"""Register this install on the hub (Free plan: security and update
	advisories) and link it in one step."""
	s = _settings()
	if hub_url:
		s.hub_url = hub_url
	f = _facts()
	out = _call("register", s, key="", json_body={
		"owner_email": owner_email, "site_url": f["site_url"],
		"label": frappe.db.get_value("Property", {}, "property_name") or f["site_url"],
		"kamra_version": f["kamra_version"], "city": f["city"], "country": f["country"],
		"rooms": f["rooms"]})
	s.connect_key = out["key"]
	_store(s, out)
	_ensure_recovery_key(s)
	s.save(ignore_permissions=True)
	heartbeat()
	return status()


@frappe.whitelist(methods=["POST"])
@require_roles("System Manager", "Hotel Admin")
def link(connect_key: str, hub_url: str | None = None) -> dict:
	"""Link with a key issued by Kamra or a partner."""
	s = _settings()
	if hub_url:
		s.hub_url = hub_url
	out = _call("hello", s, key=connect_key.strip())
	s.connect_key = connect_key.strip()
	_store(s, out)
	_ensure_recovery_key(s)
	s.save(ignore_permissions=True)
	heartbeat()
	return status()


@frappe.whitelist(methods=["POST"])
@require_roles("System Manager", "Hotel Admin")
def unlink() -> dict:
	"""Stop checking in. The recovery key stays, so existing backups can
	still be restored if the install is linked again."""
	s = _settings()
	s.connect_key = ""
	s.linked = 0
	s.save(ignore_permissions=True)
	return status()


@frappe.whitelist(methods=["POST"])
@require_roles("System Manager", "Hotel Admin")
def update_preferences(backup_enabled: int | None = None, share_benchmarks: int | None = None):
	s = _settings()
	if backup_enabled is not None:
		s.backup_enabled = cint(backup_enabled)
	if share_benchmarks is not None:
		s.share_benchmarks = cint(share_benchmarks)
	s.save(ignore_permissions=True)
	return status()


@frappe.whitelist()
@require_roles("System Manager")
def reveal_recovery_key() -> dict:
	"""Shown so the owner can store it offline. Without it, a backup
	cannot be restored on a new server."""
	s = _settings()
	_ensure_recovery_key(s)
	s.save(ignore_permissions=True)
	return {"recovery_key": s.get_password("recovery_key")}


@frappe.whitelist(methods=["POST"])
@require_roles("System Manager")
def set_recovery_key(recovery_key: str) -> dict:
	"""On a rebuilt server: paste the old key to restore old backups."""
	from cryptography.fernet import Fernet

	try:
		Fernet(recovery_key.strip().encode())
	except (ValueError, TypeError):
		frappe.throw("That is not a valid recovery key.")
	s = _settings()
	s.recovery_key = recovery_key.strip()
	s.save(ignore_permissions=True)
	return status()


# ---------------------------------------------------------------- check-in

def heartbeat() -> dict | None:
	"""Hourly. Silently skips when not linked."""
	s = _settings()
	if not s.linked or not _key(s):
		return None
	f = _facts()
	if s.share_benchmarks:
		try:
			f["metrics"] = _metrics()
		except Exception:
			frappe.log_error(title="Kamra Connect: benchmark metrics failed")
	out = _call("heartbeat", s, json_body=f)
	_store(s, out)
	s.last_heartbeat = now_datetime()
	s.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- scheduler job; persist the hub's reply
	return out


@frappe.whitelist(methods=["POST"])
@require_roles("System Manager", "Hotel Admin")
def refresh() -> dict:
	heartbeat()
	return status()


# ---------------------------------------------------------------- plans & money

@frappe.whitelist(methods=["POST"])
@require_roles("System Manager", "Hotel Admin")
def start_trial() -> dict:
	s = _settings()
	_store(s, _call("start_trial", s))
	s.save(ignore_permissions=True)
	return status()


@frappe.whitelist(methods=["POST"])
@require_roles("System Manager", "Hotel Admin")
def subscribe(plan: str, phone: str = "") -> dict:
	"""Opens Cashfree checkout (card, UPI AutoPay or bank mandate). Cashfree
	needs a mobile number for payment notices."""
	return _call("subscribe", json_body={"plan": plan, "phone": phone})


@frappe.whitelist(methods=["POST"])
@require_roles("System Manager", "Hotel Admin")
def topup(amount: float, phone: str = "") -> dict:
	return _call("topup", json_body={"amount": flt(amount), "phone": phone})


@frappe.whitelist(methods=["POST"])
@require_roles("System Manager", "Hotel Admin")
def use_connect_ai(property: str) -> dict:
	"""Point this property's Kamra Agent at the hub's metered AI: no API
	key of the hotel's own needed."""
	s = _settings()
	if not s.linked:
		frappe.throw("Link Kamra Connect first.")
	name = frappe.db.get_value("AI Assistant Settings", {"property": property})
	doc = frappe.get_doc("AI Assistant Settings", name) if name else frappe.new_doc("AI Assistant Settings")
	doc.property = property
	doc.enabled = 1
	doc.base_url = f"{_hub(s)}/connect/ai/v1"
	doc.model = "kamra"
	doc.api_key = _key(s)
	doc.save(ignore_permissions=True)
	return {"ok": True, "base_url": doc.base_url}


# ---------------------------------------------------------------- Kamra Verify
# Identity and business checks run by the hub, paid per check from the
# Connect wallet. The hotel needs no verification account of its own.

_GENDERS = {"m": "Male", "male": "Male", "f": "Female", "female": "Female",
            "t": "Other", "transgender": "Other", "other": "Other"}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance")
def verify_gstin(gstin: str, business_name: str = "") -> dict:
	"""A corporate guest's GSTIN: is it active, and whose is it."""
	out = _call("verify_gstin", json_body={"gstin": gstin, "business_name": business_name})
	from kamra.savings import log_action
	log_action("verify_gstin", "Company", None, None, minutes_saved=5,
	           rationale=f"GSTIN {out.get('gstin')} {'valid' if out.get('valid') else 'NOT valid'}"
	                     f" · {out.get('legal_name') or '-'}", channel="API")
	return out


@frappe.whitelist(methods=["POST"])
@require_roles("Finance")
def verify_bank(account: str, ifsc: str, name: str = "") -> dict:
	"""A bank account before money is sent to it (e.g. a partner payout)."""
	return _call("verify_bank", json_body={"account": account, "ifsc": ifsc, "name": name})


def _file_bytes(url: str) -> tuple[bytes, str]:
	name = frappe.db.get_value("File", {"file_url": url})
	if not name:
		frappe.throw("The ID image is not on file. Capture it first.")
	f = frappe.get_doc("File", name)
	return f.get_content(), f.file_name or "id.jpg"


def _as_date(value: str):
	from frappe.utils import getdate

	for v in (value, (value or "").replace("/", "-")):
		try:
			d = getdate(v)
			if d and 1900 < d.year <= now_datetime().year:
				return d
		except Exception:
			pass
	return None


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk")
def scan_guest_id(guest: str, id_type: str) -> dict:
	"""Read the guest's ID document on file and fill the profile: ID type
	and number, date of birth, gender, nationality; name and address only
	where the profile has none. Aadhaar numbers arrive already masked."""
	if not frappe.db.exists("Guest", guest):
		frappe.throw("Guest not found.")
	g = frappe.get_doc("Guest", guest)
	if not g.id_file:
		frappe.throw("Capture the ID document first, then read it.")
	image, filename = _file_bytes(g.id_file)
	out = _call("scan_id", params={"id_type": id_type, "filename": filename}, data=image)

	filled = {}
	def put(field, value, only_if_empty=False):
		if value and (not only_if_empty or not g.get(field)) and g.get(field) != value:
			g.set(field, value)
			filled[field] = value

	put("id_type", id_type)
	put("id_number", out.get("id_number"))
	put("date_of_birth", _as_date(out.get("date_of_birth") or ""))
	put("gender", _GENDERS.get((out.get("gender") or "").strip().lower()))
	put("nationality", out.get("nationality"), only_if_empty=True)
	put("address_line", (out.get("address") or "")[:140], only_if_empty=True)
	if out.get("name") and not (g.first_name or "").strip():
		first, _, last = out["name"].strip().partition(" ")
		put("first_name", first)
		put("last_name", last)
	if filled:
		g.save(ignore_permissions=True)
	from kamra.savings import log_action
	log_action("scan_guest_id", "Guest", g.name, None, minutes_saved=3,
	           rationale=f"{id_type} read by Kamra Verify; filled {', '.join(filled) or 'nothing new'}",
	           channel="API")
	return {"filled": {k: str(v) for k, v in filled.items()}, "read": out,
	        "charged": out.get("charged")}


# ---------------------------------------------------------------- backups

def upload_files(paths: list[str], s=None) -> dict:
	"""Encrypt each file in chunks and upload it as one backup."""
	import kamra

	s = s or _settings()
	rk = s.get_password("recovery_key", raise_exception=False)
	if not rk:
		frappe.throw("No recovery key on this install; open Settings → Kamra Connect.")
	begin = _call("backup_begin", s, json_body={"kamra_version": kamra.__version__})
	backup = begin["backup"]
	files = []
	for path in paths:
		if not path or not os.path.exists(path):
			continue
		name = os.path.basename(path)
		chunks = 0
		for index, token in crypto.encrypted_chunks(path, rk):
			_call("backup_chunk", s, params={"backup": backup, "file": name, "index": index},
			      data=token)
			chunks = index + 1
		files.append({"name": name, "chunks": chunks, "bytes": os.path.getsize(path),
		              "sha256": crypto.file_sha256(path)})
	if not files:
		frappe.throw("Nothing to back up.")
	_call("backup_finish", s, json_body={"backup": backup, "manifest": {"files": files}})
	return {"backup": backup, "files": files}


def run_backup() -> dict:
	"""Take a fresh site backup (database + files) and ship it offsite."""
	from frappe.utils.backups import new_backup

	s = _settings()
	try:
		odb = new_backup(ignore_files=False, force=True)
		paths = [odb.backup_path_db, odb.backup_path_files, odb.backup_path_private_files,
		         getattr(odb, "backup_path_conf", None)]
		out = upload_files([p for p in paths if p], s)
		size = sum(f["bytes"] for f in out["files"])
		s.last_backup = now_datetime()
		s.last_backup_status = f"OK · {out['backup']} · {size / 1024 ** 2:,.1f} MB before encryption"
	except Exception as e:
		frappe.log_error(title="Kamra Connect backup failed")
		s.last_backup_status = f"Failed: {e}"[:500]
		out = None
	s.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- background job; record the result
	return out


def scheduled_backup():
	"""Nightly, only when linked, entitled and switched on."""
	s = _settings()
	if not (s.linked and s.backup_enabled and _key(s)):
		return
	if not json.loads(s.entitlements or "{}").get("backups"):
		return
	run_backup()


@frappe.whitelist(methods=["POST"])
@require_roles("System Manager", "Hotel Admin")
def backup_now() -> dict:
	frappe.enqueue("kamra.connect.client.run_backup", queue="long", timeout=7200)
	return {"queued": True}


@frappe.whitelist()
@require_roles("System Manager", "Hotel Admin")
def list_backups() -> list[dict]:
	return _call("backup_list")


def download_backup(backup: str, s=None) -> dict:
	"""Fetch, decrypt and verify a backup into private/backups/connect-restore/."""
	s = s or _settings()
	rk = s.get_password("recovery_key", raise_exception=False)
	if not rk:
		frappe.throw("Set the recovery key for these backups first.")
	match = next((b for b in _call("backup_list", s) if b["name"] == backup), None)
	if not match:
		frappe.throw(f"Backup {backup} is not available.")
	dest = frappe.get_site_path("private", "backups", "connect-restore", backup)
	os.makedirs(dest, exist_ok=True)
	written = []
	for f in match["manifest"]["files"]:
		path = os.path.join(dest, f["name"])
		with open(path, "wb") as out:
			for i in range(cint(f["chunks"])):
				blob = _call("backup_fetch", s, params={"backup": backup, "file": f["name"], "index": i},
				             raw=True)
				out.write(crypto.decrypt_chunk(blob, rk))
		if crypto.file_sha256(path) != f["sha256"]:
			frappe.throw(f"{f['name']} failed its integrity check after download.")
		written.append(os.path.abspath(path))
	db = next((p for p in written if p.endswith(".sql.gz") or p.endswith(".sql")), "")
	pub = next((p for p in written if p.endswith(("-files.tar", "-files.tgz"))
	            and "private-files" not in os.path.basename(p)), "")
	priv = next((p for p in written if "private-files" in os.path.basename(p)), "")
	cmd = f"bench --site {frappe.local.site} restore {db}"
	if pub:
		cmd += f" --with-public-files {pub}"
	if priv:
		cmd += f" --with-private-files {priv}"
	return {"backup": backup, "files": written, "command": cmd}


def _download_job(backup: str):
	s = _settings()
	try:
		out = download_backup(backup, s)
		s.last_restore = f"{out['backup']} ready. Run on the server:\n{out['command']}"
	except Exception as e:
		frappe.log_error(title="Kamra Connect restore download failed")
		s.last_restore = f"Download of {backup} failed: {e}"[:1000]
	s.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- background job; record the result


@frappe.whitelist(methods=["POST"])
@require_roles("System Manager")
def prepare_restore(backup: str) -> dict:
	"""Download and decrypt in the background; Settings shows the restore
	command when it is ready. Restoring replaces the site, so a person
	runs that command, never Kamra on its own."""
	frappe.enqueue("kamra.connect.client._download_job", queue="long", timeout=7200,
	               backup=backup)
	return {"queued": True}
