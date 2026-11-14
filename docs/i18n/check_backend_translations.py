"""Check kamra/translations/zh.csv against the extracted backend strings.

Fails when a catalogue row cannot work at runtime:

* a source the code asks for has no translation (the UI would fall back to
  English, which is exactly the "half translated" state we must avoid);
* a translation has different `{placeholders}` than its source, so
  `.format()` raises or prints the wrong value;
* a translation is empty or blank;
* the same source appears twice (Frappe takes the first match, so the second
  is dead weight and hides edits);
* a row exists for a string the code no longer asks for (orphan).

Usage:
    python docs/i18n/check_backend_translations.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STRINGS = HERE / "backend-strings.csv"
ZH_CSV = ROOT / "kamra" / "translations" / "zh.csv"

PLACEHOLDER = re.compile(r"\{[^{}]*\}")


def read_rows(path: Path) -> list[list[str]]:
	with path.open(encoding="utf-8", newline="") as handle:
		rows = [row for row in csv.reader(handle) if row]
	return rows[1:] if rows and rows[0][0] == "source" else rows


def main() -> int:
	if not STRINGS.exists() or not ZH_CSV.exists():
		print("run extract_backend_strings.py and build_zh_csv.py first", file=sys.stderr)
		return 2

	expected = {row[0] for row in read_rows(STRINGS)}
	rows = read_rows(ZH_CSV)

	problems: list[str] = []
	seen: set[str] = set()
	for number, row in enumerate(rows, 2):
		if len(row) < 2:
			problems.append(f"zh.csv:{number}: not a source,translation row")
			continue
		source, translation = row[0], row[1]
		if source in seen:
			problems.append(f"zh.csv:{number}: duplicate source {source!r}")
		seen.add(source)
		if not translation.strip():
			problems.append(f"zh.csv:{number}: empty translation for {source!r}")
			continue
		if source not in expected:
			problems.append(f"zh.csv:{number}: orphan source {source!r} (no longer in the code)")
		if sorted(PLACEHOLDER.findall(source)) != sorted(PLACEHOLDER.findall(translation)):
			problems.append(
				f"zh.csv:{number}: placeholder mismatch\n"
				f"    source      {source!r} -> {sorted(PLACEHOLDER.findall(source))}\n"
				f"    translation {translation!r} -> {sorted(PLACEHOLDER.findall(translation))}"
			)

	missing = sorted(expected - seen)
	for source in missing:
		problems.append(f"missing translation: {source!r}")

	if problems:
		print(f"{len(problems)} problem(s):")
		for problem in problems:
			print(f"  {problem}")
		return 1

	print(f"backend translations OK: {len(seen)}/{len(expected)} strings, "
	      f"placeholders match, no orphans or duplicates")
	return 0


if __name__ == "__main__":
	sys.exit(main())
