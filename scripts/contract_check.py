#!/usr/bin/env python3
"""Fail on a breaking change to Kamra's public contract (#580).

    python3 scripts/contract_check.py base.json head.json \
        [--deprecations contract-deprecations.json]

Breaking: a tool, method, scope or webhook event removed (a rename is a
removal plus an addition); a tool input or method parameter removed or its
type changed; a new required input or parameter; a removed response,
payload or envelope key; a scope that grants less. Additions pass.

A breaking change passes only when contract-deprecations.json lists it:

    {"deprecations": [{"item": "tool:old_name", "replacement": "new_name",
                       "remove_in": "2.10.0"}]}

`item` is the key printed for the change (an item also covers everything
under it: "tool:x" covers "tool:x:input:y"). `remove_in` must be at least
two minor releases after the head contract's version.
"""

from __future__ import annotations

import argparse
import json
import sys


def _ver(v: str) -> tuple[int, ...]:
	return tuple(int(p) for p in v.split(".")[:3])


def _keys(kind: str, name: str, old: list, new: list, what: str) -> list[tuple[str, str]]:
	return [(f"{kind}:{name}:{what}:{k}", f"{what} '{k}' removed")
	        for k in sorted(set(old) - set(new))]


def breaking_changes(base: dict, head: dict) -> list[tuple[str, str]]:
	out: list[tuple[str, str]] = []

	for name, old in base.get("tools", {}).items():
		new = head.get("tools", {}).get(name)
		if new is None:
			out.append((f"tool:{name}", "tool removed or renamed"))
			continue
		for k, typ in old["inputs"].items():
			if k not in new["inputs"]:
				out.append((f"tool:{name}:input:{k}", f"input '{k}' removed"))
			elif new["inputs"][k] != typ:
				out.append((f"tool:{name}:input:{k}",
				            f"input '{k}' type {typ} -> {new['inputs'][k]}"))
		for k in sorted(set(new["required"]) - set(old["required"])):
			out.append((f"tool:{name}:required:{k}", f"input '{k}' is now required"))

	for name, old in base.get("methods", {}).items():
		new = head.get("methods", {}).get(name)
		if new is None:
			out.append((f"method:{name}", "method removed or renamed"))
			continue
		for p, meta in old["params"].items():
			if p not in new["params"]:
				out.append((f"method:{name}:param:{p}", f"parameter '{p}' removed"))
			elif meta["default"] and not new["params"][p]["default"]:
				out.append((f"method:{name}:param:{p}", f"parameter '{p}' lost its default"))
		for p in sorted(set(new["params"]) - set(old["params"])):
			if not new["params"][p]["default"]:
				out.append((f"method:{name}:param:{p}", f"new required parameter '{p}'"))
		out += _keys("method", name, old["response_keys"], new["response_keys"], "response")

	for name, old in base.get("scopes", {}).items():
		new = head.get("scopes", {}).get(name)
		if new is None:
			out.append((f"scope:{name}", "scope removed or renamed"))
			continue
		out += _keys("scope", name, old["tools"], new["tools"], "tool")
		out += _keys("scope", name, old["rest"], new["rest"], "rest")

	bw, hw = base.get("webhooks", {}), head.get("webhooks", {})
	out += [(f"webhook:envelope:{k}", f"envelope key '{k}' removed")
	        for k in sorted(set(bw.get("envelope", ())) - set(hw.get("envelope", ())))]
	for name, old in bw.get("events", {}).items():
		new = hw.get("events", {}).get(name)
		if new is None:
			out.append((f"event:{name}", "webhook event removed or renamed"))
			continue
		out += _keys("event", name, old["payload_keys"], new["payload_keys"], "payload")
	return out


def additions(base: dict, head: dict) -> list[str]:
	out = []
	for section, label in (("tools", "tool"), ("methods", "method"), ("scopes", "scope")):
		out += [f"{label}:{k}" for k in sorted(set(head.get(section, {})) - set(base.get(section, {})))]
	out += [f"event:{k}" for k in sorted(set(head.get("webhooks", {}).get("events", {}))
	                                    - set(base.get("webhooks", {}).get("events", {})))]
	return out


def check(base: dict, head: dict, deprecations: list[dict]) -> tuple[bool, list[str]]:
	"""(ok, report lines)."""
	version = _ver(head["version"])
	min_remove = (version[0], version[1] + 2, 0)
	lines: list[str] = []
	ok = True
	for key, why in breaking_changes(base, head):
		dep = next((d for d in deprecations
		            if key == d.get("item") or key.startswith(f"{d.get('item')}:")), None)
		if dep is None:
			ok = False
			lines.append(f"  BREAKING  {key}: {why}")
			continue
		problems = []
		if not dep.get("replacement"):
			problems.append("no replacement")
		try:
			if _ver(dep.get("remove_in", "")) < min_remove:
				problems.append(f"remove_in {dep.get('remove_in')} is earlier than "
				                f"{min_remove[0]}.{min_remove[1]}.0")
		except ValueError:
			problems.append(f"remove_in {dep.get('remove_in')!r} is not a version")
		if problems:
			ok = False
			lines.append(f"  BREAKING  {key}: {why} (deprecation invalid: {'; '.join(problems)})")
		else:
			lines.append(f"  deprecated {key}: {why}; use {dep['replacement']}, "
			             f"removed in {dep['remove_in']}")
	lines += [f"  added     {a}" for a in additions(base, head)]
	return ok, lines


def main(argv: list[str] | None = None) -> int:
	ap = argparse.ArgumentParser(description="Compare two Kamra contract files.")
	ap.add_argument("base")
	ap.add_argument("head")
	ap.add_argument("--deprecations")
	args = ap.parse_args(argv)
	with open(args.base, encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal -- a path from the repo tree or the CI command line, not user input
		base = json.load(fh)
	with open(args.head, encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal -- a path from the repo tree or the CI command line, not user input
		head = json.load(fh)
	deps: list[dict] = []
	if args.deprecations:
		with open(args.deprecations, encoding="utf-8") as fh:  # nosemgrep: frappe-security-file-traversal -- a path from the repo tree or the CI command line, not user input
			deps = json.load(fh).get("deprecations", [])
	ok, lines = check(base, head, deps)
	print(f"Contract {base.get('version')} -> {head.get('version')}: "
	      + ("no breaking changes" if ok else "BREAKING CHANGES"))
	print("\n".join(lines) if lines else "  no contract changes")
	if not ok:
		print("\nKeep the old name working, or list it in contract-deprecations.json "
		      "with a replacement and remove_in (see docs-site/api-stability.md).")
	return 0 if ok else 1


if __name__ == "__main__":
	sys.exit(main())
