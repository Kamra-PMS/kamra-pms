"""The UI language catalog and the on/off rules, with no Frappe dependency.

`frontend/src/i18n/languages.json` is the registry the React app imports.
Add a row there (and a `locales/<code>.json`) to ship a language. English
stays on. A language is on until its code is stored in the disabled list,
so a language added later is on without a migration.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "frontend" / "src" / "i18n" / "languages.json"
BASE = "en"
# ponytail: BCP47 primary + optional region (zh-CN); keep catalog casing
_CODE = re.compile(r"^[a-z]{2,8}(-[a-z0-9]{2,8})?$", re.I)


def _norm(code: str) -> str:
	return str(code).strip().lower()


def load_catalog(path: Path | None = None) -> list[dict]:
	"""Rows in picker order. Raises ValueError when the file is not a catalog."""
	raw = json.loads((path or CATALOG_PATH).read_text(encoding="utf-8"))
	if not isinstance(raw, list) or not raw:
		raise ValueError("UI language catalog must be a non-empty list")
	rows: list[dict] = []
	seen: set[str] = set()
	for item in raw:
		if not isinstance(item, dict):
			raise ValueError("UI language catalog row must be an object")
		code = str(item.get("code") or "").strip()
		native = str(item.get("nativeLabel") or "").strip()
		english = str(item.get("englishLabel") or "").strip()
		direction = item.get("dir")
		if not _CODE.match(code):
			raise ValueError(f"UI language code {code!r} is not a short language code")
		key = _norm(code)
		if key in seen:
			raise ValueError(f"UI language code {code} is listed twice")
		if not native or not english:
			raise ValueError(f"UI language {code} needs a native and an English name")
		if direction not in ("ltr", "rtl"):
			raise ValueError(f"UI language {code} direction must be ltr or rtl")
		seen.add(key)
		rows.append({
			"code": code,
			"nativeLabel": native,
			"englishLabel": english,
			"dir": direction,
		})
	if BASE not in seen:
		raise ValueError("UI language catalog must include English (en)")
	return rows


def catalog_codes(rows: list[dict] | None = None) -> list[str]:
	return [row["code"] for row in (rows if rows is not None else load_catalog())]


def _canonical(code: str, known: list[str]) -> str | None:
	key = _norm(code)
	for item in known:
		if _norm(item) == key:
			return item
	return None


def language_label(code: str, rows: list[dict] | None = None) -> str:
	"""The English name staff see in an error, or the code when it is unknown."""
	key = _norm(code)
	for row in rows if rows is not None else load_catalog():
		if _norm(row["code"]) == key:
			return row["englishLabel"]
	return code


def parse_stored_disabled(raw, known: list[str]) -> list[str]:
	"""Disabled codes already saved. Unknown codes, blanks and English are
	dropped, so a corrupt value or a removed language fails open."""
	if raw is None or raw == "":
		return []
	items = raw
	if isinstance(raw, str):
		try:
			items = json.loads(raw)
		except ValueError:
			return []
	if not isinstance(items, list):
		return []
	found: set[str] = set()
	for item in items:
		canon = _canonical(str(item), known)
		if canon and _norm(canon) != BASE:
			found.add(_norm(canon))
	return [code for code in known if _norm(code) in found]


class UnknownLanguage(ValueError):
	def __init__(self, code: str):
		self.code = code
		super().__init__(code)


def clean_requested_disabled(items, known: list[str]) -> list[str]:
	"""The disabled list an admin asked to save, in catalog order.

	English is ignored (it cannot be switched off). Any other code that
	is not in the catalog raises UnknownLanguage.
	"""
	if items is None:
		items = []
	if isinstance(items, str):
		text = items.strip()
		if not text:
			items = []
		else:
			try:
				items = json.loads(text)
			except ValueError:
				items = [part.strip() for part in text.split(",")]
	if not isinstance(items, (list, tuple)):
		raise UnknownLanguage("")
	found: set[str] = set()
	for item in items:
		raw = str(item).strip()
		if not raw or _norm(raw) == BASE:
			continue
		canon = _canonical(raw, known)
		if not canon:
			raise UnknownLanguage(raw)
		found.add(_norm(canon))
	return [code for code in known if _norm(code) in found]


def enabled_list(known: list[str], disabled: list[str]) -> list[str]:
	"""Catalog order, English always included. Codes absent from `disabled`
	stay on, which is how a newly registered language is on by default."""
	off = {_norm(code) for code in disabled}
	return [code for code in known if _norm(code) == BASE or _norm(code) not in off]


def resolve_language(saved: str | None, enabled: list[str] | set[str],
                     *fallbacks: str | None) -> str:
	"""`saved` when it is still enabled, else the first enabled fallback, else English."""
	offered = list(enabled)
	allow = {_norm(code) for code in offered}
	allow.add(BASE)
	for code in (saved, *fallbacks, BASE):
		if not code:
			continue
		key = _norm(code)
		if key not in allow:
			continue
		for item in offered:
			if _norm(item) == key:
				return item
		if key == BASE:
			return BASE
	return BASE
