# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Pure helpers for Kamra Enterprise.

No Frappe, no network. The whitelisted module and the adapters call these
so the forecast, the price band, the journal and the message parsers can
be tested without a site.
"""

from __future__ import annotations

import json
from datetime import date as date_cls
from decimal import Decimal, ROUND_HALF_UP

# Predicted occupancy maps onto a premium. Negative means a soft house.
# The pricing engine still clamps the result to the owner's guardrails.
OPEN_BANDS = (
	(0, 40, -8),
	(40, 70, 0),
	(70, 85, 10),
	(85, 93, 18),
	(93, 101, 25),
)

ROOM_HEADS = {"Room", "Meal Plan", "Extra Guests", "Room Levy"}
MONEY = Decimal("0.01")


def remaining_demand_share(lead_days: int) -> float:
	"""Share of the still-unsold typical demand that usually lands before arrival.

	Short lead times have little left to pick up. Far-out dates still have
	most of their booking curve ahead of them. The curve is a fixed table,
	not a fitted model, so a property can read why a date moved.
	"""
	lead = max(0, int(lead_days))
	if lead <= 1:
		return 0.08
	if lead <= 3:
		return 0.18
	if lead <= 7:
		return 0.35
	if lead <= 14:
		return 0.55
	if lead <= 30:
		return 0.70
	return 0.80


def predict_occupancy_pct(
	on_books_pct: float,
	sellable: int,
	pickup_last_7: float,
	pickup_prior_7: float,
	weekday_final_pct: float | None,
	lead_days: int,
) -> float:
	"""Pace-adjusted occupancy for one future date, as a percent.

	Never below what is already on the books. Caps at 100. With no history,
	a 70% house is the stand-in final occupancy.
	"""
	on_books = max(0.0, min(100.0, float(on_books_pct or 0)))
	rooms = int(sellable or 0)
	if rooms <= 0:
		return round(on_books, 1)
	pace = (float(pickup_last_7 or 0) + 1.0) / (float(pickup_prior_7 or 0) + 1.0)
	pace = min(max(pace, 0.25), 2.0)
	if weekday_final_pct is None:
		typical_left = max(0.0, 70.0 - on_books)
	else:
		typical_left = max(0.0, float(weekday_final_pct) - on_books)
	expected = typical_left * remaining_demand_share(lead_days) * pace
	daily = float(pickup_last_7 or 0) / 7.0
	pace_pct = min(daily * min(max(lead_days, 0), 14), rooms * 0.5) / rooms * 100.0
	predicted = on_books + max(expected, pace_pct * 0.5)
	return round(min(100.0, max(on_books, predicted)), 1)


def premium_for_occupancy(occupancy_pct: float) -> int:
	"""Open-band premium when the property has no hurdle tier for this occupancy."""
	occ = float(occupancy_pct or 0)
	for low, high, premium in OPEN_BANDS:
		if low <= occ < high:
			return int(premium)
	return 0


def clamp_rate(rate: Decimal, floor: Decimal, ceiling: Decimal) -> Decimal:
	"""Keep a computed rate inside the owner's floor and ceiling.

	A zero floor or ceiling means that side is unset.
	"""
	out = rate
	if floor and out < floor:
		out = floor
	if ceiling and out > ceiling:
		out = ceiling
	return out


def apply_open_band(
	rate: Decimal, occupancy_pct: float, floor: Decimal, ceiling: Decimal,
) -> tuple[Decimal, float]:
	"""Apply the open band, then the guardrail. Returns (rate, effective %).

	Effective percent is what the guest actually pays versus the season rate
	after the floor and ceiling, so the quote does not advertise a premium
	the guardrail removed.
	"""
	premium = premium_for_occupancy(occupancy_pct)
	if not premium or rate <= 0:
		return rate, 0.0
	adjusted = (rate * (Decimal(1) + Decimal(premium) / Decimal(100))).quantize(
		MONEY, rounding=ROUND_HALF_UP)
	adjusted = clamp_rate(adjusted, floor or Decimal(0), ceiling or Decimal(0))
	effective = float(((adjusted - rate) / rate * Decimal(100)).quantize(
		MONEY, rounding=ROUND_HALF_UP))
	return adjusted, effective


def weekday_samples(series: list[tuple[str, float]], day: str, limit: int = 8) -> list[float]:
	"""Up to `limit` earlier values that fell on the same weekday as `day`."""
	target = date_cls.fromisoformat(str(day)[:10]).weekday()
	prior = []
	for raw, value in series:
		stamp = str(raw)[:10]
		if stamp >= str(day)[:10]:
			continue
		if date_cls.fromisoformat(stamp).weekday() == target:
			prior.append((stamp, float(value)))
	prior.sort()
	return [value for _, value in prior[-limit:]]


def deviation(
	value: float, history: list[float], z_threshold: float = 2.0, min_pct: float = 20.0,
) -> dict | None:
	"""A sample-standard-deviation alert, or None when the history is too thin
	or the move is inside the band. Needs four earlier points."""
	hist = [float(x) for x in history]
	if len(hist) < 4:
		return None
	mean = sum(hist) / len(hist)
	var = sum((x - mean) ** 2 for x in hist) / (len(hist) - 1)
	std = var ** 0.5
	actual = float(value)
	if std < 1e-9:
		if actual == mean:
			return None
		z = 9.0 if actual > mean else -9.0
	else:
		z = (actual - mean) / std
	if mean:
		pct = abs(actual - mean) / abs(mean) * 100.0
	else:
		pct = 100.0 if actual else 0.0
	if abs(z) < float(z_threshold) or pct < float(min_pct):
		return None
	return {
		"z": round(z, 2),
		"mean": round(mean, 2),
		"pct": round(pct, 1),
		"actual": round(actual, 2),
		"direction": "above" if actual >= mean else "below",
	}


def peak_and_low(days: list[dict]) -> dict:
	"""The highest and lowest predicted days. `days` items need date and predicted."""
	if not days:
		return {"peak": None, "low": None}
	return {
		"peak": max(days, key=lambda row: float(row["predicted"])),
		"low": min(days, key=lambda row: float(row["predicted"])),
	}


def staffing_hint(arrivals: int, departures: int, stayovers: int) -> dict:
	"""A planning hint: about 14 cleans per attendant. Not a roster."""
	cleans = max(0, int(departures)) + max(0, int(stayovers))
	attendants = 0 if cleans == 0 else max(1, int(round(cleans / 14.0)))
	return {
		"cleans": cleans,
		"attendants": attendants,
		"arrivals": max(0, int(arrivals)),
		"departures": max(0, int(departures)),
		"stayovers": max(0, int(stayovers)),
	}


def minutes_from_eta(eta: str | None, default: int = 14 * 60) -> int:
	"""Turn '14:30' or '9.15' into minutes after midnight. 'late' means 22:00."""
	text = (eta or "").strip().lower()
	if not text:
		return default
	if "late" in text:
		return 22 * 60
	digits = []
	current = ""
	for ch in text:
		if ch.isdigit():
			current += ch
		elif current:
			digits.append(current)
			current = ""
			if len(digits) == 2:
				break
	if current:
		digits.append(current)
	if not digits:
		return default
	hour = int(digits[0])
	minute = int(digits[1]) if len(digits) > 1 else 0
	if hour > 23 or minute > 59:
		return default
	return hour * 60 + minute


def arrival_sort_key(same_day: bool, vip: bool, arrival_minutes: int | None, room: str) -> tuple:
	"""VIP same-day arrivals first, then earliest ETA, then everyone else."""
	if not same_day:
		return (1, 1, 24 * 60, room or "")
	return (0, 0 if vip else 1,
	        arrival_minutes if arrival_minutes is not None else 24 * 60,
	        room or "")


def priority_for_arrival(same_day: bool, vip: bool, arrival_minutes: int | None) -> str:
	"""Housekeeping priority for a departure clean that has an arrival behind it."""
	if not same_day:
		return "Medium"
	if vip or (arrival_minutes is not None and arrival_minutes <= 12 * 60):
		return "Urgent"
	return "High"


def facilities_from_amenities(amenities: list[str]) -> list[dict]:
	"""'Pool: heated' groups under Pool. A bare amenity sits under Resort."""
	groups: dict[str, list[str]] = {}
	for raw in amenities or []:
		text = (raw or "").strip()
		if not text:
			continue
		if ":" in text:
			area, _, detail = text.partition(":")
			area = area.strip() or "Resort"
			detail = detail.strip()
			if detail:
				groups.setdefault(area, []).append(detail)
		else:
			groups.setdefault("Resort", []).append(text)
	return [{"area": area, "items": items} for area, items in groups.items() if items]


def valid_score(score) -> int | None:
	try:
		number = int(score)
	except (TypeError, ValueError):
		return None
	if 1 <= number <= 5:
		return number
	return None


def recommend_for_guest(profile: dict) -> list[dict]:
	"""Rule-based offers from stay history and the profile the desk stored.

	`profile` keys: vip, dietary_notes, special_occasions, preferred_view,
	preferred_room_type, notes, current_room_type, room_types
	[{name, room_type_name, base_price}], stays [{room_type, nights}],
	charges [{charge_type}].
	"""
	out: list[dict] = []
	notes = " ".join(filter(None, [
		profile.get("dietary_notes") or "",
		profile.get("notes") or "",
	])).strip()
	dietary = (profile.get("dietary_notes") or "").strip()
	if dietary or any(word in notes.lower() for word in ("allerg", "vegan", "halal", "vegetarian")):
		out.append({
			"code": "dietary",
			"title": "Tell the kitchen before arrival",
			"detail": dietary or notes[:240],
		})
	occasion = (profile.get("special_occasions") or "").strip()
	if occasion:
		out.append({
			"code": "occasion",
			"title": "Mark a special occasion",
			"detail": occasion[:240],
		})
	if profile.get("vip"):
		out.append({
			"code": "vip_welcome",
			"title": "VIP welcome before arrival",
			"detail": "Send the welcome note and prepare the arrival amenity.",
		})
	view = (profile.get("preferred_view") or "").strip()
	if view:
		out.append({
			"code": "view",
			"title": "Keep the preferred view",
			"detail": view[:120],
		})
	types = list(profile.get("room_types") or [])
	types.sort(key=lambda row: float(row.get("base_price") or 0))
	by_name = {row.get("name"): row for row in types}
	by_label = {row.get("room_type_name"): row for row in types}
	current_name = profile.get("current_room_type")
	current = by_name.get(current_name) or by_label.get(current_name)
	past_prices = []
	for stay in profile.get("stays") or []:
		row = by_name.get(stay.get("room_type")) or by_label.get(stay.get("room_type"))
		if row:
			past_prices.append(float(row.get("base_price") or 0))
	preferred = (profile.get("preferred_room_type") or "").strip()
	target = None
	if preferred:
		target = by_name.get(preferred) or by_label.get(preferred)
	if target is None and past_prices and current is not None:
		typical = sorted(past_prices)[len(past_prices) // 2]
		if typical > float(current.get("base_price") or 0) + 0.5:
			higher = [row for row in types
			          if float(row.get("base_price") or 0) > float(current.get("base_price") or 0)]
			target = higher[0] if higher else None
	if target is None and profile.get("vip") and types and current is not None:
		top = types[-1]
		if top.get("name") != current.get("name"):
			target = top
	if target is not None and (current is None or target.get("name") != current.get("name")):
		out.append({
			"code": "upgrade",
			"title": f"Offer {target.get('room_type_name') or target.get('name')}",
			"detail": "Matches a previous stay, a saved preference, or VIP status.",
			"room_type": target.get("name"),
		})
	charges = {str(row.get("charge_type") or "") for row in (profile.get("charges") or [])}
	if charges & {"Restaurant", "Breakfast", "Dinner", "Minibar", "Room Service"}:
		out.append({
			"code": "dining",
			"title": "Offer dining they ordered before",
			"detail": "Previous stays posted restaurant, minibar or room-service charges.",
		})
	if "Spa" in charges:
		out.append({
			"code": "spa",
			"title": "Offer a spa time",
			"detail": "A previous stay included a spa charge.",
		})
	if "Laundry" in charges:
		out.append({
			"code": "laundry",
			"title": "Offer laundry",
			"detail": "They used laundry on an earlier stay.",
		})
	nights = [int(stay.get("nights") or 0) for stay in (profile.get("stays") or [])]
	if nights and (sum(nights) / len(nights)) >= 4:
		out.append({
			"code": "late_checkout",
			"title": "Offer a late check-out",
			"detail": "Their stays average four nights or more.",
		})
	return out


def auth_header(name: str | None, secret: str | None) -> dict:
	"""Header map for a provider call. Authorization values gain a Bearer
	prefix when the hotel pasted a raw token."""
	if not secret:
		return {}
	header = (name or "Authorization").strip() or "Authorization"
	value = secret.strip()
	if header.lower() == "authorization" and not value.lower().startswith(("bearer ", "token ")):
		value = f"Bearer {value}"
	return {header: value}


def parse_provider_json(status: int, body: str, *, ok_message: str) -> dict:
	"""Read a 2xx JSON body. A non-JSON 2xx still counts as accepted."""
	if status == 0 or not (200 <= int(status or 0) < 300):
		text = (body or "").strip() or f"HTTP {status}"
		return {"ok": False, "message": text[:300], "ids": []}
	data = None
	if body and body.strip():
		try:
			data = json.loads(body)
		except json.JSONDecodeError:
			data = None
	if isinstance(data, dict) and data.get("ok") is False:
		return {
			"ok": False,
			"message": str(data.get("message") or data.get("error") or "Provider refused.")[:300],
			"ids": [],
		}
	ids = []
	message = ok_message
	if isinstance(data, dict):
		message = str(data.get("message") or ok_message)[:300]
		raw_ids = data.get("key_ids") or data.get("id") or data.get("message_id")
		if isinstance(raw_ids, list):
			ids = [str(item) for item in raw_ids if item]
		elif raw_ids:
			ids = [str(raw_ids)]
	return {"ok": True, "message": message, "ids": ids}


def _money(value) -> Decimal:
	return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def build_journal(rows: list[dict], accounts: dict) -> dict:
	"""One balanced summary journal for closed invoices.

	`rows` are accounting.export_invoices rows (with `lines`). Debtors is
	debited for the credit total. Room revenue is required. Food and
	beverage posts to its own account when one is set, otherwise it folds
	into room revenue. Tax posts to its account, or folds into revenue when
	no tax account is set, so the entry still balances.
	"""
	debtors = (accounts.get("debtors") or "").strip()
	room_acct = (accounts.get("room") or "").strip()
	fnb_acct = (accounts.get("fnb") or "").strip()
	tax_acct = (accounts.get("tax") or "").strip()
	if not debtors or not room_acct:
		return {
			"ok": False,
			"error": "Set the debtors account and the room revenue account before syncing.",
			"lines": [],
		}
	room = Decimal(0)
	fnb = Decimal(0)
	tax = Decimal(0)
	for row in rows or []:
		for line in row.get("lines") or []:
			heads = {part.strip() for part in str(line.get("description") or "").split(",") if part.strip()}
			taxable = _money(line.get("taxable"))
			tax += _money(line.get("total_tax"))
			if not heads or heads <= ROOM_HEADS or heads & ROOM_HEADS:
				room += taxable
			else:
				fnb += taxable
	if not tax_acct:
		room += tax
		tax = Decimal(0)
	credits: dict[str, Decimal] = {}

	def add(account: str, amount: Decimal) -> None:
		if amount:
			credits[account] = credits.get(account, Decimal(0)) + amount

	add(room_acct, room)
	add(fnb_acct or room_acct, fnb)
	if tax_acct:
		add(tax_acct, tax)
	total = sum(credits.values(), Decimal(0)).quantize(MONEY, rounding=ROUND_HALF_UP)
	if total <= 0:
		return {"ok": False, "error": "Nothing to post for this date.", "lines": []}
	lines = [{"account": debtors, "debit": float(total), "credit": 0.0}]
	for account, amount in credits.items():
		lines.append({
			"account": account,
			"debit": 0.0,
			"credit": float(amount.quantize(MONEY, rounding=ROUND_HALF_UP)),
		})
	return {"ok": True, "error": None, "lines": lines}


def erpnext_payload(company: str, posting_date: str, remark: str, lines: list[dict]) -> dict:
	"""The Journal Entry body ERPNext's REST resource expects."""
	return {
		"doctype": "Journal Entry",
		"voucher_type": "Journal Entry",
		"company": company,
		"posting_date": posting_date,
		"user_remark": remark,
		"cheque_no": remark[:140],
		"cheque_date": posting_date,
		"accounts": [
			{
				"account": line["account"],
				"debit_in_account_currency": line["debit"],
				"credit_in_account_currency": line["credit"],
			}
			for line in lines
		],
	}
