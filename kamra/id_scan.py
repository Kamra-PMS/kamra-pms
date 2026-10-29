"""Read what an ID scanner sends: the two or three machine-readable lines
of a passport or ID card (MRZ, ICAO 9303), or whatever the country pack
knows how to read (India: the QR on an Aadhaar card).

The scanner is a plain USB or Bluetooth reader set to keyboard mode: it
types into the focused box like a keyboard, so no driver or local service
is needed. A phone or tablet camera that can read a QR sends the same text.

Nothing is stored here. The desk sees the fields filled in, checks them
against the guest, and saves through the usual check-in calls.
"""

from __future__ import annotations

import re
from datetime import date

import frappe
from frappe import _

from kamra.authz import require_roles

_WEIGHTS = (7, 3, 1)
# a scan is a few hundred characters; an Aadhaar secure QR a few thousand
MAX_LEN = 20000


def _cd_value(ch: str) -> int:
	if ch.isdigit():
		return int(ch)
	if "A" <= ch <= "Z":
		return ord(ch) - 55
	return 0  # "<" filler


def _check_digit(field: str) -> str:
	return str(sum(_cd_value(c) * _WEIGHTS[i % 3] for i, c in enumerate(field)) % 10)


def _ok(field: str, digit: str) -> bool:
	# "<" in the check position means the field is blank (an optional number)
	return digit == _check_digit(field) or (digit == "<" and not field.strip("<"))


def _date(yymmdd: str, future: bool) -> str | None:
	if not re.fullmatch(r"\d{6}", yymmdd):
		return None
	yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:])
	this = date.today().year % 100
	# expiry dates are this century; a birth year past this year is last century
	century = 2000 if future or yy <= this else 1900
	try:
		return date(century + yy, mm, dd).isoformat()
	except ValueError:
		return None


def _names(field: str) -> str:
	surname, _sep, given = field.partition("<<")
	clean = lambda s: " ".join(p for p in s.split("<") if p)  # noqa: E731
	return " ".join(p for p in (clean(given), clean(surname)) if p).title()


_SEX = {"M": "Male", "F": "Female", "X": "Other"}


def _mrz_lines(text: str) -> list[str] | None:
	lines = [re.sub(r"\s", "", ln).upper() for ln in re.split(r"[\r\n]+", text)]
	lines = [ln for ln in lines if ln]
	if len(lines) == 1:
		# some readers send the lines run together
		one = lines[0]
		for width, rows in ((44, 2), (36, 2), (30, 3)):
			if len(one) == width * rows:
				lines = [one[i * width:(i + 1) * width] for i in range(rows)]
				break
	shape = [len(ln) for ln in lines]
	if shape in ([44, 44], [36, 36], [30, 30, 30]) and all(
			re.fullmatch(r"[A-Z0-9<]+", ln) for ln in lines):
		return lines
	return None


def parse_mrz(text: str) -> dict | None:
	"""The fields of a passport (TD3), ID card (TD1) or TD2 document, with
	every check digit verified. None when the text is not an MRZ; throws
	when it is one but did not read cleanly."""
	lines = _mrz_lines(text)
	if not lines:
		return None
	if len(lines) == 3:  # TD1: number on line 1, dates on line 2, names on line 3
		l1, l2, l3 = lines
		code, number, n_cd = l1[0:2], l1[5:14], l1[14]
		dob, dob_cd, sex = l2[0:6], l2[6], l2[7]
		exp, exp_cd, nat = l2[8:14], l2[14], l2[15:18]
		name = l3
	else:  # TD3 passport (44) and TD2 (36) share line 2's layout
		l1, l2 = lines
		code, name = l1[0:2], l1[5:]
		number, n_cd, nat = l2[0:9], l2[9], l2[10:13]
		dob, dob_cd, sex = l2[13:19], l2[19], l2[20]
		exp, exp_cd = l2[21:27], l2[27]
	if not (_ok(number, n_cd) and _ok(dob, dob_cd) and _ok(exp, exp_cd)):
		frappe.throw(_("The ID didn't read cleanly. Scan it again."))
	return {
		"id_type": "Passport" if code.startswith("P") else "Other",
		"id_number": number.replace("<", ""),
		"full_name": _names(name),
		"date_of_birth": _date(dob, future=False),
		"gender": _SEX.get(sex),
		"nationality_code": nat.replace("<", ""),
		"id_expiry_date": _date(exp, future=True),
		"source": "mrz",
	}


def _age(dob: str | None) -> int | None:
	if not dob:
		return None
	d, today = date.fromisoformat(dob), date.today()
	return today.year - d.year - ((today.month, today.day) < (d.month, d.day))


def read(property: str, text: str) -> dict:
	text = (text or "").strip()
	if not text:
		frappe.throw(_("Nothing was scanned."))
	if len(text) > MAX_LEN:
		frappe.throw(_("That scan is too long to be an ID."))
	out = parse_mrz(text)
	if out is None:
		from kamra.localization import pack_for
		reader = getattr(pack_for(property), "read_id_scan", None)
		out = reader(text) if reader else None
	if out is None:
		frappe.throw(_("Kamra can't read this ID's code. Type the details in, "
		               "and take a picture of the ID."))
	from kamra.localization import pack_for
	pack = pack_for(property)
	code = out.pop("nationality_code", None)
	if code and not out.get("nationality"):
		# ponytail: home country by code, others keep the 3-letter code the
		# desk can edit; add an ISO 3166 table if foreign walk-ins complain
		home = getattr(pack, "HOME_COUNTRY_ISO3", None)
		out["nationality"] = getattr(pack, "DEFAULT_NATIONALITY", "") if code == home else code
	out["age"] = _age(out.get("date_of_birth"))
	return out


@frappe.whitelist(methods=["POST"])
@require_roles("Front Desk", "Kamra Agent")
def read_id_scan(property: str, text: str) -> dict:
	"""Turn what an ID scanner (or a camera reading a QR) sent into guest
	fields: name, ID type and number, date of birth, age, gender,
	nationality, expiry, and an address where the ID carries one. Read
	only: nothing is saved until the desk saves the guest."""
	return read(property, text)
