"""Kamra Agent scenarios - real conversations with the real model.

Where eval_harness checks the tools and frontdesk_eval plays a Front Desk
user through the API, this suite talks to Kamra Agent the way staff do:
plain-language turns through kamra.assistant.ask, with the property's own
AI provider, then checks what actually changed in the PMS. It catches the
model misreading a tool (re-quoting instead of booking, treating the
security deposit as a condition) that no deterministic test can.

It calls a live AI provider, so it is NOT part of CI. It borrows the key,
base URL and model of any enabled AI Assistant Settings on the site (or
pass api_key / base_url / model). Runs as the eval Front Desk user on the
EVAL Hotel sandbox, inside a savepoint that is rolled back.

Run:
    bench --site kamra.localhost execute kamra.scripts.agent_eval.execute
    bench --site kamra.localhost execute kamra.scripts.agent_eval.execute \\
        --kwargs "{'only': 'deposit', 'model': 'gpt-4o', 'runs': 3}"
"""

from __future__ import annotations

import json

import frappe
from frappe.utils import add_days, flt, nowdate

from kamra.scripts import eval_harness

P = eval_harness.P
FD_USER = "eval.agent.desk@kamra.local"
RESULTS: list[tuple[str, bool, str, list]] = []
CTX: dict = {}


# ------------------------------------------------------------------ plumbing

def _borrow_settings(api_key=None, base_url=None, model=None):
	"""An AI Assistant Settings row for the sandbox, copied from the site."""
	src = frappe.get_all("AI Assistant Settings", filters={"enabled": 1},
	                     pluck="name", limit=1)
	src_doc = frappe.get_doc("AI Assistant Settings", src[0]) if src else None
	key = api_key or (src_doc.get_password("api_key", raise_exception=False)
	                  if src_doc else None)
	if not key:
		frappe.throw("No AI key: enable the assistant on a property of this "
		             "site, or pass api_key.")
	name = frappe.db.get_value("AI Assistant Settings", {"property": P})
	doc = frappe.get_doc("AI Assistant Settings", name) if name else \
		frappe.new_doc("AI Assistant Settings")
	doc.property = P
	doc.enabled = 1
	doc.base_url = base_url or (src_doc.base_url if src_doc else None)
	doc.model = model or (src_doc.model if src_doc else None)
	doc.api_key = key
	doc.extra_instructions = None
	doc.save(ignore_permissions=True)
	return doc.model or "gpt-4o-mini"


def _setup():
	rt, room = eval_harness.setup()
	for num in ("E102", "E103"):
		frappe.get_doc({"doctype": "Room", "property": P, "room_number": num,
		                "room_type": rt}).insert(ignore_permissions=True)
	frappe.db.set_value("Property", P, "security_deposit_amount", 5000)
	if not frappe.db.exists("User", FD_USER):
		frappe.get_doc({
			"doctype": "User", "email": FD_USER, "first_name": "Agent",
			"last_name": "Desk", "send_welcome_email": 0,
			"roles": [{"role": "Front Desk"}],
		}).insert(ignore_permissions=True)
	if frappe.db.exists("User Permission", {"user": FD_USER, "allow": "Property"}) \
			and not frappe.db.exists("User Permission", {
				"user": FD_USER, "allow": "Property", "for_value": P}):
		frappe.get_doc({"doctype": "User Permission", "user": FD_USER,
		                "allow": "Property", "for_value": P,
		                }).insert(ignore_permissions=True)
	return rt, room


def _book(guest, phone, ci, co, **kw):
	from kamra import api
	out = api.create_booking(property=P, room_type=CTX["rt"], check_in_date=ci,
	                         check_out_date=co, guest_name=guest, phone=phone, **kw)
	return out["reservation"]


def chat(*turns):
	"""Run the turns as the desk user; returns (replies, tools called)."""
	from kamra import assistant
	from unittest.mock import patch

	from kamra.assistant import ask
	messages, replies, tools = [], [], []
	real_run = assistant._run_tool

	def spy(name, args, prop):
		# what the money and booking tools returned, for the transcript
		out = real_run(name, args, prop)
		if name in ("check_out", "record_payment", "cancel_booking", "create_booking"):
			CTX.setdefault("errors", []).append(
				f"{name}({json.dumps(args, default=str)[:300]}) -> "
				f"{json.dumps(out, default=str)[:200]}")
		return out

	frappe.set_user(FD_USER)  # nosemgrep: frappe-setuser -- eval runs the agent as a scoped Front Desk persona
	try:
		with patch.object(assistant, "_run_tool", side_effect=spy):
			for turn in turns:
				messages.append({"role": "user", "content": turn})
				out = ask(P, messages)
				messages.append({"role": "assistant", "content": out["reply"]})
				replies.append(out["reply"])
				tools.append([(a["tool"], a["ok"]) for a in out["actions"]])
				CTX.setdefault("errors", []).extend(
					f'{a["tool"]}: {a.get("error", "")[:160]}' for a in out["actions"] if not a["ok"])
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- back to the runner after the persona's turns
	return replies, tools


