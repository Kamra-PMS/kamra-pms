# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Push one day's closed invoices to ERPNext.

Same-site uses the ERPNext app when it is installed on this bench.
Remote POSTs a Journal Entry to the hotel's ERPNext site with a token.
Neither path invents a posted entry: a missing account, a missing app, or
an HTTP error comes back as a failure the desk can read.

The entry is one summary voucher per property per date, keyed by
cheque_no KAMRA-<property>-<date>, so a second run does not duplicate it.
CSV export for Tally and Zoho stays on the Accounting Export screen.
"""

from __future__ import annotations

import json

import frappe
from frappe.utils import cint

from kamra.enterprise_http import request_json
from kamra.enterprise_logic import build_journal, erpnext_payload


def sync_day(property: str, business_date: str) -> dict:
	from kamra.accounting import export_invoices
	from kamra.settings import get_setting

	mode = get_setting(property, "ent_erp_mode", "off") or "off"
	if mode not in ("same_site", "remote"):
		return {"ok": False, "posted": False, "reason": "ERPNext sync is off."}
	existing = _existing(property, business_date)
	if existing and existing.get("status") == "Posted":
		return {"ok": True, "posted": True, "replayed": True,
		        "external_id": existing.get("external_id"),
		        "name": existing.get("name")}
	exported = export_invoices(property, business_date, business_date)
	rows = exported.get("rows") or []
	if not rows:
		return {"ok": True, "posted": False, "reason": "nothing_to_post",
		        "invoices": 0}
	accounts = {
		"debtors": get_setting(property, "ent_acct_debtors", "") or "",
		"room": get_setting(property, "ent_acct_room", "") or "",
		"fnb": get_setting(property, "ent_acct_fnb", "") or "",
		"tax": get_setting(property, "ent_acct_tax", "") or "",
	}
	journal = build_journal(rows, accounts)
	if not journal["ok"]:
		name = _record(property, business_date, mode, "Failed", "", journal["error"], len(rows))
		return {"ok": False, "posted": False, "reason": journal["error"], "name": name}
	company = (get_setting(property, "ent_erp_company", "") or "").strip()
	remark = f"KAMRA-{property}-{business_date}"[:140]
	payload = erpnext_payload(company, business_date, remark, journal["lines"])
	if mode == "same_site":
		result = _post_same_site(payload, remark)
	else:
		result = _post_remote(property, payload, remark)
	status = "Posted" if result["ok"] else "Failed"
	name = _record(property, business_date, mode, status,
	               result.get("external_id") or "", result.get("error") or "", len(rows))
	return {"ok": result["ok"], "posted": result["ok"], "name": name,
	        "external_id": result.get("external_id") or "",
	        "reason": result.get("error"), "invoices": len(rows),
	        "replayed": bool(result.get("replayed"))}


def _post_same_site(payload: dict, remark: str) -> dict:
	if "erpnext" not in frappe.get_installed_apps():
		return {"ok": False, "error": "ERPNext is not installed on this site. "
		        "Use remote mode, or install ERPNext. CSV export still works."}
	if not payload.get("company"):
		company = frappe.db.get_value("Company", {}, "name")
		if not company:
			return {"ok": False, "error": "Set the ERPNext company."}
		payload["company"] = company
	found = frappe.db.get_value("Journal Entry", {"cheque_no": remark}, "name")
	if found:
		return {"ok": True, "external_id": found, "replayed": True}
	try:
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return {"ok": True, "external_id": doc.name}
	except Exception as exc:
		frappe.log_error(title="Enterprise ERPNext sync")
		return {"ok": False, "error": str(exc)[:500]}


def _post_remote(property: str, payload: dict, remark: str) -> dict:
	from kamra.settings import get_setting
	base = (get_setting(property, "ent_erp_url", "") or "").strip().rstrip("/")
	key = (get_setting(property, "ent_erp_key", "") or "").strip()
	secret = _secret(property)
	if not (base and key and secret and payload.get("company")):
		return {"ok": False, "error": "Set the ERPNext URL, API key, API secret and company."}
	from urllib.parse import quote, urlencode
	headers = {"Authorization": f"token {key}:{secret}"}
	query = urlencode({
		"filters": json.dumps([["cheque_no", "=", remark]]),
		"fields": json.dumps(["name"]),
		"limit_page_length": "1",
	})
	status, body = request_json(
		f"{base}/api/resource/{quote('Journal Entry')}?{query}",
		headers=headers, method="GET")
	if 200 <= status < 300:
		try:
			data = json.loads(body).get("data") or []
		except json.JSONDecodeError:
			data = []
		if data:
			return {"ok": True, "external_id": data[0].get("name") or remark, "replayed": True}
	status, body = request_json(f"{base}/api/resource/Journal%20Entry", payload, headers=headers)
	if not (200 <= status < 300):
		return {"ok": False, "error": (body or f"HTTP {status}")[:500]}
	try:
		external = (json.loads(body).get("data") or {}).get("name") or ""
	except json.JSONDecodeError:
		external = ""
	return {"ok": True, "external_id": external or remark}


def _secret(property: str) -> str:
	if not frappe.db.exists("DocType", "Enterprise Secret"):
		return ""
	if not frappe.db.exists("Enterprise Secret", property):
		return ""
	return frappe.get_doc("Enterprise Secret", property).get_password(
		"erpnext_api_secret", raise_exception=False) or ""


def _existing(property: str, business_date: str):
	rows = frappe.get_all(
		"Accounting Sync Log",
		filters={"property": property, "business_date": business_date, "status": "Posted"},
		fields=["name", "status", "external_id"],
		limit=1,
	)
	return rows[0] if rows else None


def _record(property, business_date, adapter, status, external_id, error, invoices) -> str:
	doc = frappe.get_doc({
		"doctype": "Accounting Sync Log",
		"property": property,
		"business_date": business_date,
		"adapter": "ERPNext" if adapter == "same_site" else "ERPNext remote",
		"status": status,
		"external_id": external_id,
		"voucher_count": cint(invoices),
		"error": (error or "")[:500],
	})
	doc.insert(ignore_permissions=True)
	return doc.name
