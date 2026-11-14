"""Extract the backend's user-visible strings for translation.

Frappe translates anything wrapped in `_()` / `frappe._()`, plus doctype and
field labels, from an app-level `translations/<lang>.csv`. This script walks
the Python source with `ast` (so multi-line and implicitly concatenated
strings are captured exactly) and the doctype JSON for labels, then writes
`backend-strings.csv` next to itself: one row per distinct source string.

Runtime-built messages (f-strings, `"a" + var`, `.format()` over a variable)
cannot be translated from a catalogue. They are reported separately on stdout
so they can be fixed by hand or accepted as-is.

Usage:
    python docs/i18n/extract_backend_strings.py            # write the CSV
    python docs/i18n/extract_backend_strings.py --list     # print every string
"""

from __future__ import annotations

import ast
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APP = ROOT / "kamra"
OUT = HERE / "backend-strings.csv"
ZH_CSV = APP / "translations" / "zh.csv"

# Code that never reaches a screen: tests, demo/eval scripts, patches.
SKIP_DIRS = {"tests", "scripts", "patches", "public"}


def py_files():
	for path in APP.rglob("*.py"):
		if SKIP_DIRS & set(path.relative_to(APP).parts):
			continue
		yield path


def doctype_label_files():
	for path in (APP / "kamra" / "doctype").rglob("*.json"):
		if path.name == "modules.txt":
			continue
		yield path


def is_translate_call(node: ast.AST) -> bool:
	if not isinstance(node, ast.Call):
		return False
	func = node.func
	return (isinstance(func, ast.Name) and func.id == "_") or (
		isinstance(func, ast.Attribute) and func.attr == "_"
	)


def literal(node: ast.AST) -> str | None:
	"""A single string literal, including implicitly concatenated parts."""
	if isinstance(node, ast.Constant) and isinstance(node.value, str):
		return node.value
	return None


def placeholders(text: str) -> str:
	import re

	return " ".join(sorted(set(re.findall(r"\{(\w+)\}", text))))


def existing_translations() -> dict[str, str]:
	if not ZH_CSV.exists():
		return {}
	with ZH_CSV.open(encoding="utf-8", newline="") as handle:
		return {row[0]: row[1] for row in csv.reader(handle) if len(row) >= 2}


def main() -> int:
	wanted = existing_translations()
	strings: dict[str, set[str]] = {}
	kinds: dict[str, set[str]] = {}
	dynamic: list[tuple[str, int, str]] = []

	for path in py_files():
		rel = path.relative_to(ROOT).as_posix()
		try:
			tree = ast.parse(path.read_text(encoding="utf-8"))
		except SyntaxError as err:  # a broken file is a finding of its own
			print(f"cannot parse {rel}: {err}", file=sys.stderr)
			continue
		for node in ast.walk(tree):
			if is_translate_call(node):
				text = literal(node.args[0]) if node.args else None
				if text is None:
					dynamic.append((rel, getattr(node, "lineno", 0), ast.unparse(node)))
					continue
				strings.setdefault(text, set()).add(rel)
				kinds.setdefault(text, set()).add("code")
			elif (
				isinstance(node, ast.Call)
				and isinstance(node.func, ast.Attribute)
				and node.func.attr == "throw"
				and node.args
			):
				# frappe.throw("...") with no _() would stay English forever.
				text = literal(node.args[0])
				if text and not is_translate_call(node.args[0]):
					dynamic.append((rel, getattr(node, "lineno", 0), f'frappe.throw({text!r})'))

	for path in doctype_label_files():
		rel = path.relative_to(ROOT).as_posix()
		try:
			doc = json.loads(path.read_text(encoding="utf-8"))
		except (json.JSONDecodeError, UnicodeDecodeError):
			continue
		if not isinstance(doc, dict):
			continue
		labels = []
		if doc.get("label"):
			labels.append(doc["label"])
		for field in doc.get("fields", []):
			if isinstance(field, dict) and field.get("label"):
				labels.append(field["label"])
		for label in labels:
			strings.setdefault(label, set()).add(rel)
			kinds.setdefault(label, set()).add("doctype")

	rows = sorted(strings.items(), key=lambda item: item[0].lower())
	with OUT.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.writer(handle)
		writer.writerow(["source", "kind", "placeholders", "sources", "status"])
		for text, sources in rows:
			writer.writerow(
				[
					text,
					"+".join(sorted(kinds[text])),
					placeholders(text),
					"; ".join(sorted(sources)),
					"translated" if text in wanted else "needs_translation",
				]
			)

	missing = [text for text, _ in rows if text not in wanted]
	print(f"{len(rows)} distinct backend strings -> {OUT.relative_to(ROOT)}")
	print(f"  code: {sum(1 for _, k in kinds.items() if 'code' in k)}"
	      f"  doctype labels: {sum(1 for _, k in kinds.items() if 'doctype' in k)}")
	print(f"  translated in zh.csv: {len(rows) - len(missing)}"
	      f"  missing: {len(missing)}")
	print(f"  runtime-built (cannot be translated from a catalogue): {len(dynamic)}")
	if "--list" in sys.argv:
		for text, _ in rows:
			if text in missing:
				print(text)
		for rel, line, snippet in dynamic:
			print(f"DYNAMIC {rel}:{line}  {snippet}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
