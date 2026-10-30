"""The QR on an Aadhaar card or e-Aadhaar print, as a scanner types it.

Two kinds are in circulation:
- the old QR (cards before 2018): plain XML, <PrintLetterBarcodeData uid=...>
- the secure QR (UIDAI, 2018 on): one long decimal number. As bytes it is
  gzip; inside, fields split by byte 255, then a photo and a signature.

Only the last 4 digits of the Aadhaar number are kept, the same masking
Kamra Verify uses: a hotel has no reason to hold the full number. The
secure QR itself only carries those 4 digits.

ponytail: the UIDAI signature is not checked, so the desk still compares
the card with the guest. Add the check (UIDAI public certificate) if a
property needs proof the card is genuine.
"""

from __future__ import annotations

import re
import zlib
from datetime import date

_GENDER = {"M": "Male", "F": "Female", "T": "Other"}
# secure QR fields after the optional version marker (V2, V3...)
_SECURE = ("email_mobile", "reference_id", "name", "dob", "gender", "care_of",
           "district", "landmark", "house", "location", "pincode",
           "post_office", "state", "street", "sub_district", "vtc")
MAX_INFLATED = 64 * 1024
_ADDRESS = ("house", "street", "landmark", "location", "vtc", "post_office",
            "sub_district", "district", "state", "pincode")


def mask(value: str | None) -> str:
	"""Aadhaar is never held whole: its last 4 digits in the register mask,
	'••••••••1012'. Takes a full number, a masked one or just the last 4."""
	digits = re.sub(r"\D", "", value or "")
	return "•" * 8 + digits[-4:] if digits else ""


_masked = mask


def _dob(value: str) -> str | None:
	value = (value or "").strip()
	for pat, order in ((r"(\d{2})[-/](\d{2})[-/](\d{4})", "dmy"),
	                   (r"(\d{4})[-/](\d{2})[-/](\d{2})", "ymd")):
		m = re.fullmatch(pat, value)
		if m:
			a, b, c = (int(x) for x in m.groups())
			y, mo, d = (c, b, a) if order == "dmy" else (a, b, c)
			try:
				return date(y, mo, d).isoformat()
			except ValueError:
				return None
	return None


def _address(parts: dict) -> str:
	seen, out = set(), []
	for k in _ADDRESS:
		v = (parts.get(k) or "").strip()
		if v and v.casefold() not in seen:
			seen.add(v.casefold())
			out.append(v)
	return ", ".join(out)


def _old_qr(text: str) -> dict:
	# attributes by regex, not an XML parser: the input is untrusted and
	# all we want is a handful of attribute values
	attrs = dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', text))
	dob = _dob(attrs.get("dob", ""))
	return {
		"id_type": "Aadhaar",
		"id_number": _masked(re.sub(r"\D", "", attrs.get("uid", ""))[-4:]),
		"full_name": attrs.get("name", "").strip(),
		"date_of_birth": dob,
		"year_of_birth": None if dob else (attrs.get("yob") or None),
		"gender": _GENDER.get(attrs.get("gender", "").strip()[:1].upper()),
		"address": _address({**attrs, "post_office": attrs.get("po"),
		                     "sub_district": attrs.get("subdist"),
		                     "pincode": attrs.get("pc"),
		                     "location": attrs.get("loc")}),
		"city": attrs.get("vtc") or attrs.get("dist") or "",
		"nationality": "Indian",
		"source": "aadhaar_qr",
	}


def _secure_qr(text: str) -> dict | None:
	# a real secure QR runs to 5,000-6,500 digits, past Python's 4,300-digit
	# int() limit: build the number in chunks instead
	n = 0
	for i in range(0, len(text), 1000):
		chunk = text[i:i + 1000]
		n = n * 10 ** len(chunk) + int(chunk)
	raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
	try:
		# capped: the card's text and photo are a few KB, never megabytes
		inflate = zlib.decompressobj(16 + zlib.MAX_WBITS)
		data = inflate.decompress(raw, MAX_INFLATED)
	except zlib.error:
		return None
	if inflate.unconsumed_tail:
		return None
	fields = data.split(b"\xff")
	if fields and fields[0][:1] == b"V":  # V2 and later lead with a version
		fields = fields[1:]
	if len(fields) < len(_SECURE):
		return None
	parts = {k: fields[i].decode("iso-8859-1").strip() for i, k in enumerate(_SECURE)}
	return {
		"id_type": "Aadhaar",
		"id_number": _masked(parts["reference_id"][:4]),
		"full_name": parts["name"],
		"date_of_birth": _dob(parts["dob"]),
		"gender": _GENDER.get(parts["gender"][:1].upper()),
		"address": _address(parts),
		"city": parts["vtc"] or parts["district"],
		"nationality": "Indian",
		"source": "aadhaar_qr",
	}


def read(text: str) -> dict | None:
	text = text.strip()
	if "PrintLetterBarcodeData" in text:
		return _old_qr(text)
	if re.fullmatch(r"\d{200,}", text):
		return _secure_qr(text)
	return None
