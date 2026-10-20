#!/usr/bin/env python3
"""Generate docs-site/mcp-tools.md from kamra.mcp_tools.

Run from docs-site/:  python3 gen_mcp_tools.py
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from kamra.mcp_tools import TOOL_COUNT, TOOLS  # noqa: E402

OUT = os.path.join(HERE, "mcp-tools.md")


def _ascii_dashes(text: str) -> str:
	"""Docs CI rejects Unicode em/en dashes in published markdown."""
	return (
		text.replace("\u2014", " - ")
		.replace("\u2013", "-")
		.replace(" — ", " - ")
		.replace("—", " - ")
		.replace(" – ", " - ")
		.replace("–", "-")
	)


def main() -> None:
	groups: dict[str, list] = defaultdict(list)
	for spec in TOOLS:
		groups[spec.group].append(spec)

	lines = [
		"# MCP tool reference",
		"",
		f"Kamra exposes **{TOOL_COUNT} governed tools** on the hosted MCP",
		"endpoint (`/mcp`) and the stdio sidecar (`mcp/kamra_mcp.py`). Every",
		"call runs as the connected user - **role** permissions apply, tools",
		"are further filtered by the property's **enabled modules**, prices",
		"come from the pricing engine, and each action is recorded in the",
		"activity ledger.",
		"",
		"This page is generated from `kamra/mcp_tools.py`. Re-run",
		"`python3 gen_mcp_tools.py` in `docs-site/` when the registry changes.",
		"",
	]
	order = [
		"Front desk",
		"Ops",
		"Housekeeping",
		"Billing",
		"Revenue",
		"Briefings",
		"Night audit",
		"Groups",
		"Banquets",
		"F&B",
		"Laundry",
		"Onboarding",
		"Channels",
	]
	for group in order:
		specs = groups.get(group) or []
		if not specs:
			continue
		lines.append(f"## {group}")
		lines.append("")
		for spec in specs:
			args = ", ".join(spec.parameters)
			sig = f"`{spec.name}({args})`" if args else f"`{spec.name}()`"
			lines.append(f"### {sig}")
			lines.append("")
			lines.append(_ascii_dashes(spec.description))
			lines.append("")
			lines.append(f"Endpoint: `kamra.{spec.dotted}`.")
			if spec.mutating:
				lines.append("Mutating - logged to the activity ledger.")
			lines.append("")
	text = _ascii_dashes("\n".join(lines).rstrip() + "\n")
	with open(OUT, "w", encoding="utf-8") as f:  # nosemgrep: frappe-security-file-traversal -- OUT is a fixed path in the docs folder; docs build script, not a request handler
		f.write(text)
	print(f"wrote {OUT} ({TOOL_COUNT} tools)")


if __name__ == "__main__":
	main()
