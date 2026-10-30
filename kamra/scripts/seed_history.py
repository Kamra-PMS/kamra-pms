"""Give the demo hotel a past: weeks of stays, bills, POS, housekeeping,
banquets and night audits, ending yesterday.

The public demo is wiped and rebuilt every night (reset_demo), so its
dashboards and reports would otherwise always be empty. This replays a
deterministic history through the real write paths - create_booking,
check_in, the POS, laundry, housekeeping, add_folio_payment, check_out,
close_folio, the city ledger, banquets, the night audit - one business
day at a time, with the clock set to that day. Every figure in Reports,
the audit packs and AR aging therefore ties out exactly as it would in a
real hotel, and lists sort by the day things happened.

Run with:
    bench --site <demo> execute kamra.scripts.seed_history.execute

Only for the demo property, and idempotent: does nothing once a Night
Audit Run exists for it. seed_demo calls it at the end of a fresh seed.
"""

from __future__ import annotations

import datetime
import random
import sys
import time
from contextlib import contextmanager

import frappe
from frappe.utils import add_days, date_diff, getdate, nowdate
from frappe.utils import data as _fdata

PROPERTY = "Kamra Demo Palace"
DAYS = 75
SEED = 2026

FRONT_DESK = "frontdesk@kamra.local"
HOUSEKEEPER = "hk@kamra.local"
FINANCE = "finance@kamra.local"
GM = "gm@kamra.local"

FIRST = [
	"Aditi", "Rahul", "Kavya", "Nikhil", "Ishaan", "Pooja", "Siddharth",
	"Neha", "Varun", "Tara", "Kabir", "Riya", "Aman", "Shreya", "Dev",
	"Lakshmi", "Farhan", "Zoya", "Imran", "Ayesha", "Joseph", "Maria",
	"Thomas", "Anjali", "Harish", "Gauri", "Manish", "Sana", "Yusuf",
	"Emma", "Liam", "Sofia", "Lucas", "Hana", "Kenji", "Amara", "Noah",
	"Chloe", "Mateo", "Elena", "Omar", "Leila", "Daniel", "Grace",
]
LAST = [
	"Bhat", "Kulkarni", "Reddy", "Joshi", "Chopra", "Banerjee", "Gupta",
	"Shetty", "Varghese", "Fernandes", "Qureshi", "Khan", "Patel", "Desai",
	"Hegde", "Mukherjee", "Saxena", "Thakur", "Kamath", "Naidu", "Walker",
	"Rossi", "Silva", "Tanaka", "Okafor", "Novak", "Haddad", "Becker",
	"Moreau", "Larsen",
]

# (company, credit days on its account, days it actually takes to pay;
# None never pays inside the window - the account collections chases)
COMPANIES = [
	("Northwind Logistics", 15, 25),
	("Bluepeak Software", 30, 45),
	("Sahyadri Pharma", 7, None),
]

# day of week -> occupancy target (Mon=0); weekends run hotter
OCCUPANCY = [0.58, 0.55, 0.62, 0.66, 0.78, 0.86, 0.72]

# (weight, source) for booking sources; Corporate books on a company
SOURCES = [
	(30, "OTA"), (18, "Website"), (16, "Phone"), (10, "Walk-in"),
	(10, "Corporate"), (6, "AI Agent"), (10, "Manual"),
]

# what in-house guests run up outside the POS: (type, text, low, high, tax%, odds)
EXTRAS = [
	("Minibar", "Minibar", 150, 650, 18, 0.18),
	("Spa", "Spa treatment", 1800, 4200, 18, 0.07),
]

LAUNDRY_ITEMS = ["Shirt", "Trousers", "Dress", "Socks (pair)", "Nightwear"]

TICKETS = [
	("Extra towels for the room", "Housekeeping", "Low"),
	("AC not cooling", "Maintenance", "High"),
	("TV remote not working", "Maintenance", "Medium"),
	("Airport drop at 6 am", "Concierge", "Medium"),
	("Late checkout request", "Front Desk", "Low"),
	("Hot water is slow", "Maintenance", "High"),
	("Extra pillows", "Housekeeping", "Low"),
	("Room service order delayed", "Room Service", "Medium"),
]

FOUND = [
	"Phone charger", "Black sunglasses", "Silver bracelet", "Kids' teddy bear",
	"Paperback novel", "Blue umbrella", "Wireless earbuds case",
]