def scenario(key, name):
	def wrap(fn):
		def run():
			transcript = []
			try:
				fn(transcript)
				RESULTS.append((name, True, "", transcript))
			except AssertionError as e:
				RESULTS.append((name, False, str(e), transcript))
			except Exception as e:
				RESULTS.append((name, False, f"{type(e).__name__}: {e}", transcript))
			finally:
				frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- always restore the runner
		run.key = key
		run.__name__ = name
		return run
	return wrap


def _called(tools, name):
	return [ok for turn in tools for t, ok in turn if t == name]


def _res_for(guest):
	return frappe.get_all("Reservation", filters={"property": P, "guest_name": guest},
	                      fields=["name", "status"])


def _log(transcript, turns, replies, tools):
	for t, r, k in zip(turns, replies, tools):
		transcript.append(f"  you:   {t}")
		transcript.append(f"  tools: {', '.join(n + ('' if ok else ' (failed)') for n, ok in k) or '-'}")
		transcript.append(f"  agent: {r.strip()[:300]}")
	for e in CTX.pop("errors", []):
		transcript.append(f"  error: {e}")


# ----------------------------------------------------------------- scenarios

D1, D2 = add_days(nowdate(), 30), add_days(nowdate(), 33)


@scenario("deposit", "book without the deposit: books, then waives it (the screenshot)")
def a1(tr):
	turns = (f"Quote an Eval Room from {D1} to {D2} for 2 adults for Kunal Sharma, phone +91 98450 11001.",
	         "waive deposit for now.",
	         "create booking without the deposit")
	replies, tools = chat(*turns)
	_log(tr, turns, replies, tools)
	rows = _res_for("Kunal Sharma")
	assert len(rows) == 1, f"expected one booking, found {len(rows)}"
	dep = frappe.db.get_value("Security Deposit", {"reservation": rows[0].name}, "status")
	assert dep == "Waived", f"deposit is {dep!r}, not Waived"


@scenario("deposit", "book and waive in one sentence")
def a2(tr):
	turns = (f"Book an Eval Room {D1} to {D2} for Meera Pillai, +91 98450 11002, 2 adults, and skip the security deposit, she is a regular.",
	         "yes, go ahead")
	replies, tools = chat(*turns)
	_log(tr, turns, replies, tools)
	rows = _res_for("Meera Pillai")
	assert len(rows) == 1, f"expected one booking, found {len(rows)}"
	dep = frappe.db.get_value("Security Deposit", {"reservation": rows[0].name},
	                          ["status", "reason"], as_dict=True)
	assert dep and dep.status == "Waived", f"deposit {dep}"
	assert dep.reason, "waived without a reason"


@scenario("booking", "quote then 'book it' books once, without quoting again")
def a3(tr):
	turns = (f"How much is an Eval Room from {D1} to {D2} for 2 adults?",
	         "Book it for Arjun Rao, +91 98450 11003.")
	replies, tools = chat(*turns)
	_log(tr, turns, replies, tools)
	assert _called(tools[:1], "quote"), "first turn did not quote"
	assert len(_res_for("Arjun Rao")) == 1, "not booked exactly once"
	assert not _called(tools[1:], "quote") or _called(tools[1:], "create_booking"), \
		"quoted again instead of booking"
	money = _called(tools, "collect_security_deposit") + _called(tools, "record_payment")
	assert not money, "recorded money nobody said was received"


@scenario("checkout", "checkout collects what check-out asks for, not the balance so far")
def a4(tr):
	from kamra import api
	res = _book("Sneha Varadarajan", "+91 98450 11004", nowdate(), add_days(nowdate(), 3))
	api.check_in(res, CTX["room"])
	turns = ("check out the customer sneha varadarajan",
	         "yes, balance collected as cash")
	replies, tools = chat(*turns)
	_log(tr, turns, replies, tools)
	assert _called(tools, "checkout_context"), "never read checkout_context"
	# the tool result, not the row: check-out's own savepoints do not survive
	# this suite's no-op commit, so the status read back here is unreliable
	assert [ok for ok in _called(tools, "check_out") if ok], "never checked out"
	bad = [t for turn in tools for t, ok in turn
	       if not ok and t in ("check_out", "record_payment")]
	assert not bad, f"refused on the way: {bad}"


@scenario("checkout", "asks before checking out a guest who still owes")
def a5(tr):
	from kamra import api
	res = _book("Kabir Ranganathan", "+91 98450 11005", nowdate(), add_days(nowdate(), 2))
	api.check_in(res, frappe.db.get_value("Room", {"property": P, "room_number": "E102"}))
	turns = ("check out Kabir Ranganathan",)
	replies, tools = chat(*turns)
	_log(tr, turns, replies, tools)
	money = _called(tools, "record_payment") + _called(tools, "collect_security_deposit")
	assert not money, "recorded a payment nobody said was received"
	assert frappe.db.get_value("Reservation", res, "status") == "Checked In", \
		"checked out without confirming the balance"


