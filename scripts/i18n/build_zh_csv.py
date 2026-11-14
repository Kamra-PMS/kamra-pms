"""Build kamra/translations/zh.csv from the extracted backend strings.

Frappe translates `_()` text and doctype labels from an app-level CSV:
`kamra/translations/<language>.csv`, one `source,translation` row each. That
file is the source of truth for the Chinese catalogue; this script only helps
maintain it.

`backend-strings.csv` (written by extract_backend_strings.py) lists the
strings the code asks for. Rows already in zh.csv are kept, a source the UI
dictionary already translates is copied over when its `{placeholders}` match
exactly, and whatever is still missing is written to
`backend-strings-todo.csv`. Both work files are regenerable and not committed.

Usage:
    python scripts/i18n/build_zh_csv.py
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


def main() -> int:
	if not STRINGS.exists():
		print(f"run extract_backend_strings.py first ({STRINGS} missing)", file=sys.stderr)
		return 2

	ui = json.loads(UI_DICT.read_text(encoding="utf-8"))
	existing = {row[0]: row[1] for row in read_csv(ZH_CSV) if len(row) >= 2 and row[1].strip()}
	translated: dict[str, str] = dict(existing)
	reused = 0

	sources = [row[0] for row in read_csv(STRINGS)]
	for source in sources:
		if source in translated:
			continue
		candidate = ui.get(source)
		if candidate and placeholders(candidate) == placeholders(source):
			translated[source] = candidate
			reused += 1

	# Drop rows for strings the code no longer asks for, so a renamed message
	# does not leave a stale entry that could later shadow the real one.
	translated = {source: text for source, text in translated.items() if source in set(sources)}

	ZH_CSV.parent.mkdir(parents=True, exist_ok=True)
	with ZH_CSV.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.writer(handle, lineterminator="\n")
		for source in sorted(translated):
			writer.writerow([source, translated[source]])

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