# (customer, event type, venue suffix, attendees, days before today)
FUNCTIONS = [
	("Reddy-Joshi wedding reception", "Wedding", "Grand Ballroom", 220, 52),
	("Bluepeak quarterly offsite", "Conference", "Boardroom", 24, 38),
	("Kulkarni 60th birthday", "Birthday", "Garden Lawn", 80, 27),
	("Sahyadri Pharma product launch", "Product Launch", "Grand Ballroom", 150, 15),
	("Fernandes engagement dinner", "Engagement", "Riverside Deck", 60, 6),
]


# -- clock -------------------------------------------------------------------

_REAL_NOW = _fdata.now_datetime
_state: dict = {"at": None, "set_real": None}


def _sim_now() -> datetime.datetime:
	"""The simulated wall clock: the set moment plus real time since."""
	if _state["at"] is None:
		return _REAL_NOW()
	return _state["at"] + datetime.timedelta(seconds=time.monotonic() - _state["set_real"])


def _swap(old, new) -> int:
	"""Point every loaded frappe/kamra module that holds `old` at `new`.
	Modules bind now_datetime at import, so patching frappe.utils alone
	would miss `from frappe.utils import now_datetime` in kamra.*."""
	n = 0
	for name, mod in list(sys.modules.items()):
		if mod is None or not name.startswith(("frappe", "kamra")):
			continue
		try:
			if getattr(mod, "now_datetime", None) is old:
				mod.now_datetime = new
				n += 1
		except Exception:
			# lazy or odd modules that refuse attribute access stay as they are
			continue
	return n


def at(day: str, hour: int, minute: int = 0) -> None:
	# minutes may run past 59 (a long cleaning round); they roll into the hour
	_state["at"] = datetime.datetime.combine(getdate(day), datetime.time(hour)) \
		+ datetime.timedelta(minutes=minute)
	_state["set_real"] = time.monotonic()


@contextmanager
def simulated_past():
	"""Run the block on a movable clock, with outbound side effects off:
	no background jobs (WhatsApp, webhooks, OTA pushes, printers), no
	realtime pings to people browsing the demo, no email."""
	real_enqueue, real_publish = frappe.enqueue, frappe.publish_realtime
	muted = {
		"mute_emails": frappe.flags.mute_emails,
		"kamra_mute_webhooks": frappe.flags.kamra_mute_webhooks,
	}
	frappe.enqueue = lambda *a, **k: None
	frappe.publish_realtime = lambda *a, **k: None
	frappe.flags.mute_emails = True
	frappe.flags.kamra_mute_webhooks = True
	_swap(_REAL_NOW, _sim_now)
	try:
		yield
	finally:
		_state["at"] = None
		# modules imported during the run picked up _sim_now too
		_swap(_sim_now, _REAL_NOW)
		frappe.enqueue, frappe.publish_realtime = real_enqueue, real_publish
		for k, v in muted.items():
			frappe.flags[k] = v


# -- entry -------------------------------------------------------------------


def execute(days: int = DAYS) -> dict:
	if not frappe.db.exists("Property", PROPERTY):
		print(f"seed_history: no '{PROPERTY}' here, nothing to do.")
		return {"skipped": "no demo property"}
	if frappe.db.exists("Night Audit Run", {"property": PROPERTY}):
		print("seed_history: history already present, skipping.")
		return {"skipped": "history already present"}
	started = time.monotonic()
	user = frappe.session.user
	try:
		with simulated_past():
			stats = History(int(days)).run()
	finally:
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- seed script restores the caller after replaying staff actions
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- seed script runs outside the request cycle
	stats["seconds"] = round(time.monotonic() - started, 1)
	print(f"seed_history: {stats}")
	return stats


def after_reset():
	"""reset_demo's last step: replay the past, then open the demo again
	whatever happens (the guard also expires on its own)."""
	from kamra.demo_guard import end_rebuild
	try:
		return execute()
	finally:
		end_rebuild()


def _instant_modes() -> list[str]:
	"""The demo country's instant modes (a wallet / instant transfer)."""
	from kamra.localization import instant_payment_modes, pack_for
	return instant_payment_modes(pack_for(PROPERTY))


