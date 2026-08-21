"""Kamra MCP server — stdio sidecar for air-gapped / localhost setups.

Prefer the hosted connector: in Kamra, open Kamra Agent → Connect Claude.
That talks to https://your-site/mcp over OAuth and needs no Python here.

This process is the fallback when Anthropic cannot reach the hotel (no
public HTTPS). Tools come from kamra.mcp_tools so they stay in lockstep
with the remote server.

Env:
    KAMRA_URL         e.g. http://kamra.localhost:8000
    KAMRA_API_KEY     personal or service API key
    KAMRA_API_SECRET  matching secret
    KAMRA_PROPERTY    property name
"""

from __future__ import annotations

import inspect
import json
import os
import sys

import requests
from mcp.server.fastmcp import FastMCP

# The registry lives in the Frappe app. When this file is launched from a
# bench (`apps/kamra/mcp/kamra_mcp.py`) the app package is on sys.path via
# the site env; when launched from this folder, add the parent package.
_APP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "kamra"))
if _APP not in sys.path:
	sys.path.insert(0, os.path.dirname(_APP))

from kamra.mcp_tools import (  # noqa: E402
	INSTRUCTIONS,
	TOOLS,
	_JSON_TYPES,
	prepare_arguments,
)

KAMRA_URL = os.environ.get("KAMRA_URL", "http://kamra.localhost:8000")
API_KEY = os.environ["KAMRA_API_KEY"]
API_SECRET = os.environ["KAMRA_API_SECRET"]
PROPERTY = os.environ.get("KAMRA_PROPERTY", "")

mcp = FastMCP("kamra", instructions=INSTRUCTIONS)


def call(dotted: str, **params):
	"""POST to any whitelisted Kamra endpoint, e.g. "api.get_quote"."""
	res = requests.post(
		f"{KAMRA_URL}/api/method/kamra.{dotted}",
		json=params,
		headers={"Authorization": f"token {API_KEY}:{API_SECRET}"},
		timeout=30,
	)
	if not res.ok:
		try:
			msgs = json.loads(res.json().get("_server_messages", "[]"))
			if msgs:
				raise RuntimeError(json.loads(msgs[0]).get("message", res.text))
		except (ValueError, KeyError):
			pass
		res.raise_for_status()
	return res.json()["message"]


def _bind(spec):
	params = []
	for pname, schema in spec.parameters.items():
		annotation = _JSON_TYPES.get(schema.get("type"), str)
		default = inspect.Parameter.empty if pname in spec.required else None
		params.append(
			inspect.Parameter(
				pname,
				inspect.Parameter.KEYWORD_ONLY,
				default=default,
				annotation=annotation,
			)
		)
	sig = inspect.Signature(params)

	def impl(**kwargs):
		property_name = PROPERTY or kwargs.get("property") or ""
		if not property_name:
			raise RuntimeError("KAMRA_PROPERTY is not set.")
		return call(spec.dotted, **prepare_arguments(spec, kwargs, property_name))

	impl.__name__ = spec.name
	impl.__doc__ = spec.description
	impl.__signature__ = sig
	return impl


for _spec in TOOLS:
	mcp.tool(name=_spec.name, description=_spec.description)(_bind(_spec))


if __name__ == "__main__":
	if not PROPERTY:
		sys.stderr.write("KAMRA_PROPERTY is required.\n")
		sys.exit(1)
	mcp.run()
