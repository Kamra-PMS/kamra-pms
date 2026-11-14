"""Build kamra/translations/zh.csv from the extracted backend strings.

Frappe translates `_()` text and doctype labels from an app-level CSV:
`kamra/translations/<language>.csv`, one `source,translation` row each. The
UI dictionary (`frontend/src/i18n/locales/zh-CN.json`) already holds a
reviewed translation for every English string the frontend uses, so any
backend source that appears there too is copied over verbatim - provided the
`{placeholders}` match exactly, which is what makes the copy safe.

Rows already present in zh.csv are kept (so hand edits survive a rerun), and
what is still missing is written to `backend-strings-todo.csv` for translation.

Usage:
    python docs/i18n/build_zh_csv.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STRINGS = HERE / "backend-strings.csv"
TODO = HERE / "backend-strings-todo.csv"
BATCHES = HERE / "batches"
UI_DICT = ROOT / "frontend" / "src" / "i18n" / "locales" / "zh-CN.json"
ZH_CSV = ROOT / "kamra" / "translations" / "zh.csv"


def placeholders(text: str) -> set[str]:
	return set(re.findall(r"\{(\w+)\}", text))


def read_csv(path: Path) -> list[list[str]]:
	if not path.exists():
		return []
	with path.open(encoding="utf-8", newline="") as handle:
		rows = [row for row in csv.reader(handle) if row]
	return rows[1:] if rows and rows[0][0] == "source" else rows


def read_batches() -> dict[str, str]:
	"""Translations produced in review passes: docs/i18n/batches/*.tsv.

	Tab-separated `source<TAB>translation`, one row each. TSV because the
	sources are sentences full of commas and quotes; a source containing a
	tab would be ambiguous, so the column count is checked.
	"""
	out: dict[str, str] = {}
	if not BATCHES.exists():
		return out
	for path in sorted(BATCHES.glob("*.tsv")):
		for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
			if not line.strip():
				continue
			parts = line.split("\t")
			if len(parts) != 2:
				raise SystemExit(f"{path.name}:{number}: expected source<TAB>translation")
			source, translation = parts
			if translation.strip():
				out[source] = translation.strip()
	return out


def main() -> int:
	if not STRINGS.exists():
		print(f"run extract_backend_strings.py first ({STRINGS} missing)", file=sys.stderr)
		return 2

	ui = json.loads(UI_DICT.read_text(encoding="utf-8"))
	batches = read_batches()
	existing = {row[0]: row[1] for row in read_csv(ZH_CSV) if len(row) >= 2 and row[1].strip()}
	translated: dict[str, str] = dict(existing)
	reused = 0

	for row in read_csv(STRINGS):
		source = row[0]
		if source in translated or source in batches:
			continue
		candidate = ui.get(source)
		if candidate and placeholders(candidate) == placeholders(source):
			translated[source] = candidate
			reused += 1

	# Reviewed batches win over both the reused UI strings and earlier runs.
	translated.update(batches)
	# Drop rows for strings the code no longer asks for, so a renamed message
	# does not leave a stale entry that could later shadow the real one.
	sources = [row[0] for row in read_csv(STRINGS)]
	translated = {source: text for source, text in translated.items() if source in set(sources)}

	ZH_CSV.parent.mkdir(parents=True, exist_ok=True)
	with ZH_CSV.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.writer(handle, lineterminator="\n")
		for source in sorted(translated):
			writer.writerow([source, translated[source]])

	sources = [row[0] for row in read_csv(STRINGS)]
	missing = [source for source in sources if source not in translated]
	with TODO.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.writer(handle, lineterminator="\n")
		writer.writerow(["source", "translation"])
		for source in missing:
			writer.writerow([source, ""])

	print(f"{len(sources)} backend strings, {len(sources) - len(missing)} translated "
	      f"({reused} reused from the UI dictionary, {len(existing)} already in zh.csv)")
	print(f"  still to translate: {len(missing)} -> {TODO.relative_to(ROOT)}")
	print(f"  wrote {len(translated)} rows -> {ZH_CSV.relative_to(ROOT)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