class History:
	def __init__(self, days: int):
		self.rng = random.Random(SEED)
		self.today = nowdate()
		self.start = add_days(self.today, -days)
		self.days = days
		self.stats: dict[str, int] = {}
		self.guests: list[tuple[str, str]] = []
		self.rooms = frappe.get_all(
			"Room", filters={"property": PROPERTY},
			fields=["name", "room_type", "room_number"], order_by="room_number")
		self.rooms_by_type: dict[str, list[str]] = {}
		for r in self.rooms:
			self.rooms_by_type.setdefault(r.room_type, []).append(r.name)
		self.busy: dict[str, set[str]] = {r.name: set() for r in self.rooms}
		self.companies: list[str] = []
		self.pay_after: dict[str, int] = {}
		self.outlets = frappe.get_all("POS Outlet", filters={"property": PROPERTY}, pluck="name")
		self.menu = {
			o: frappe.get_all("Menu Item", filters={"outlet": o, "available": 1}, pluck="name")
			for o in self.outlets
		}
		self.plan: list[dict] = []
		self.group: dict | None = None
		self.functions: list[dict] = []
		self.tickets: list[tuple[str, str]] = []

	def bump(self, key: str, n: int = 1) -> None:
		self.stats[key] = self.stats.get(key, 0) + n

	def attempt(self, key: str, fn, *args, quiet: bool = False, **kwargs):
		"""Call a write path; count it, or count and log the refusal. quiet
		is for refusals the plan expects (a no-show on a sold-out night)."""
		frappe.db.savepoint("seed_history_step")
		try:
			out = fn(*args, **kwargs)
			self.bump(key)
			return out
		except Exception:
			# undo whatever the refused call half-wrote, keep the day
			frappe.db.rollback(save_point="seed_history_step")
			self.bump(f"{key}_refused")
			if not quiet:
				frappe.log_error(title=f"seed_history: {key}")
			return None

	def as_user(self, user: str) -> None:
		frappe.set_user(user)  # nosemgrep: frappe-setuser -- demo seed acts as each demo staff member so history carries their names

	# -- setup ---------------------------------------------------------------

	def run(self) -> dict:
		self.as_user("Administrator")
		at(self.start, 7)
		self._mark_existing_stays()
		self._companies()
		self._guest_pool()
		frappe.db.set_value("Property", PROPERTY, "business_date", self.start,
		                    update_modified=False)
		# the group first: its rooms are promised before walk-in demand fills them
		self._plan_group()
		self._plan()
		self.functions = self._plan_functions()
		by_book: dict[str, list[dict]] = {}
		for s in self.plan:
			by_book.setdefault(s["book_on"], []).append(s)
		day = self.start
		while getdate(day) < getdate(self.today):
			self._day(day, by_book.get(day, []))
			day = add_days(day, 1)
		return self.stats

	def _hold(self, room: str, start, end) -> None:
		"""Mark room busy on every night from start up to (not incl.) end."""
		if room not in self.busy:
			return
		d = str(getdate(start))
		while getdate(d) < getdate(end):
			self.busy[room].add(d)
			d = add_days(d, 1)

	def _mark_existing_stays(self) -> None:
		"""Rooms already spoken for stay off our plan: the base seed's
		stays, a guest still in house past their date, room blocks, and
		rooms out of order."""
		for r in frappe.get_all(
				"Reservation",
				filters={"property": PROPERTY, "room": ("is", "set"),
				         "status": ("in", ["Confirmed", "Checked In"])},
				fields=["room", "check_in_date", "check_out_date", "status"]):
			end = r.check_out_date
			if r.status == "Checked In" and getdate(end) <= getdate(self.today):
				end = add_days(self.today, 1)
			self._hold(r.room, r.check_in_date, end)
		for b in frappe.get_all(
				"Room Block", filters={"property": PROPERTY},
				fields=["room", "from_date", "to_date", "block_status"]):
			if (b.block_status or "") != "Released" and b.from_date and b.to_date:
				self._hold(b.room, b.from_date, add_days(b.to_date, 1))
		for room in frappe.get_all(
				"Room", filters={"property": PROPERTY, "housekeeping_status": "Out of Order"},
				pluck="name"):
			self._hold(room, self.start, add_days(self.today, 1))

	def _companies(self) -> None:
		"""Three accounts with their own payment terms, set up the way the
		Companies and City Ledger screens save them."""
		for name, credit_days, pays_after in COMPANIES:
			if not frappe.db.exists("Corporate Account", {"company_name": name}):
				frappe.get_doc({
					"doctype": "Corporate Account", "company_name": name,
					"contact_name": "Accounts desk", "credit_allowed": 1,
				}).insert(ignore_permissions=True)
			acc = frappe.db.get_value("Corporate Account", {"company_name": name})
			if not frappe.db.exists("City Ledger Account", {"property": PROPERTY, "company": acc}):
				frappe.get_doc({
					"doctype": "City Ledger Account", "property": PROPERTY, "company": acc,
					"account_number": f"AR-{name[:20]}", "credit_limit": 0, "balance": 0,
					"use_default_credit_days": 0, "credit_days": credit_days,
				}).insert(ignore_permissions=True)
			self.companies.append(acc)
			self.pay_after[acc] = pays_after

	def _guest_pool(self) -> None:
		seen = set()
		while len(self.guests) < 140:
			name = f"{self.rng.choice(FIRST)} {self.rng.choice(LAST)}"
			if name in seen:
				continue
			seen.add(name)
			self.guests.append((name, f"+91 9{self.rng.randint(100000000, 999999999)}"))

	# -- plan ----------------------------------------------------------------

	def _plan(self) -> None:
		"""Decide every stay up front so rooms never clash."""
		day = self.start
		while getdate(day) < getdate(self.today):
			target = round(len(self.rooms) * OCCUPANCY[getdate(day).weekday()])
			taken = sum(1 for b in self.busy.values() if day in b)
			for _ in range(max(0, target - taken)):
				stay = self._new_stay(day)
				if stay:
					self.plan.append(stay)
			# bookings that never turn up, or call off
			for kind, odds in (("no_show", 0.10), ("cancel", 0.16)):
				ghost = self._ghost(day, kind) if self.rng.random() < odds else None
				if ghost:
					self.plan.append(ghost)
			day = add_days(day, 1)

	def _free_room(self, rt: str, arrive: str, nights: int) -> str | None:
		dates = [add_days(arrive, i) for i in range(nights)]
		for room in self.rooms_by_type[rt]:
			if not any(d in self.busy[room] for d in dates):
				for d in dates:
					self.busy[room].add(d)
				return room
		return None

	def _new_stay(self, arrive: str) -> dict | None:
		nights = self.rng.choices([1, 2, 3, 4, 5], [30, 32, 20, 12, 6])[0]
		types = list(self.rooms_by_type)
		self.rng.shuffle(types)
		for rt in types:
			room = self._free_room(rt, arrive, nights)
			if room:
				return self._stay(arrive, add_days(arrive, nights), rt, room)
		return None

	def _ghost(self, arrive: str, kind: str) -> dict | None:
		"""A booking that never stays. It still holds a room of its type
		until it is cancelled or the audit marks it, so it needs one free."""
		nights = self.rng.choice([1, 2])
		rt = self.rng.choice(list(self.rooms_by_type))
		if not self._free_room(rt, arrive, nights):
			return None
		stay = self._stay(arrive, add_days(arrive, nights), rt, None)
		stay["kind"] = kind
		return stay

	def _stay(self, arrive: str, depart: str, rt: str, room: str | None) -> dict:
		source = self.rng.choices([s for _w, s in SOURCES], [w for w, _s in SOURCES])[0]
		lead = 0 if source == "Walk-in" else self.rng.choice([0, 1, 2, 3, 5, 7, 10, 14, 21, 30])
		book_on = add_days(arrive, -lead)
		if getdate(book_on) < getdate(self.start):
			book_on = self.start
		# a few regulars come back
		guest = self.rng.choice(self.guests[:25] if self.rng.random() < 0.2 else self.guests)
		suite = rt.endswith("STE")
		self._seq = getattr(self, "_seq", 0) + 1
		return {
			"id": self._seq,
			"arrive": arrive, "depart": depart, "room_type": rt, "room": room,
			"source": source, "book_on": book_on, "guest": guest,
			"company": self.rng.choice(self.companies) if source == "Corporate" else None,
			"adults": self.rng.choice([1, 2, 2, 3] if suite else [1, 2, 2]),
			"kind": "stay", "res": None, "group": None,
		}

	def _plan_group(self) -> None:
		"""One corporate group: three rooms, two nights, about four weeks ago."""
		arrive = add_days(self.today, -26)
		if getdate(arrive) <= getdate(self.start):
			return
		rt = next((t for t in self.rooms_by_type if t.endswith("DLX")), next(iter(self.rooms_by_type)))
		self.group = {
			"name": "Bluepeak sales kickoff", "arrive": arrive, "depart": add_days(arrive, 2),
			"room_type": rt, "book_on": max(self.start, add_days(arrive, -12)),
			"company": self.companies[1], "doc": None,
		}
		for i in range(3):
			room = self._free_room(rt, arrive, 2)
			if not room:
				continue
			stay = self._stay(arrive, add_days(arrive, 2), rt, room)
			# names come in after the block is set up, one a day
			stay.update(kind="stay", group=self.group, company=self.companies[1],
			            book_on=max(add_days(self.group["book_on"], 1 + i), add_days(arrive, -5 + i)),
			            source="Corporate")
			self.plan.append(stay)

	def _plan_functions(self) -> list[dict]:
		venues = {v.venue_name: v.name for v in frappe.get_all(
			"Venue", filters={"property": PROPERTY}, fields=["name", "venue_name"])}
		menus = frappe.get_all("Banquet Menu", filters={"property": PROPERTY}, pluck="name")
		out = []
		for customer, kind, venue, pax, ago in FUNCTIONS:
			event = add_days(self.today, -ago)
			if getdate(event) <= getdate(self.start) or venue not in venues:
				continue
			out.append({
				"customer": customer, "type": kind, "venue": venues[venue], "pax": pax,
				"event": event, "enquire": max(self.start, add_days(event, -24)),
				"menu": self.rng.choice(menus) if menus else None, "doc": None,
			})
		# two on the books for the coming weeks, enquired during the window
		for customer, kind, venue, pax, ahead in (
				("Okafor-Silva wedding", "Wedding", "Garden Lawn", 180, 18),
				("Northwind leadership summit", "Conference", "Boardroom", 30, 9)):
			if venue in venues:
				out.append({
					"customer": customer, "type": kind, "venue": venues[venue], "pax": pax,
					"event": add_days(self.today, ahead), "enquire": add_days(self.today, -12),
					"menu": self.rng.choice(menus) if menus else None, "doc": None,
				})
		for f in out:
			# confirmed a few days after the enquiry, and always before the day
			f["confirm"] = str(min(getdate(add_days(f["enquire"], 4)),
			                       getdate(add_days(f["event"], -1))))
		return out

	# -- one business day ----------------------------------------------------

	def _day(self, day: str, bookings: list[dict]) -> None:
		at(day, 7, 30)
		self.as_user(FRONT_DESK)
		sess = self.attempt("tills_opened", self._open_till)
		if self.group and self.group["book_on"] == day:
			self._group_block()
		for s in bookings:
			self._book(s)
		self._functions_desk(day)
		at(day, 9, 0)
		self.as_user(HOUSEKEEPER)
		self._laundry_collect(day)
		# departures settle and leave
		at(day, 10, 30)
		self.as_user(FRONT_DESK)
		for s in self.plan:
			if s["res"] and s.get("in") and s["depart"] == day:
				self._check_out(s)
		at(day, 11, 15)
		self.as_user(HOUSEKEEPER)
		self._clean_rooms(day)
		at(day, 12, 0)
		self.as_user(FRONT_DESK)
		for s in self.plan:
			if s["res"] and s["arrive"] == day and s["kind"] == "cancel":
				self.attempt("cancelled", self._cancel, s)
		at(day, 13, 0)
		self._pos(day, "lunch")
		at(day, 14, 30)
		self.as_user(FRONT_DESK)
		for s in self.plan:
			if s["res"] and s["arrive"] == day and s["kind"] == "stay":
				self._check_in(s)
		at(day, 16, 0)
		self._tickets(day)
		at(day, 18, 0)
		self.as_user(HOUSEKEEPER)
		self._laundry_deliver()
		at(day, 20, 0)
		self._pos(day, "dinner")
		self.as_user(FRONT_DESK)
		for s in self.plan:
			if s.get("in") and not s.get("out") and s["arrive"] <= day < s["depart"]:
				self._extras(s)
		at(day, 23, 30)
		self._close_till(sess)
		self.as_user(FINANCE)
		self._collect_receivables(day)
		self.as_user("Administrator")
		self._agent_log(day)
		at(add_days(day, 1), 3, 0)
		self.attempt("night_audits", self._night_audit)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- seed script commits each simulated day so a failure keeps the days before it

	# -- front desk ----------------------------------------------------------

	def _open_till(self) -> str:
		from kamra.cashier import open_session
		return open_session(PROPERTY, opening_float=5000)["name"]

	def _close_till(self, sess: str | None) -> None:
		if not sess:
			return
		from kamra.cashier import _recompute_session_totals, close_session
		expected = _recompute_session_totals(sess)["expected_cash"]
		self.attempt("tills_closed", close_session, sess, counted_cash=expected)

	def _book(self, s: dict) -> None:
		from kamra.api import create_booking, pickup_group_room
		name, phone = s["guest"]
		key = f"demo-history-{s['id']}"
		if s["group"] and s["group"]["doc"]:
			out = self.attempt("group_pickups", pickup_group_room, s["group"]["doc"],
			                   s["room_type"], name, phone=phone, adults=1,
			                   idempotency_key=key)
		else:
			out = self.attempt(
				"bookings", create_booking,
				property=PROPERTY, room_type=s["room_type"],
				check_in_date=s["arrive"], check_out_date=s["depart"],
				guest_name=name, phone=phone, adults=s["adults"],
				company=s["company"],
				source="Manual" if s["source"] == "Corporate" else s["source"],
				assign_room=0, idempotency_key=key, quiet=s["kind"] != "stay")
		if out:
			s["res"] = out.get("reservation") or out.get("name")

	def _cancel(self, s: dict) -> None:
		from kamra.api import cancel_reservation
		cancel_reservation(s["res"], reason="Guest request", waive_fee=1)

	def _check_in(self, s: dict) -> None:
		from kamra.api import check_in
		if self.attempt("checked_in", check_in, s["res"], room=s["room"]) is not None:
			s["in"] = True

	def _folios(self, s: dict) -> list[dict]:
		return frappe.get_all(
			"Folio", filters={"reservation": s["res"]},
			fields=["name", "folio_type", "balance", "grand_total", "status"])

	def _extras(self, s: dict) -> None:
		from kamra.api import post_stay_charge
		for charge_type, desc, lo, hi, gst, odds in EXTRAS:
			if self.rng.random() < odds:
				self.attempt("charges", post_stay_charge, s["res"], charge_type, desc,
				             self.rng.randrange(lo, hi, 50), gst_rate=gst)

	def _check_out(self, s: dict) -> None:
		from kamra.api import add_folio_payment, check_out, close_folio
		inst = _instant_modes()
		modes = ["Card", *inst, "Cash", *inst, "Card"]
		for f in self._folios(s):
			if f.folio_type == "Company" or float(f.balance or 0) <= 0:
				continue
			self.attempt("payments", add_folio_payment, f.name,
			             self.rng.choice(modes), round(float(f.balance), 2))
		if self.attempt("checked_out", check_out, s["res"]) is None:
			return
		s["out"] = True
		# the checkout sheet issues the invoices for every settled bill
		for f in self._folios(s):
			if f.status != "Closed" and float(f.grand_total or 0) > 0 and float(f.balance or 0) == 0:
				self.attempt("invoices", close_folio, f.name)

	def _group_block(self) -> None:
		from kamra.api import create_group_block
		g = self.group
		out = self.attempt(
			"group_blocks", create_group_block, PROPERTY, g["name"], g["arrive"], g["depart"],
			[{"room_type": g["room_type"], "rooms_blocked": 4}], company=g["company"],
			cutoff_date=add_days(g["arrive"], -3), attendees=4)
		if out:
			g["doc"] = out.get("group_booking") or out.get("name")

	# -- housekeeping, laundry, tickets, lost and found ----------------------

	def _clean_rooms(self, day: str) -> None:
		from kamra.api import hk_claim_task, hk_log_item, hk_update_task
		tasks = frappe.get_all(
			"Housekeeping Task",
			filters={"property": PROPERTY, "status": ("in", ["Pending", "In Progress"]),
			         "task_type": "Checkout Clean"},
			fields=["name", "room", "status"])
		for i, t in enumerate(tasks):
			at(day, 11, 15 + 8 * i)
			if t.status == "Pending":
				self.attempt("hk_claimed", hk_claim_task, t.name)
				self.attempt("hk_started", hk_update_task, t.name, "In Progress")
			at(day, 11, 45 + 8 * i)
			self.attempt("hk_done", hk_update_task, t.name, "Done")
			if self.rng.random() < 0.05:
				self.attempt("lost_found", hk_log_item, PROPERTY, self.rng.choice(FOUND),
				             room=t.room)

	def _laundry_collect(self, day: str) -> None:
		from kamra.laundry import collect_laundry
		rates = frappe.get_all("Laundry Rate", filters={"property": PROPERTY},
		                       pluck="item_name")
		items = [i for i in LAUNDRY_ITEMS if i in rates] or rates[:3]
		if not items:
			return
		for s in self.plan:
			if s.get("in") and not s.get("out") and s["arrive"] < day < s["depart"] \
					and self.rng.random() < 0.12:
				lines = [{"item_name": n, "qty": self.rng.randint(1, 3)}
				         for n in self.rng.sample(items, min(2, len(items)))]
				self.attempt("laundry_orders", collect_laundry, PROPERTY,
				             room=s["room"], items=lines)

	def _laundry_deliver(self) -> None:
		from kamra.laundry import deliver_laundry, laundry_status, return_items
		for o in frappe.get_all("Laundry Order",
		                        filters={"property": PROPERTY, "status": "Collected"},
		                        pluck="name"):
			laundry_status(o, "In Process")
			laundry_status(o, "Ready")
			doc = frappe.get_doc("Laundry Order", o)
			return_items(o, {it.name: int(it.qty) for it in doc.items})
			self.attempt("laundry_delivered", deliver_laundry, o)

	def _tickets(self, day: str) -> None:
		from kamra.api import advance_ticket, create_ticket
		# yesterday's requests get closed off first
		self.as_user(FRONT_DESK)
		for name, opened in list(self.tickets):
			if opened < day:
				self.attempt("tickets_resolved", advance_ticket, name, "Resolved",
				             resolution_note="Done and confirmed with the guest.")
				self.tickets.remove((name, opened))
		in_house = [s for s in self.plan if s.get("in") and not s.get("out")
		            and s["arrive"] <= day < s["depart"]]
		for _ in range(self.rng.choice([0, 1, 1, 2])):
			if not in_house:
				break
			s = self.rng.choice(in_house)
			subject, category, priority = self.rng.choice(TICKETS)
			out = self.attempt("tickets", create_ticket, PROPERTY, subject, category,
			                   priority=priority, room=s["room"], reservation=s["res"])
			if out:
				name = out.get("name") or out.get("ticket")
				if self.rng.random() < 0.6:
					at(day, 17, 10)
					self.attempt("tickets_resolved", advance_ticket, name, "Resolved",
					             resolution_note="Sorted within the hour.")
				else:
					self.tickets.append((name, day))

	# -- restaurant and bar --------------------------------------------------

	def _pos(self, day: str, service: str) -> None:
		from kamra.pos import confirm_order, create_order, deliver_order, pay_order, remove_item
		self.as_user(FRONT_DESK)
		in_house = [s for s in self.plan if s.get("in") and not s.get("out")
		            and s["arrive"] <= day < s["depart"] and s["room"]]
		weekend = getdate(day).weekday() >= 4
		for outlet in self.outlets:
			items = self.menu.get(outlet) or []
			if not items:
				continue
			bar = "Bar" in outlet
			if service == "lunch" and bar:
				continue
			count = self.rng.randint(2, 5) if service == "lunch" else self.rng.randint(4, 9)
			if weekend:
				count += 2
			for n in range(count):
				at(day, 13 if service == "lunch" else 19, (n * 7) % 60)
				lines = [{"menu_item": m, "qty": self.rng.choice([1, 1, 2])}
				         for m in self.rng.sample(items, min(len(items), self.rng.randint(1, 4)))]
				to_room = in_house and self.rng.random() < 0.25
				room_stay = self.rng.choice(in_house) if to_room else None
				order = self.attempt(
					"pos_orders", create_order, outlet, lines,
					room=room_stay["room"] if room_stay else None,
					table_no=None if room_stay else f"T{self.rng.randint(1, 12)}",
					guests=self.rng.choice([1, 2, 2, 3, 4]))
				if not order:
					continue
				name = order.get("name") or order.get("order")
				doc = frappe.get_doc("POS Order", name)
				if len(doc.items) > 1 and self.rng.random() < 0.05:
					# the captain takes a line off before it goes to the kitchen
					self.attempt("pos_voided_lines", remove_item, name, doc.items[-1].name)
				self.attempt("pos_confirmed", confirm_order, name)
				if room_stay:
					self.attempt("pos_room_charges", deliver_order, name)
				else:
					self.attempt("pos_paid", pay_order, name,
					             self.rng.choice(["Card", *_instant_modes(), "Cash", "Card"]))

	# -- money in from companies ---------------------------------------------

	def _collect_receivables(self, day: str) -> None:
		"""Each company pays its bills a set number of days after they land,
		which leaves a realistic spread across the aging buckets."""
		if getdate(day).weekday() != 4:
			return
		from kamra.ledger import city_ledger_open_folios, city_ledger_settle
		for acc in frappe.get_all("City Ledger Account",
		                          filters={"property": PROPERTY, "disabled": 0},
		                          fields=["name", "company"]):
			wait = self.pay_after.get(acc.company, 30)
			if wait is None:
				continue
			due = 0.0
			for item in city_ledger_open_folios(acc.name):
				when = item.get("invoice_date") or item.get("posting_date") or item.get("date")
				if when and date_diff(day, when) >= wait:
					due += float(item.get("outstanding") or item.get("balance") or 0)
			if due > 0:
				self.attempt("city_ledger_receipts", city_ledger_settle, acc.name,
				             round(due, 2), mode="Bank Transfer",
				             reference=f"NEFT {getdate(day).strftime('%d%m')}")

	# -- banquets ------------------------------------------------------------

	def _functions_desk(self, day: str) -> None:
		from kamra import banquet
		for f in self.functions:
			if f["enquire"] == day and not f["doc"]:
				out = self.attempt(
					"banquet_enquiries", banquet.create_enquiry, PROPERTY, f["venue"],
					f["event"], f["customer"], event_type=f["type"], attendees=f["pax"],
					customer_phone=f"+91 98{self.rng.randint(10000000, 99999999)}",
					source="Phone", session="Evening")
				if not out:
					continue
				f["doc"] = out.get("function") or out.get("name")
				if f["menu"]:
					self.attempt("banquet_menus", banquet.add_menu, f["doc"], f["menu"],
					             qty=f["pax"])
				self.attempt("banquet_quotes", banquet.generate_quote, f["doc"])
				banquet.set_status(f["doc"], "Tentative")
			elif f["doc"] and day == f["confirm"]:
				self.attempt("banquet_confirmed", banquet.set_status, f["doc"], "Confirmed")
				total = float(frappe.db.get_value("Venue Booking", f["doc"], "grand_total") or 0)
				if total:
					self.attempt("banquet_receipts", banquet.record_receipt, f["doc"],
					             round(total * 0.3, 2), mode="Bank Transfer", kind="Advance")
			elif f["doc"] and day == add_days(f["event"], 1):
				total, paid = frappe.db.get_value(
					"Venue Booking", f["doc"], ["grand_total", "advance_received"]) or (0, 0)
				rest = round(float(total or 0) - float(paid or 0), 2)
				if rest > 0:
					self.attempt("banquet_receipts", banquet.record_receipt, f["doc"], rest,
					             mode="Bank Transfer", kind="Payment")
				self.attempt("banquet_closed", banquet.close_out, f["doc"],
				             pax_actual=f["pax"] - self.rng.randint(0, 12))

	# -- the agent, and the end of the day -----------------------------------

	def _agent_log(self, day: str) -> None:
		from kamra.savings import log_action
		for action, minutes, why, channel in self.rng.sample([
				("answer_guest_call", 6, "Answered a rate question and quoted a Deluxe", "Voice"),
				("create_reservation", 8, "Booked a two-night stay over WhatsApp", "WhatsApp"),
				("send_arrival_reminder", 4, "Confirmed tomorrow's arrival times", "WhatsApp"),
				("night_audit_prep", 25, "Reconciled the day's postings before the audit", "Desk"),
				("upsell_offer", 5, "Offered a suite upgrade at check-in", "WhatsApp"),
		], 2):
			at(day, self.rng.randint(9, 21), self.rng.randint(0, 59))
			self.attempt("agent_actions", log_action, action_type=action, property=PROPERTY,
			             minutes_saved=minutes, rationale=why, agent_name="Kamra Agent",
			             channel=channel)

	def _night_audit(self) -> None:
		from kamra.folio import run_night_audit
		run_night_audit(PROPERTY, mode="scheduled")
