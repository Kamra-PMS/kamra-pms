"""Write kamra/translations/{es,ar}.csv for report pages and emails, from the
SPA's dictionaries, so a report reads the same in the app and in the inbox.

Run after changing a report dataset, column or pack label:
    python kamra/scripts/gen_report_translations.py
"""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "kamra" / "custom_reports.py").read_text()
# company statements and payment reminders (#238): labels, _tr() and _() text
STATEMENTS = (ROOT / "kamra" / "statements.py").read_text()
# every label/title literal in the report catalog, plus the page and email text
WORDS = sorted(set(re.findall(r'"(?:label|title)": "([^"]+)"', SRC))
               | set(re.findall(r'_col\("\w+", "([^"]+)"', SRC))
               | set(re.findall(r'\("[a-z0-9_]+", "([^"]+)"\)', STATEMENTS))
               | set(re.findall(r'\b_(?:tr)?\(["\']([^"\']+)["\']', STATEMENTS))
               | {"Report", "Kamra report", "The report is attached.",
                  "Metric", "This period", "Previous period", "Variance",
                  "Variance %", "vs previous period", "All companies"})
ROWS = "{0} rows"  # the SPA says "{n} rows"


def main():
	missing = []
	for lang in ("es", "ar"):
		ui = json.loads((ROOT / "frontend/src/i18n/locales" / f"{lang}.json").read_text())
		out = ROOT / "kamra" / "translations" / f"{lang}.csv"
		# keep rows other code added by hand (booking, privacy messages)
		rows = dict(csv.reader(out.open(encoding="utf-8"))) if out.exists() else {}
		for word in WORDS:
			if word in ui:
				rows[word] = ui[word]
			else:
				missing.append((lang, word))
		if "{n} rows" in ui:
			rows[ROWS] = ui["{n} rows"].replace("{n}", "{0}")
		else:
			missing.append((lang, "{n} rows"))
		with out.open("w", newline="", encoding="utf-8") as f:
			csv.writer(f).writerows(rows.items())
	for lang, word in missing:
		print(f"missing {lang}: {word}")


if __name__ == "__main__":
	main()
