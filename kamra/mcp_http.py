"""Remote MCP over Streamable HTTP, served in-process on the Frappe site.

Claude (and any MCP client) POSTs JSON-RPC to /mcp with a Bearer token
from mcp_oauth. Unauthenticated calls return 401 plus protected-resource
metadata so the client can start OAuth.
"""

from __future__ import annotations

import json

import frappe
from werkzeug.wrappers import Response

from kamra.mcp_oauth import (
	authorization_server_doc,
	handle_authorize_get,
	handle_authorize_post,
	handle_register,
	handle_token,
	lookup_access_token,
	parse_form,
	protected_resource_doc,
	protected_resource_url,
)
from kamra.mcp_tools import (
	BY_NAME,
	INSTRUCTIONS,
	TOOL_COUNT,
	allowed_tools,
	call_tool,
	mcp_tool_list,
)

PROTOCOL_VERSIONS = ("2025-11-25", "2025-03-26", "2024-11-05")
CORS_HEADERS = {
	"Access-Control-Allow-Origin": "*",
	"Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
	"Access-Control-Allow-Headers": (
		"Authorization, Content-Type, Accept, MCP-Protocol-Version, Mcp-Session-Id"
	),
	"Access-Control-Expose-Headers": "Mcp-Session-Id, WWW-Authenticate",
}


class MCPPageRenderer:
	"""Intercept /mcp and /mcp/oauth/* before the SPA catch-all."""

	def __init__(self, path, http_status_code=None):
		self.path = (path or "").lstrip("/")
		self.http_status_code = http_status_code

	def can_render(self):
		return self.path == "mcp" or self.path.startswith("mcp/")

	def render(self):
		return dispatch(self.path, frappe.request)


def dispatch(path: str, request) -> Response:
	method = (request.method or "GET").upper()
	if method == "OPTIONS":
		return _response("", 204)

	if path == "mcp/.well-known/oauth-protected-resource":
		return _json(protected_resource_doc())
	if path in (
		"mcp/oauth/.well-known/oauth-authorization-server",
		"mcp/oauth/metadata",
	):
		return _json(authorization_server_doc())

	if path == "mcp/oauth/register":
		if method != "POST":
			return _json({"error": "method_not_allowed"}, 405)
		body = _read_json(request)
		status, payload = handle_register(body)
		return _json(payload, status)

	if path == "mcp/oauth/token":
		if method != "POST":
			return _json({"error": "method_not_allowed"}, 405)
		form = parse_form(request.get_data() or b"")
		if not form and getattr(request, "form", None):
			form = {k: request.form.get(k) for k in request.form}
		status, payload = handle_token(form)
		return _json(payload, status)

	if path == "mcp/oauth/authorize":
		return _authorize(method, request)

	if path == "mcp":
		return _mcp_endpoint(method, request)

	return _json({"error": "not_found"}, 404)


def _authorize(method: str, request) -> Response:
	if method == "GET":
		params = {k: request.args.get(k) for k in request.args}
		status, ctype, body = handle_authorize_get({k: v or "" for k, v in params.items()})
	elif method == "POST":
		form = parse_form(request.get_data() or b"")
		if not form and getattr(request, "form", None):
			form = {k: request.form.get(k) for k in request.form}
		status, ctype, body = handle_authorize_post(form)
	else:
		return _json({"error": "method_not_allowed"}, 405)
	if status == 302:
		resp = Response("", status=302)
		resp.headers["Location"] = body
		_apply_cors(resp)
		return resp
	resp = Response(body, status=status, content_type=f"{ctype}; charset=utf-8")
	_apply_cors(resp)
	return resp


def _mcp_endpoint(method: str, request) -> Response:
	grant = _bearer(request)
	if method == "DELETE":
		if not grant:
			return _unauthorized()
		return _response("", 204)
	if method == "GET":
		# SSE not implemented; Claude's JSON POST path is enough.
		if not grant:
			return _unauthorized()
		return _response("", 405)
	if method != "POST":
		return _json({"error": "method_not_allowed"}, 405)
	if not grant:
		return _unauthorized()

	frappe.set_user(grant.user)  # nosemgrep: frappe-setuser -- OAuth bearer already validated; impersonate the grant owner for role-filtered MCP tools
	body = _read_json(request)
	if body is None:
		return _rpc_error(None, -32700, "Parse error", 400)
	if isinstance(body, list):
		replies = [_handle_rpc(item, grant) for item in body]
		replies = [r for r in replies if r is not None]
		return _json(replies if replies else None, 200 if replies else 202)
	reply = _handle_rpc(body, grant)
	if reply is None:
		return _response("", 202)
	return _json(reply)


