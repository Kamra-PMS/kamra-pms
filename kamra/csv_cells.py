"""Cells of a CSV file that people open in a spreadsheet.

Guest names, table names and reasons are typed by people, and a spreadsheet
runs a cell that starts like a formula. Same rule as the screens' own
exports (frontend/src/lib/csv.ts).
"""

from __future__ import annotations

import re

# =, +, -, @ and their full-width forms after any blank space, or a cell that
# starts with a tab or a line break
_RUNS = re.compile("^(?:[\\s﻿]*[=+\\-@＝＋－＠]|[\t\r\n])")
_NUMBER = re.compile(r"-?[0-9]+(\.[0-9]+)?")


def safe_cell(value):
	"""`value` as it should be written: text that would run gets a leading
	quote. Numbers, negative ones included, stay as they are."""
	if isinstance(value, str) and _RUNS.match(value) and not _NUMBER.fullmatch(value.strip()):
		return f"'{value}"
	return value