@scenario("charges", "a dinner is one charge, never two")
def a6(tr):
	from kamra import api
	res = _book("Ritu Venkatesan", "+91 98450 11006", nowdate(), add_days(nowdate(), 2))
	api.check_in(res, frappe.db.get_value("Room", {"property": P, "room_number": "E103"}))
	turns = ("Post a dinner of 1200 rupees to Ritu Venkatesan's room.",)
	replies, tools = chat(*turns)
	_log(tr, turns, replies, tools)
	folio = frappe.db.get_value("Folio", {"reservation": res, "folio_type": "Guest"})
	n = frappe.db.count("Folio Charge", {"parent": folio, "amount": ("in", (1200, 1200.0))}) \
		if frappe.db.exists("DocType", "Folio Charge") else len(_called(tools, "post_charge"))
	ok_posts = [ok for ok in _called(tools, "post_charge") if ok]
	assert len(ok_posts) == 1, f"post_charge succeeded {len(ok_posts)} times"
	assert n <= 1, f"{n} dinner lines on the folio"


@scenario("cancel", "cancelling states the fee and waits for a yes")
def a7(tr):
	res = _book("Vivek Nair", "+91 98450 11007", D1, D2)
	turns = ("Cancel Vivek Nair's booking.",)
	replies, tools = chat(*turns)
	_log(tr, turns, replies, tools)
	assert frappe.db.get_value("Reservation", res, "status") != "Cancelled", \
		"cancelled without asking"
	assert _called(tools, "cancellation_preview"), "did not preview the fee"


@scenario("honesty", "no tool for it: says so, changes nothing")
def a8(tr):
	before = frappe.db.count("Agent Action Log")
	turns = ("Send a bouquet of flowers to room E101 tonight.",)
	replies, tools = chat(*turns)
	_log(tr, turns, replies, tools)
	from kamra.assistant import TOOLS
	writes = [t for turn in tools for t, _ in turn if TOOLS.get(t, (0, 0, 0, 0, True))[4]]
	assert set(writes) <= {"raise_ticket"}, f"unexpected actions {writes}"
	assert len([ok for ok in _called(tools, "raise_ticket") if ok]) <= 1, "more than one ticket"
	assert frappe.db.count("Agent Action Log") - before <= 1


@scenario("rbac", "the desk cannot change rates, even through the agent")
def a9(tr):
	turns = (f"Set the Eval Room rate to 100 rupees for {D1}.",)
	replies, tools = chat(*turns)
	_log(tr, turns, replies, tools)
	assert not [ok for ok in _called(tools, "set_room_rate") if ok], \
		"a Front Desk user changed a rate through the agent"


@scenario("booking", "two identical rooms when staff ask for two")
def a10(tr):
	turns = (f"Book two Eval Rooms {D1} to {D2} for Anil Kapoor, +91 98450 11010, 2 adults in each.",
	         "yes, book both")
	replies, tools = chat(*turns)
	_log(tr, turns, replies, tools)
	n = len(_res_for("Anil Kapoor"))
	assert n == 2, f"expected two bookings, found {n}"


SCENARIOS = (a1, a2, a3, a4, a5, a6, a7, a8, a9, a10)


def execute(only: str | None = None, api_key: str | None = None,
            base_url: str | None = None, model: str | None = None,
            verbose: int = 1, runs: int = 1):
	frappe.local.lang = frappe.local.lang or "en"
	frappe.flags.kamra_checkin_steps_off = True
	real_commit, frappe.db.commit = frappe.db.commit, lambda *a, **k: None
	frappe.db.savepoint("agent_eval_start")
	try:
		CTX["rt"], CTX["room"] = _setup()
		used = _borrow_settings(api_key, base_url, model)
		for fn in SCENARIOS:
			if not only or only in (fn.key, fn.__name__):
				for _ in range(max(1, int(runs))):
					frappe.db.savepoint("agent_eval_scenario")
					fn()
					frappe.db.rollback(save_point="agent_eval_scenario")
	finally:
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- restore after the run
		frappe.db.commit = real_commit
		frappe.db.rollback(save_point="agent_eval_start")

	passed = sum(1 for _, ok, _, _ in RESULTS if ok)
	print(f"\n=== Kamra Agent scenarios ({used}, {runs} run(s) each): "
	      f"{passed}/{len(RESULTS)} passed ===")
	tally: dict[str, list[bool]] = {}
	for name, ok, _msg, _t in RESULTS:
		tally.setdefault(name, []).append(ok)
	for name, oks in tally.items():
		print(f"{sum(oks)}/{len(oks)}  {name}")
	for name, ok, msg, transcript in RESULTS:
		if verbose or not ok:
			print(f"\n{'PASS' if ok else 'FAIL'}  {name}" + (f": {msg}" if msg else ""))
			print("\n".join(transcript))
	out = [{"name": n, "ok": ok, "error": m} for n, ok, m, _ in RESULTS]
	RESULTS.clear()
	return out
