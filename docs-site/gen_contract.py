#!/usr/bin/env python3
"""Generate the public contract (docs-site/public/contract.json).

The contract is what connected apps and AI clients rely on: MCP tools,
public REST methods, service account scopes and webhook events. CI compares
a PR's contract with the base branch's (scripts/contract_check.py).

No site needed: the MCP registry imports without Frappe (as in
gen_mcp_tools.py), everything else is read from the source with `ast`.

    python3 docs-site/gen_contract.py [--root REPO] [--out FILE]
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _module_tree(root: str, module: str) -> ast.Module | None:
	base = os.path.join(root, "kamra", *module.split("."))
	for path in (base + ".py", os.path.join(base, "__init__.py")):
		if os.path.exists(path):
			with open(path, encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal -- a path from the repo tree or the CI command line, not user input
				return ast.parse(fh.read(), path)
	return None


def _literal(root: str, module: str, name: str):
	"""A top-level `NAME = <literal>` from a module, or None."""
	tree = _module_tree(root, module)
	for node in tree.body if tree else ():
		target = node.target if isinstance(node, ast.AnnAssign) else (
			node.targets[0] if isinstance(node, ast.Assign) else None)
		if isinstance(target, ast.Name) and target.id == name:
			return ast.literal_eval(node.value)
	return None


def _signature(root: str, dotted: str, trees: dict) -> dict | None:
	module, func = dotted.rsplit(".", 1)
	if module not in trees:
		trees[module] = _module_tree(root, module)
	tree = trees[module]
	for node in tree.body if tree else ():
		if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == func:
			a = node.args
			pos = a.posonlyargs + a.args
			defaults = len(pos) - len(a.defaults)
			params = {p.arg: {"default": i >= defaults} for i, p in enumerate(pos)}
			for p, dflt in zip(a.kwonlyargs, a.kw_defaults, strict=True):
				params[p.arg] = {"default": dflt is not None}
			return {"params": dict(sorted(params.items()))}
	return None


def _version(root: str) -> str:
	with open(os.path.join(root, "kamra", "__init__.py"), encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal -- a path from the repo tree or the CI command line, not user input
		return re.search(r'__version__\s*=\s*"([^"]+)"', fh.read()).group(1)


def build(root: str, keep: tuple[str, ...] = ()) -> dict:
	"""`keep`: methods already in a published contract (CI passes the base
	branch's). They stay in while the function exists, so moving a tool to a
	new endpoint does not quietly drop the old one from the contract."""
	root = os.path.abspath(root)
	sys.path.insert(0, root)
	from kamra import mcp_tools as m

	try:
		from kamra import contract_keys as ck
	except ImportError:  # a base branch from before the contract existed
		ck = None
	response_keys = getattr(ck, "RESPONSE_KEYS", {})
	payload_keys = getattr(ck, "WEBHOOK_PAYLOAD_KEYS", {})

	tools = {}
	for spec in m.TOOLS:
		hints = m.annotations(spec)
		tools[spec.name] = {
			"target": f"kamra.{spec.dotted}",
			"inputs": {k: v.get("type") for k, v in sorted(spec.parameters.items())},
			"required": sorted(spec.required),
			"mutating": spec.mutating,
			**{h: hints[h] for h in ("readOnlyHint", "destructiveHint", "idempotentHint")},
		}

	scopes = _literal(root, "service_accounts", "SCOPES") or {}
	scopes = {k: {"tools": sorted(v.get("tools", ())), "rest": sorted(v.get("rest", ()))}
	          for k, v in sorted(scopes.items())}

	dotted = {s.dotted for s in m.TOOLS} | set(response_keys)
	dotted |= {r for s in scopes.values() for r in s["rest"]}
	trees: dict = {}
	methods = {}
	for d in sorted(dotted | {k.removeprefix("kamra.") for k in keep}):
		sig = _signature(root, d, trees)
		if sig is None:
			if d in dotted:  # a tool, scope or key table names a missing function
				raise SystemExit(f"contract: kamra.{d} not found in kamra/")
			continue  # gone since the base contract: the check reports it
		methods[f"kamra.{d}"] = {**sig, "response_keys": sorted(response_keys.get(d, ()))}

	events = _literal(root, "webhooks", "EVENTS") or {}
	stale = set(payload_keys) - set(events)
	if stale:
		raise SystemExit(f"contract: contract_keys lists unknown webhook events {sorted(stale)}")

	return {
		"version": _version(root),
		"tools": tools,
		"methods": methods,
		"scopes": scopes,
		"webhooks": {
			"envelope": sorted(getattr(ck, "WEBHOOK_ENVELOPE_KEYS", ())),
			"events": {e: {"payload_keys": sorted(payload_keys.get(e, ()))}
			           for e in sorted(events)},
		},
	}


def main() -> None:
	ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
	ap.add_argument("--root", default=os.path.join(HERE, ".."))
	ap.add_argument("--out", default=os.path.join(HERE, "public", "contract.json"))
	ap.add_argument("--keep", help="a base contract.json whose methods stay tracked")
	args = ap.parse_args()
	keep: tuple[str, ...] = ()
	if args.keep:
		with open(args.keep, encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal -- a path from the repo tree or the CI command line, not user input
			keep = tuple(json.load(fh).get("methods", {}))
	contract = build(args.root, keep)
	with open(args.out, "w", encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal -- a path from the repo tree or the CI command line, not user input
		json.dump(contract, fh, indent=1, sort_keys=True)
		fh.write("\n")
	print(f"Wrote {args.out}: {len(contract['tools'])} tools, "
	      f"{len(contract['methods'])} methods, {len(contract['scopes'])} scopes, "
	      f"{len(contract['webhooks']['events'])} webhook events")


if __name__ == "__main__":
	main()
