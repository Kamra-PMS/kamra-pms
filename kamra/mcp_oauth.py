"""MCP OAuth 2.1 for Claude (and any remote MCP client).

Public clients, authorization code + PKCE S256, dynamic client
registration, refresh-token rotation. Tokens are hashed at rest and
bound to a Frappe user + property — Claude acts as that person.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import time
from urllib.parse import parse_qs, quote, urlencode, urlparse

import frappe
from frappe.utils import add_to_date, get_url, now_datetime

from kamra.authz import require_roles
from kamra.mcp_tools import TOOL_COUNT

SCOPE = "kamra.mcp"
ACCESS_TTL_HOURS = 1
REFRESH_TTL_DAYS = 30
CODE_TTL_MINUTES = 10

CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"
CLAUDE_CALLBACK_COM = "https://claude.com/api/mcp/auth_callback"
LOOPBACK_PATH = "/callback"


def hash_token(raw: str) -> str:
	return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_token(nbytes: int = 32) -> str:
	return secrets.token_urlsafe(nbytes)


def pkce_s256(verifier: str) -> str:
	digest = hashlib.sha256(verifier.encode("ascii")).digest()
	return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def origin() -> str:
	return get_url().rstrip("/")


def mcp_resource_url() -> str:
	return f"{origin()}/mcp"


def issuer_url() -> str:
	return f"{origin()}/mcp/oauth"


def protected_resource_url() -> str:
	return f"{origin()}/mcp/oauth/resource"


def is_public_https(url: str | None = None) -> bool:
	parsed = urlparse(url or origin())
	host = (parsed.hostname or "").lower()
	if parsed.scheme != "https":
		return False
	if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost"):
		return False
	return True


def redirect_uri_allowed(uri: str) -> bool:
	if not uri:
		return False
	parsed = urlparse(uri)
	if uri in (CLAUDE_CALLBACK, CLAUDE_CALLBACK_COM):
		return True
	if parsed.scheme == "https" and parsed.hostname in ("claude.ai", "claude.com"):
		return parsed.path == "/api/mcp/auth_callback"
	if parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost"):
		return parsed.path == LOOPBACK_PATH
	return False


def parse_form(raw: bytes | str | None) -> dict[str, str]:
	if not raw:
		return {}
	if isinstance(raw, bytes):
		raw = raw.decode("utf-8", errors="replace")
	parsed = parse_qs(raw, keep_blank_values=True)
	return {k: (v[-1] if v else "") for k, v in parsed.items()}


def protected_resource_doc() -> dict:
	return {
		"resource": mcp_resource_url(),
		"authorization_servers": [issuer_url()],
		"bearer_methods_supported": ["header"],
		"scopes_supported": [SCOPE, "offline_access"],
	}


def authorization_server_doc() -> dict:
	base = issuer_url()
	return {
		"issuer": base,
		"authorization_endpoint": f"{base}/authorize",
		"token_endpoint": f"{base}/token",
		"registration_endpoint": f"{base}/register",
		"revocation_endpoint": f"{base}/revoke",
		"response_types_supported": ["code"],
		"grant_types_supported": ["authorization_code", "refresh_token"],
		"code_challenge_methods_supported": ["S256"],
		"token_endpoint_auth_methods_supported": ["none"],
		"scopes_supported": [SCOPE, "offline_access"],
		"client_id_metadata_document_supported": True,
	}


def claude_install_url(property_name: str, mcp_url: str | None = None) -> str:
	url = mcp_url or mcp_resource_url()
	name = f"{property_name} (Kamra)"
	return (
		"https://claude.ai/customize/connectors"
		"?modal=add-custom-connector"
		f"&connectorName={quote(name)}"
		f"&connectorUrl={quote(url, safe='')}"
	)


def _json_list(value) -> list[str]:
	if not value:
		return []
	if isinstance(value, list):
		return [str(v) for v in value]
	try:
		parsed = json.loads(value)
		if isinstance(parsed, list):
			return [str(v) for v in parsed]
	except (TypeError, ValueError):
		pass
	return [part.strip() for part in str(value).split(",") if part.strip()]


def handle_register(body: dict) -> tuple[int, dict]:
	uris = body.get("redirect_uris") or []
	if not isinstance(uris, list) or not uris:
		return 400, {"error": "invalid_client_metadata", "error_description": "redirect_uris required"}
	for uri in uris:
		if not redirect_uri_allowed(str(uri)):
			return 400, {
				"error": "invalid_redirect_uri",
				"error_description": f"redirect_uri not allowed: {uri}",
			}
	client_id = "mcp_" + secrets.token_urlsafe(18)
	issued = int(time.time())
	doc = frappe.get_doc(
		{
			"doctype": "MCP OAuth Client",
			"client_id": client_id,
			"client_name": (body.get("client_name") or "MCP client")[:140],
			"token_endpoint_auth_method": "none",
			"redirect_uris": json.dumps(list(uris)),
			"grant_types": "authorization_code,refresh_token",
			"client_id_issued_at": issued,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- persists DCR so Claude can authorize immediately
	return 201, {
		"client_id": client_id,
		"client_id_issued_at": issued,
		"redirect_uris": list(uris),
		"token_endpoint_auth_method": "none",
		"grant_types": ["authorization_code", "refresh_token"],
		"response_types": ["code"],
		"code_challenge_method": "S256",
	}


def _client(client_id: str):
	if not client_id:
		return None
	name = frappe.db.exists("MCP OAuth Client", {"client_id": client_id})
	return frappe.get_doc("MCP OAuth Client", name) if name else None


def _client_redirects(client) -> list[str]:
	return _json_list(client.redirect_uris)


def handle_authorize_get(params: dict[str, str]) -> tuple[int, str, str]:
	"""Returns status, content-type, body. 302 via Location is encoded as html meta? We return a special tuple.

	Caller uses the HTML body. Redirects are returned as status 302 with body = Location.
	"""
	user = frappe.session.user
	if not user or user == "Guest":
		here = f"{issuer_url()}/authorize?{urlencode(params)}"
		login = f"{origin()}/login?redirect-to={quote(here, safe='')}"
		return 302, "text/plain", login

	error = _authorize_query_error(params)
	if error:
		return 400, "text/html", _error_page(error)

	properties = frappe.get_all(
		"Property", fields=["name", "property_name"], order_by="property_name asc"
	)
	if not properties:
		return 400, "text/html", _error_page("This site has no property yet.")
	return 200, "text/html", _consent_page(params, user, properties)


def _authorize_query_error(params: dict[str, str]) -> str | None:
	if params.get("response_type") != "code":
		return "response_type must be code."
	if params.get("code_challenge_method", "S256") != "S256":
		return "PKCE S256 is required."
	if not params.get("code_challenge"):
		return "code_challenge is required."
	if not params.get("client_id"):
		return "client_id is required."
	client = _client(params["client_id"])
	if not client:
		return "Unknown client. Re-add the connector so Claude can register."
	redirect = params.get("redirect_uri") or ""
	if not redirect_uri_allowed(redirect):
		return "redirect_uri is not allowed."
	if redirect not in _client_redirects(client):
		return "redirect_uri does not match the registered client."
	return None


def handle_authorize_post(form: dict[str, str]) -> tuple[int, str, str]:
	user = frappe.session.user
	if not user or user == "Guest":
		return 401, "text/plain", "Sign in first."
	if form.get("decision") != "allow":
		redirect = form.get("redirect_uri") or ""
		state = form.get("state") or ""
		if redirect_uri_allowed(redirect):
			sep = "&" if "?" in redirect else "?"
			return 302, "text/plain", f"{redirect}{sep}{urlencode({'error': 'access_denied', 'state': state})}"
		return 400, "text/html", _error_page("Access denied.")

	params = {
		"response_type": "code",
		"client_id": form.get("client_id") or "",
		"redirect_uri": form.get("redirect_uri") or "",
		"state": form.get("state") or "",
		"code_challenge": form.get("code_challenge") or "",
		"code_challenge_method": "S256",
	}
	error = _authorize_query_error(params)
	if error:
		return 400, "text/html", _error_page(error)

	property_name = form.get("property") or ""
	if not property_name or not frappe.db.exists("Property", property_name):
		return 400, "text/html", _error_page("Pick a property.")

	code = new_token()
	frappe.get_doc(
		{
			"doctype": "MCP OAuth Grant",
			"user": user,
			"property": property_name,
			"client": params["client_id"],
			"redirect_uri": params["redirect_uri"],
			"scope": SCOPE,
			"code_hash": hash_token(code),
			"code_challenge": params["code_challenge"],
			"code_expires": add_to_date(now_datetime(), minutes=CODE_TTL_MINUTES),
			"revoked": 0,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- auth code must persist before the redirect

	q = {"code": code, "state": params["state"]}
	sep = "&" if "?" in params["redirect_uri"] else "?"
	return 302, "text/plain", f"{params['redirect_uri']}{sep}{urlencode(q)}"


def _oauth_error(code: str, description: str, status: int = 400) -> tuple[int, dict]:
	return status, {"error": code, "error_description": description}


def handle_token(form: dict[str, str]) -> tuple[int, dict]:
	grant_type = form.get("grant_type") or ""
	if grant_type == "authorization_code":
		return _token_from_code(form)
	if grant_type == "refresh_token":
		return _token_from_refresh(form)
	return _oauth_error("unsupported_grant_type", "Use authorization_code or refresh_token.")


def _token_from_code(form: dict[str, str]) -> tuple[int, dict]:
	code = form.get("code") or ""
	verifier = form.get("code_verifier") or ""
	redirect = form.get("redirect_uri") or ""
	client_id = form.get("client_id") or ""
	if not code or not verifier:
		return _oauth_error("invalid_request", "code and code_verifier are required.")
	if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier):
		return _oauth_error("invalid_request", "code_verifier is malformed.")

	name = frappe.db.get_value("MCP OAuth Grant", {"code_hash": hash_token(code), "revoked": 0})
	if not name:
		return _oauth_error("invalid_grant", "Unknown or used authorization code.")
	grant = frappe.get_doc("MCP OAuth Grant", name)
	if grant.client and client_id and grant.client != client_id:
		return _oauth_error("invalid_grant", "client_id mismatch.")
	if grant.redirect_uri != redirect:
		return _oauth_error("invalid_grant", "redirect_uri mismatch.")
	if grant.code_expires and grant.code_expires < now_datetime():
		return _oauth_error("invalid_grant", "Authorization code expired.")
	if pkce_s256(verifier) != (grant.code_challenge or ""):
		return _oauth_error("invalid_grant", "PKCE verification failed.")
	return _issue_tokens(grant)


def _token_from_refresh(form: dict[str, str]) -> tuple[int, dict]:
	refresh = form.get("refresh_token") or ""
	if not refresh:
		return _oauth_error("invalid_request", "refresh_token is required.")
	name = frappe.db.get_value(
		"MCP OAuth Grant", {"refresh_token_hash": hash_token(refresh), "revoked": 0}
	)
	if not name:
		return _oauth_error("invalid_grant", "Unknown refresh token.")
	grant = frappe.get_doc("MCP OAuth Grant", name)
	if grant.refresh_expires and grant.refresh_expires < now_datetime():
		grant.revoked = 1
		grant.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		return _oauth_error("invalid_grant", "Refresh token expired.")
	return _issue_tokens(grant)


def _issue_tokens(grant) -> tuple[int, dict]:
	access = new_token()
	refresh = new_token()
	now = now_datetime()
	grant.code_hash = ""
	grant.code_challenge = grant.code_challenge  # keep for audit; code is spent
	grant.access_token_hash = hash_token(access)
	grant.refresh_token_hash = hash_token(refresh)
	grant.access_expires = add_to_date(now, hours=ACCESS_TTL_HOURS)
	grant.refresh_expires = add_to_date(now, days=REFRESH_TTL_DAYS)
	grant.revoked = 0
	grant.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- token exchange must persist before Claude calls /mcp
	return 200, {
		"access_token": access,
		"token_type": "Bearer",
		"expires_in": ACCESS_TTL_HOURS * 3600,
		"refresh_token": refresh,
		"scope": SCOPE,
	}


def lookup_access_token(raw: str):
	if not raw:
		return None
	name = frappe.db.get_value(
		"MCP OAuth Grant", {"access_token_hash": hash_token(raw), "revoked": 0}
	)
	if not name:
		return None
	grant = frappe.get_doc("MCP OAuth Grant", name)
	if grant.access_expires and grant.access_expires < now_datetime():
		return None
	return grant


def revoke_grants(user: str, property: str | None = None) -> int:
	filters: dict = {"user": user, "revoked": 0}
	if property:
		filters["property"] = property
	rows = frappe.get_all("MCP OAuth Grant", filters=filters, pluck="name")
	for name in rows:
		frappe.db.set_value("MCP OAuth Grant", name, "revoked", 1)
	if rows:
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
	return len(rows)


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Revenue Manager", "Housekeeping")
def connect_info(property: str) -> dict:
	"""What the Connect Claude button needs: public MCP URL, install link, status."""
	prop_name = frappe.db.get_value("Property", property, "property_name") or property
	mcp_url = mcp_resource_url()
	last = frappe.db.sql(
		"""
		SELECT name, creation, actor, action_type, rationale
		FROM `tabAgent Action Log`
		WHERE action_channel = 'MCP' AND property = %s AND actor = %s
		ORDER BY creation DESC LIMIT 1
		""",
		(property, frappe.session.user),
		as_dict=True,
	)
	active = frappe.db.count(
		"MCP OAuth Grant",
		{"user": frappe.session.user, "property": property, "revoked": 0},
	)
	return {
		"mcp_url": mcp_url,
		"issuer": issuer_url(),
		"claude_install_url": claude_install_url(prop_name, mcp_url),
		"claude_code": f"claude mcp add --transport http kamra {mcp_url}",
		"is_public_https": is_public_https(),
		"property": property,
		"property_name": prop_name,
		"user": frappe.session.user,
		"tool_count": TOOL_COUNT,
		"active_grants": int(active or 0),
		"last_mcp": last[0] if last else None,
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Finance", "Revenue Manager", "Housekeeping")
def revoke_my_grants(property: str | None = None) -> dict:
	n = revoke_grants(frappe.session.user, property or None)
	from kamra.savings import log_action

	log_action(
		"mcp_grants_revoked",
		"Property",
		property,
		property,
		rationale=f"Revoked {n} MCP grant(s)",
	)
	return {"revoked": n}


def _error_page(message: str) -> str:
	return _html_shell(
		"Could not connect",
		f"<p>{frappe.utils.escape_html(message)}</p>"
		"<p><a href='/kamra/assistant'>Back to Kamra</a></p>",
	)


def _consent_page(params: dict[str, str], user: str, properties: list[dict]) -> str:
	csrf = frappe.sessions.get_csrf_token()
	options = []
	for p in properties:
		label = frappe.utils.escape_html(p.property_name or p.name)
		options.append(f'<option value="{frappe.utils.escape_html(p.name)}">{label}</option>')
	hidden = []
	for key in (
		"client_id",
		"redirect_uri",
		"state",
		"code_challenge",
		"code_challenge_method",
		"scope",
	):
		val = frappe.utils.escape_html(params.get(key) or "")
		hidden.append(f'<input type="hidden" name="{key}" value="{val}">')
	who = frappe.utils.escape_html(user)
	return _html_shell(
		"Connect Claude to this hotel",
		f"""
		<p>Claude will act as <strong>{who}</strong> — the same role limits
		as the desk. Prices, taxes and availability stay in Kamra. Every
		action lands in the Activity log under your name.</p>
		<form method="post" action="{issuer_url()}/authorize">
		  <input type="hidden" name="csrf_token" value="{csrf}">
		  {''.join(hidden)}
		  <label>Property
		    <select name="property">{''.join(options)}</select>
		  </label>
		  <div class="row">
		    <button type="submit" name="decision" value="allow">Allow</button>
		    <button type="submit" name="decision" value="deny" class="ghost">Deny</button>
		  </div>
		</form>
		""",
	)


def _html_shell(title: str, body: str) -> str:
	return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{frappe.utils.escape_html(title)} · Kamra</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0; font: 16px/1.45 ui-sans-serif, system-ui, sans-serif;
         background:#f4f1ea; color:#1a1a1a; }}
  main {{ max-width: 28rem; margin: 12vh auto; padding: 1.75rem;
          background:#fff; border:1px solid #e5e0d5; border-radius: 16px; }}
  h1 {{ font-size: 1.25rem; margin: 0 0 .75rem; }}
  p {{ color:#444; }}
  label {{ display:block; font-size:.85rem; font-weight:600; margin: 1rem 0 .4rem; }}
  select {{ width:100%; padding:.55rem .7rem; border:1px solid #ccc; border-radius:8px; }}
  .row {{ display:flex; gap:.6rem; margin-top: 1.25rem; }}
  button {{ flex:1; padding:.7rem 1rem; border:0; border-radius:999px;
            background:#1E7B4F; color:#fff; font-weight:600; cursor:pointer; }}
  button.ghost {{ background:#fff; color:#333; border:1px solid #ccc; }}
  a {{ color:#1E7B4F; }}
</style>
</head>
<body><main><h1>{frappe.utils.escape_html(title)}</h1>{body}</main></body>
</html>"""
