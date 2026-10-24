"""MCP now needs the MCP Read or MCP Manage role. Before, every staff member
could connect Claude. So nobody connected today loses access, everyone who
has a live MCP connection, or whose API key has made MCP calls, gets MCP
Manage: the same reach they had. Admins are exempt and are skipped.

Idempotent: users who already hold an MCP role are left alone."""

import frappe

from kamra.authz import ADMIN
from kamra.mcp_access import MCP_MANAGE, MCP_ROLES, ensure_roles


def execute():
	ensure_roles()
	users: set[str] = set()
	if frappe.db.table_exists("MCP OAuth Grant"):
		users.update(frappe.get_all("MCP OAuth Grant", filters={"revoked": 0},
		                            pluck="user", distinct=True))
	if frappe.db.table_exists("Agent Action Log"):
		# an API key client logs its writes under its own user on the MCP channel
		users.update(frappe.get_all("Agent Action Log",
		                            filters={"action_channel": "MCP"},
		                            pluck="actor", distinct=True))
	for user in sorted(u for u in users if u and u not in ("Administrator", "Guest")):
		if not frappe.db.exists("User", user):
			continue
		roles = set(frappe.get_roles(user))
		if roles & set(ADMIN) or roles & set(MCP_ROLES):
			continue
		doc = frappe.get_doc("User", user)
		doc.append("roles", {"role": MCP_MANAGE})
		doc.flags.ignore_permissions = True
		doc.save()
