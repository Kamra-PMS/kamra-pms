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


def main() -> None:
	groups: dict[str, list] = defaultdict(list)
	for spec in TOOLS:
		groups[spec.group].append(spec)

	lines = [
		"# MCP tool reference",
		"",
		f"Kamra exposes **{TOOL_COUNT} governed tools** on the hosted MCP",
		"endpoint (`/mcp`) and the stdio sidecar (`mcp/kamra_mcp.py`). Every",
		"call runs as the connected user — role permissions apply, prices come",
		"from the pricing engine, and each action is recorded in the activity",
		"ledger.",
		"",
		"This page is generated from `kamra/mcp_tools.py`. Re-run",
		"`python3 gen_mcp_tools.py` in `docs-site/` when the registry changes.",
		"",
	]
	order = [
		"Front desk",
		"Ops",
		"Billing",
		"Revenue",
		"Briefings",
		"Night audit",
		"Groups",
		"Onboarding",
		"Banquets",
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
			lines.append(spec.description)
			lines.append("")
			lines.append(f"Endpoint: `kamra.{spec.dotted}`.")
			if spec.mutating:
				lines.append("Mutating — logged to the activity ledger.")
			lines.append("")
	text = "\n".join(lines).rstrip() + "\n"
	with open(OUT, "w", encoding="utf-8") as f:
		f.write(text)
	print(f"wrote {OUT} ({TOOL_COUNT} tools)")


if __name__ == "__main__":
	main()
