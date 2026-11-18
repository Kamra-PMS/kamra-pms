# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""SMS providers for Enterprise.

`log` records the message and does not send it. Use it to check the text
before a provider is connected. `http` POSTs JSON to the URL in Settings.
The hotel's SMS vendor (or a small proxy in front of one) accepts:

    {"to", "from", "text", "property", "purpose"}

and returns 2xx. A JSON body may include "id" or "message_id".
The auth header name is a setting; the secret is stored encrypted on
Enterprise Secret, not in the settings log.
"""

from __future__ import annotations

import frappe

from kamra.enterprise_http import request_json
from kamra.enterprise_logic import auth_header, parse_provider_json


def send_sms(property: str, to: str, body: str, *, purpose: str,
             guest: str | None = None, reservation: str | None = None) -> dict:
	"""Send or log one SMS. Never raises. Does not claim a log row was sent."""
	from kamra.settings import get_setting
	provider = get_setting(property, "ent_sms_provider", "none") or "none"
	if provider not in ("http", "log"):
		return {"ok": False, "status": "Not configured",
		        "reason": "Choose an SMS provider under Settings, Enterprise."}
	if not (to or "").strip():
		return {"ok": False, "status": "Failed", "reason": "No phone number."}
	if provider == "log":
		name = _log(property, to, body, purpose, "Logged", "log", "", "",
		            guest, reservation)
		return {"ok": True, "sent": False, "logged": True, "status": "Logged",
		        "name": name,
		        "reason": "Logged only. No SMS provider was called."}
	url = (get_setting(property, "ent_sms_url", "") or "").strip()
	if not url:
		return {"ok": False, "status": "Not configured",
		        "reason": "Set the SMS provider URL."}
	secret = _secret(property, "sms_auth")
	headers = auth_header(get_setting(property, "ent_sms_auth_header", "Authorization"), secret)
	status, text = request_json(url, {
		"to": to.strip(),
		"from": get_setting(property, "ent_sms_from", "") or "",
		"text": body[:1000],
		"property": property,
		"purpose": purpose,
	}, headers=headers)
	parsed = parse_provider_json(status, text, ok_message="SMS accepted by the provider.")
	row_status = "Sent" if parsed["ok"] else "Failed"
	name = _log(property, to, body, purpose, row_status, "http",
	            parsed["ids"][0] if parsed["ids"] else "",
	            "" if parsed["ok"] else parsed["message"], guest, reservation)
	return {"ok": parsed["ok"], "sent": parsed["ok"], "logged": False,
	        "status": row_status, "name": name,
	        "reason": None if parsed["ok"] else parsed["message"],
	        "provider_id": parsed["ids"][0] if parsed["ids"] else ""}


def _secret(property: str, field: str) -> str:
	if not frappe.db.exists("DocType", "Enterprise Secret"):
		return ""
	if not frappe.db.exists("Enterprise Secret", property):
		return ""
	doc = frappe.get_doc("Enterprise Secret", property)
	return doc.get_password(field, raise_exception=False) or ""


def _log(property, to, body, purpose, status, adapter, provider_id, error,
         guest, reservation) -> str:
	doc = frappe.get_doc({
		"doctype": "SMS Message",
		"property": property,
		"recipient": (to or "")[:140],
		"body": (body or "")[:1000],
		"purpose": purpose,
		"status": status,
		"adapter": adapter,
		"provider_id": provider_id,
		"error": (error or "")[:500],
		"guest": guest,
		"reservation": reservation,
	})
	doc.insert(ignore_permissions=True)
	return doc.name
