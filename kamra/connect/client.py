"""Kamra Connect, install side - only what Kamra Verify needs.

The hub (hub.kamrapms.com by default) runs paid checks with Kamra's own
verification keys and charges each successful one to this install's
Connect wallet, so a hotel needs no verification account of its own.
Off until an owner links the install with a Connect key.

Which checks a property may run is its country pack's call (see
kamra.localization.india.verify); this module only talks to the hub.
"""

import json

import frappe

from kamra.authz import require_perm

DEFAULT_HUB = "https://hub.kamrapms.com"
HUB_API = "kamra_hub.api"
KEY_HEADER = "X-Kamra-Connect-Key"
SETTINGS = "Kamra Connect Settings"

_transport = {"fn": None}


def use_transport(fn=None):
	"""Tests swap in an in-process hub: callable(name, key, json_body=None,
	params=None, data=None) -> response body. None restores HTTP."""
	_transport["fn"] = fn


def _settings():
	return frappe.get_single(SETTINGS)


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


def call(name: str, s=None, *, key: str | None = None, json_body: dict | None = None,
         params: dict | None = None, data: bytes | None = None):
	"""One hub method. Raises with the hub's own message on failure."""
	s = s or _settings()
	if key is None:
		key = _key(s) if s.linked else ""
	if not key:
		frappe.throw("Link Kamra Connect first: Settings → Kamra Verify.")
	if _transport["fn"]:
		return _transport["fn"](name, key, json_body=json_body, params=params, data=data)

	import requests

	headers = {KEY_HEADER: key}
	if data is not None:
		# raw upload: arguments ride in the query string
		headers["Content-Type"] = "application/octet-stream"
		body = None
	else:
		# Frappe reads arguments from a JSON body and ignores the query
		# string when one is present, so everything goes in the body
		body = {**(json_body or {}), **(params or {})}
		params = None
	try:
		resp = requests.post(f"{_hub(s)}/api/method/{HUB_API}.{name}",
		                     json=body, data=data, params=params, headers=headers, timeout=60)
	except requests.RequestException as e:
		frappe.throw(f"Kamra Connect hub is unreachable: {e}")
	if resp.status_code >= 400:
		frappe.throw(f"Kamra Connect: {_error_message(resp)}")
	return resp.json().get("message")


@frappe.whitelist()
@require_perm("Property", "configure")
def status() -> dict:
	s = _settings()
	return {"linked": bool(s.linked), "hub_url": _hub(s)}


@frappe.whitelist(methods=["POST"])
@require_perm("Property", "configure")
def link(connect_key: str, hub_url: str | None = None) -> dict:
	"""Link with a key issued by Kamra or a partner. The hub must know the
	key before it is saved."""
	s = _settings()
	if hub_url:
		s.hub_url = hub_url
	key = (connect_key or "").strip()
	call("hello", s, key=key)
	s.connect_key = key
	s.linked = 1
	s.save(ignore_permissions=True)
	return status()


@frappe.whitelist(methods=["POST"])
@require_perm("Property", "configure")
def unlink() -> dict:
	s = _settings()
	s.connect_key = ""
	s.linked = 0
	s.save(ignore_permissions=True)
	return status()