def _bearer(request):
	header = request.headers.get("Authorization") or ""
	if not header.lower().startswith("bearer "):
		return None
	return lookup_access_token(header.split(" ", 1)[1].strip())


def _unauthorized() -> Response:
	resp = _json(
		{
			"error": "invalid_token",
			"error_description": "Sign in with OAuth to use Kamra MCP.",
		},
		401,
	)
	resp.headers["WWW-Authenticate"] = (
		'Bearer realm="Kamra", '
		f'resource_metadata="{protected_resource_url()}", '
		'scope="kamra.mcp"'
	)
	return resp


def _handle_rpc(msg: dict, grant) -> dict | None:
	if not isinstance(msg, dict):
		return _rpc_error_body(None, -32600, "Invalid Request")
	rpc_id = msg.get("id", _MISSING)
	method = msg.get("method") or ""
	params = msg.get("params") or {}
	notification = rpc_id is _MISSING
	try:
		result = _dispatch_method(method, params, grant)
	except Exception as exc:
		if notification:
			return None
		return _rpc_error_body(msg.get("id"), -32000, str(exc)[:400])
	if notification:
		return None
	return {"jsonrpc": "2.0", "id": msg.get("id"), "result": result}


_MISSING = object()


def _dispatch_method(method: str, params: dict, grant) -> dict:
	if method == "initialize":
		requested = (params.get("protocolVersion") or PROTOCOL_VERSIONS[0])
		version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[1]
		return {
			"protocolVersion": version,
			"capabilities": {"tools": {"listChanged": False}},
			"serverInfo": {"name": "kamra", "version": str(TOOL_COUNT), "title": "Kamra PMS"},
			"instructions": INSTRUCTIONS,
		}
	if method in ("notifications/initialized", "notifications/cancelled"):
		return {}
	if method == "ping":
		return {}
	if method == "tools/list":
		return {"tools": mcp_tool_list(allowed_tools())}
	if method == "tools/call":
		return _tools_call(params, grant)
	raise ValueError(f"Unknown method: {method}")


def _tools_call(params: dict, grant) -> dict:
	name = params.get("name") or ""
	arguments = params.get("arguments") or {}
	spec = BY_NAME.get(name)
	if not spec:
		return {
			"content": [{"type": "text", "text": f"Unknown tool: {name}"}],
			"isError": True,
		}
	try:
		result = call_tool(spec, arguments, grant.property)
		text = frappe.as_json(result)
		return {
			"content": [{"type": "text", "text": text}],
			"structuredContent": json.loads(text) if text not in ("", "null") else result,
			"isError": False,
		}
	except Exception as exc:
		msg = str(exc)[:800]
		return {
			"content": [{"type": "text", "text": msg}],
			"isError": True,
		}


def _read_json(request):
	raw = request.get_data() or b""
	if not raw:
		return {}
	try:
		return json.loads(raw)
	except ValueError:
		return None


def _json(payload, status: int = 200) -> Response:
	body = "" if payload is None else json.dumps(payload)
	resp = Response(
		body,
		status=status if payload is not None else 202,
		content_type="application/json",
	)
	_apply_cors(resp)
	return resp


def _response(body: str, status: int) -> Response:
	resp = Response(body, status=status)
	_apply_cors(resp)
	return resp


def _rpc_error(rpc_id, code: int, message: str, http: int = 200) -> Response:
	return _json(_rpc_error_body(rpc_id, code, message), http)


def _rpc_error_body(rpc_id, code: int, message: str) -> dict:
	return {
		"jsonrpc": "2.0",
		"id": rpc_id,
		"error": {"code": code, "message": message},
	}


def _apply_cors(resp: Response) -> None:
	resp.headers["Cache-Control"] = "no-store"
	for key, value in CORS_HEADERS.items():
		resp.headers[key] = value
