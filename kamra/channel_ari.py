"""Outbound ARI by changes: the outbox a channel manager like Channex certifies.

Channex asks a PMS to send only what changed, batched into date ranges, under
its rate limit (10 calls a minute per property and per endpoint), and a full
sync only when someone asks for it - never on a timer. So instead of pushing
the whole snapshot every hour and after every booking:

1. Anything that moves availability or price (a booking, a season, a rate
   plan, a room going out of order, a mapping) queues a `Channel ARI Outbox`
   row, in the same transaction, with the window of dates it can move.
2. One worker per connection (`flush_outbox`) joins the due rows, computes
   the cells of those dates with the same engines as everything else
   (`channel_manager.ari_snapshot` for availability, `pricing.quote` for each
   mapped rate plan), keeps only what differs from what the provider last
   accepted (`Channel ARI State`), joins consecutive equal days into ranges
   and sends ONE call per kind - under a local cap per endpoint, waiting a
   short batch window for restrictions so a few edits in a row go together,
   pausing on a 429 and backing off on a 5xx.

Adapters opt in by implementing `push_ari_changes(conn, kind, changes)` (see
kamra.channels); the others keep the hourly whole-snapshot `push_ari`.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate, nowdate

from kamra.authz import require_roles

ARI_HORIZON_DAYS = 500  # the full sync and the nightly sweep
ARI_MAX_DAYS = 730  # a user's change is sent whole up to here
KINDS = ("availability", "restrictions")


def _now() -> float:
	"""The module's clock (tests move it)."""
	return time.time()


# ---------------------------------------------------------------------------
# Cells: {external_id: {"YYYY-MM-DD": {field: value}}}
# ---------------------------------------------------------------------------


def _clip(date_from, date_to) -> tuple[str, str] | None:
	"""[date_from, date_to] inside [today, today + ARI_MAX_DAYS); None if
	nothing is left."""
	today = getdate(nowdate())
	start = max(getdate(date_from or today), today)
	end = min(getdate(date_to or add_days(today, ARI_HORIZON_DAYS - 1)),
	          getdate(add_days(today, ARI_MAX_DAYS - 1)))
	if end < start:
		return None
	return str(start), str(end)


def availability_cells(conn, date_from, date_to) -> dict[str, dict[str, dict]]:
	"""{external_room_id: {"YYYY-MM-DD": {"availability": int}}} for each mapped
	room type, once per external_room_id however many rate plans it has. It
	comes from channel_manager.ari_snapshot: the same engine as the
	double-booking guard, without copying it."""
	from kamra.channel_manager import ari_snapshot
	window = _clip(date_from, date_to)
	if not window:
		return {}
	start, end = window
	out: dict[str, dict[str, dict]] = {}
	for row in ari_snapshot(conn.property, conn.name, date_diff(end, start) + 1,
	                        start=start, with_rates=False):
		room = out.setdefault(str(row["external_room_id"]), {})
		for d in row["days"]:
			room.setdefault(d["date"], {"availability": int(d["available"])})
	return out


def _plan_night_rate(property: str, room_type: str, rate_plan: str | None, d) -> Decimal | None:
	"""The pricing engine's room total for one night from `d`, on `rate_plan`
	(None: the room type's base price), for the type's base occupancy (or 2
	adults), to 2 decimals. None when the night cannot be quoted or is not
	worth more than 0."""
	from kamra.pricing import quote
	adults = frappe.db.get_value("Room Type", room_type, "base_occupancy") or 2
	try:
		q = quote(property, room_type, str(d), str(add_days(d, 1)), adults=int(adults),
		          children=0, rate_plan=rate_plan or None, check_restrictions=False)
		total = Decimal(str(q["room_total"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
	except Exception:
		return None
	return total if total > 0 else None


def _restriction_day(rate: Decimal | None, rules: dict | None = None) -> dict:
	"""The one place a day's restriction values are put together: the rate,
	or stop-sell when there is no price, and the day's Rate Restrictions
	(`rules`, pricing.day_restrictions) when the property uses them."""
	out = {"stop_sell": True} if rate is None else {"rate": rate, "stop_sell": False}
	if rules is not None:
		out["stop_sell"] = out["stop_sell"] or rules["stop_sell"]
		out.update(min_stay_arrival=max(rules["min_nights"], 1),
		           max_stay=rules["max_nights"],
		           closed_to_arrival=rules["closed_to_arrival"],
		           closed_to_departure=rules["closed_to_departure"])
	return out


def restriction_cells(conn, date_from, date_to) -> dict[str, dict[str, dict]]:
	"""{external_rate_id: {"YYYY-MM-DD": {"rate": Decimal, "stop_sell": False}}}
	for each mapping with a provider rate plan id, priced by _plan_night_rate;
	a day without a price is {"stop_sell": True} and carries no rate."""
	from kamra.channel_manager import _mappings
	window = _clip(date_from, date_to)
	if not window:
		return {}
	start, end = window
	days = date_diff(end, start) + 1
	# ponytail: a property that never made a Rate Restriction sends none, so
	# rules a hotel keeps in the channel manager itself are not overwritten
	uses_rules = bool(frappe.db.exists("Rate Restriction", {"property": conn.property}))
	from kamra.pricing import day_restrictions, restriction_rules
	out: dict[str, dict[str, dict]] = {}
	for m in _mappings(conn.name):
		if not m.external_rate_id:
			continue
		rules = restriction_rules(conn.property, m.room_type, m.rate_plan, start, end) \
			if uses_rules else None
		plan = out.setdefault(str(m.external_rate_id), {})
		for i in range(days):
			d = getdate(add_days(start, i))
			plan[str(d)] = _restriction_day(
				_plan_night_rate(conn.property, m.room_type, m.rate_plan, d),
				day_restrictions(rules, d) if rules is not None else None)
	return out


def _canon(value):
	"""A cell value as stored in Channel ARI State (JSON): rates as 2-decimal
	strings, so 241 and "241.00" compare equal."""
	if isinstance(value, Decimal | float) and not isinstance(value, bool):
		return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
	return value


def diff_cells(cells: dict, sent: dict) -> dict:
	"""Only the fields whose value differs from `sent` (same shape); a day
	with no change does not appear, nor an id with no changed day."""
	out: dict[str, dict[str, dict]] = {}
	for ext_id, days in cells.items():
		known = sent.get(ext_id) or {}
		for d, values in days.items():
			before = known.get(d) or {}
			changed = {f: v for f, v in values.items()
			           if f not in before or _canon(before[f]) != _canon(v)}
			if changed:
				out.setdefault(ext_id, {})[d] = changed
	return out


def compress(cells: dict) -> list[dict]:
	"""[{"external_id", "date" | "date_from" + "date_to", "values"}]:
	CONSECUTIVE days with the SAME values become one range; a lone day goes
	as "date". Stable order: by external_id, then date."""
	out = []
	for ext_id in sorted(cells):
		run = None
		for d in sorted(cells[ext_id]):
			values = cells[ext_id][d]
			key = {f: _canon(v) for f, v in values.items()}
			if run and run["key"] == key and str(add_days(run["end"], 1)) == d:
				run["end"] = d
				continue
			if run:
				out.append(_range(ext_id, run))
			run = {"start": d, "end": d, "key": key, "values": values}
		if run:
			out.append(_range(ext_id, run))
	return out


def _range(ext_id: str, run: dict) -> dict:
	if run["start"] == run["end"]:
		return {"external_id": ext_id, "date": run["start"], "values": run["values"]}
	return {"external_id": ext_id, "date_from": run["start"], "date_to": run["end"],
	        "values": run["values"]}


# ---------------------------------------------------------------------------
# What the provider accepted (Channel ARI State)
# ---------------------------------------------------------------------------

_ID_FIELD = {"availability": "external_room_id", "restrictions": "external_rate_id"}


def _state_name(connection: str, kind: str, ext_id: str) -> str:
	return f"{connection}|{kind}|{ext_id}"


def _load_sent(connection: str, kind: str) -> dict:
	out = {}
	for r in frappe.get_all("Channel ARI State", filters={"connection": connection, "kind": kind},
	                        fields=["external_id", "sent_values"]):
		try:
			out[r.external_id] = json.loads(r.sent_values or "{}")
		except ValueError:
			out[r.external_id] = {}
	return out


def _remember(connection: str, kind: str, cells: dict) -> None:
	"""Merge accepted cells into Channel ARI State, field by field; days
	before today are dropped."""
	today = nowdate()
	for ext_id, days in cells.items():
		if not days:
			continue
		name = _state_name(connection, kind, ext_id)
		exists = frappe.db.exists("Channel ARI State", name)
		known = {}
		if exists:
			try:
				known = json.loads(frappe.db.get_value("Channel ARI State", name, "sent_values") or "{}")
			except ValueError:
				known = {}
		for d, values in days.items():
			known.setdefault(d, {}).update({f: _canon(v) for f, v in values.items()})
		payload = json.dumps({d: known[d] for d in sorted(known) if d >= today}, sort_keys=True)
		if exists:
			frappe.db.set_value("Channel ARI State", name, "sent_values", payload)
		else:
			frappe.get_doc({"doctype": "Channel ARI State", "connection": connection, "kind": kind,
				"external_id": ext_id, "sent_values": payload}).insert(ignore_permissions=True)


def _forget(connection: str, kind: str, ext_id: str | None) -> None:
	if ext_id:
		frappe.db.delete("Channel ARI State", {"name": _state_name(connection, kind, ext_id)})


def _expand(changes: list[dict]) -> dict:
	"""compress() undone: the cells a list of changes stands for."""
	cells: dict[str, dict[str, dict]] = {}
	for c in changes:
		start = c.get("date") or c["date_from"]
		end = c.get("date") or c["date_to"]
		for i in range(date_diff(end, start) + 1):
			cells.setdefault(c["external_id"], {})[str(add_days(start, i))] = dict(c["values"])
	return cells


# ---------------------------------------------------------------------------
# The outbox
# ---------------------------------------------------------------------------

ARI_JOB = "channex-ari::{connection}"
_ARI_PAUSE = "channex_ari_pause::{connection}::{kind}"
_ARI_CALLS = "channex_ari_calls::{connection}::{kind}"  # timestamps of the last minute's calls
_ARI_ERROR = "channex_ari_error::{connection}"


def _dt(ts: float) -> datetime:
	"""A timestamp of the module's clock as Frappe stores a Datetime: naive,
	on the system time zone, to the second."""
	from zoneinfo import ZoneInfo

	from frappe.utils import get_system_timezone
	return datetime.fromtimestamp(int(ts), ZoneInfo(get_system_timezone())).replace(tzinfo=None)


def _ts(value) -> float:
	from zoneinfo import ZoneInfo

	from frappe.utils import get_datetime, get_system_timezone
	return get_datetime(value).replace(tzinfo=ZoneInfo(get_system_timezone())).timestamp()


def _supports_outbox(provider: str | None) -> bool:
	from kamra.channels import provider_for
	try:
		return hasattr(provider_for(provider), "push_ari_changes")
	except Exception:
		return False


def outbox_connections(property: str | None = None) -> list[frappe._dict]:
	"""The active connections whose adapter takes changes (push_ari_changes)."""
	filters = {"active": 1}
	if property:
		filters["property"] = property
	return [c for c in frappe.get_all("Channel Manager Connection", filters=filters,
	                                  fields=["name", "property", "provider"])
	        if _supports_outbox(c.provider)]


def uses_outbox(connection: str) -> bool:
	return _supports_outbox(frappe.db.get_value("Channel Manager Connection", connection, "provider"))


def enqueue_flush(connection: str) -> None:
	"""One worker per connection at a time, after the change commits."""
	frappe.enqueue("kamra.channel_ari.flush_outbox", queue="short", connection=connection,
	               job_id=ARI_JOB.format(connection=connection), deduplicate=True,
	               enqueue_after_commit=True)


def _insert_row(values: dict) -> str:
	return frappe.get_doc(dict(values, doctype="Channel ARI Outbox")).insert(ignore_permissions=True).name


def _queued_here() -> set:
	"""The outbox rows this transaction inserted (emptied on commit or
	rollback). Only these can be joined: a Pending row another transaction
	committed may be the one a worker is claiming right now, and this
	transaction's snapshot would still show it Pending."""
	rows = getattr(frappe.local, "kamra_ari_queued", None)
	if rows is None:
		rows = frappe.local.kamra_ari_queued = set()

		def forget():
			frappe.local.kamra_ari_queued = None
		frappe.db.after_commit.add(forget)
		frappe.db.after_rollback.add(forget)
	return rows


def _queue(connection: str, property: str, date_from, date_to, kinds: str, reason: str,
           full: bool) -> str | None:
	window = _clip(date_from, date_to)
	if not window:
		return None
	values = {"connection": connection, "status": "Pending", "kinds": kinds, "full": int(bool(full)),
	          "date_from": window[0], "date_to": window[1], "attempts": 0}
	# the same change twice in one transaction is one row (an insert fires
	# both after_insert and on_update...). Never a row a worker claimed
	# (Sending): what it sends was computed before this change.
	queued = _queued_here()
	name = frappe.db.get_value("Channel ARI Outbox", dict(values, name=("in", sorted(queued))),
	                           "name") if queued else None
	if not name:
		name = _insert_row(dict(values, property=property, reason=(reason or "")[:140],
		                        queued_at=_dt(_now())))
		queued.add(name)
	enqueue_flush(connection)
	return name


def enqueue_ari_change(property: str, date_from=None, date_to=None, kinds: str = "both", reason: str = "",
                       full: bool = False) -> list[str]:
	"""Queue a change for every active connection of `property` whose adapter
	takes changes: one Pending row each, in the caller's transaction (a
	rolled-back change leaves none), and a flush after the commit. Dates
	default to today .. today + ARI_HORIZON_DAYS. Never raises: a failure
	goes to the Error Log and the save that triggered it goes on."""
	try:
		names = []
		for c in outbox_connections(property):
			name = _queue(c.name, c.property, date_from, date_to, kinds, reason, full)
			if name:
				names.append(name)
		return names
	except Exception as exc:
		frappe.log_error(title="Channex ARI enqueue",
		                 message=f"{property} · {reason} · {type(exc).__name__}: {exc}"[:1000])
		return []


def _hold(conn, kind: str, rows: list, now: float) -> int:
	"""Seconds this kind has to wait before a call: a pause (429 or a spent
	RateLimit header), the local cap of calls per minute, or - restrictions
	only - the batch window that lets a few edits in a row go together."""
	until = frappe.cache.get_value(_ARI_PAUSE.format(connection=conn.name, kind=kind))
	if until and float(until) > now:
		return max(1, math.ceil(float(until) - now))
	calls = sorted(t for t in (frappe.cache.get_value(
		_ARI_CALLS.format(connection=conn.name, kind=kind)) or []) if t > now - 60)
	if len(calls) >= int(conn.ari_calls_per_minute or 10):
		return max(1, math.ceil(calls[0] + 60 - now))
	batch = int(conn.ari_batch_seconds or 0)
	if kind == "restrictions" and batch and not any(r.full for r in rows):
		oldest = min((_ts(r.queued_at) for r in rows if r.queued_at), default=now)
		if now - oldest < batch:
			return max(1, math.ceil(oldest + batch - now))
	return 0


def _count_call(connection: str, kind: str, now: float) -> None:
	key = _ARI_CALLS.format(connection=connection, kind=kind)
	calls = [t for t in (frappe.cache.get_value(key) or []) if t > now - 60] + [now]
	frappe.cache.set_value(key, calls, expires_in_sec=120)


def _pause(connection: str, kind: str, seconds: int, now: float) -> int:
	seconds = max(1, int(seconds))
	frappe.cache.set_value(_ARI_PAUSE.format(connection=connection, kind=kind), now + seconds,
	                       expires_in_sec=seconds + 60)
	return seconds


def _ari_error(conn, exc: Exception) -> None:
	"""Channex unreachable (5xx, network, timeout): one Error Log an hour."""
	key = _ARI_ERROR.format(connection=conn.name)
	if frappe.cache.get_value(key):
		return
	frappe.cache.set_value(key, 1, expires_in_sec=3600)
	frappe.log_error(title=f"Channex ARI {conn.name}", message=f"{type(exc).__name__}: {exc}"[:1000])


def _windows(rows: list) -> list[tuple[str, str]]:
	"""The rows' date windows, clipped and merged where they touch."""
	spans = sorted(w for w in (_clip(r.date_from, r.date_to) for r in rows) if w)
	merged: list[tuple[str, str]] = []
	for start, end in spans:
		if merged and getdate(start) <= getdate(add_days(merged[-1][1], 1)):
			merged[-1] = (merged[-1][0], max(merged[-1][1], end))
		else:
			merged.append((start, end))
	return merged


def _cells(conn, kind: str, windows: list[tuple[str, str]]) -> dict:
	fn = availability_cells if kind == "availability" else restriction_cells
	out: dict[str, dict[str, dict]] = {}
	for start, end in windows:
		for ext_id, days in fn(conn, start, end).items():
			out.setdefault(ext_id, {}).update(days)
	return out


def _key(change: dict) -> tuple:
	return (str(change.get("external_id")), change.get("date"), change.get("date_from"), change.get("date_to"))


def _other(kind: str) -> str:
	return "restrictions" if kind == "availability" else "availability"


def _done(rows: list, kind: str, task_ids: list, now: float, detail: str = "") -> None:
	"""This kind of these rows went out (or had nothing to send)."""
	for r in rows:
		values = {}
		if task_ids:
			values["task_ids"] = "\n".join(filter(None, [r.task_ids or "", *task_ids]))[:2000]
			r.task_ids = values["task_ids"]
		if detail:
			values["detail"] = detail[:280]
		if r.kinds == "both":
			r.kinds = values["kinds"] = _other(kind)
		else:
			r.status = values["status"] = "Sent"
			values["sent_at"] = _dt(now)
		frappe.db.set_value("Channel ARI Outbox", r.name, values, update_modified=True)


def _backoff(rows: list, bumped: set, now: float) -> None:
	for r in rows:
		if r.name in bumped:
			continue
		bumped.add(r.name)
		r.attempts = int(r.attempts or 0) + 1
		wait = min(30 * 2 ** (r.attempts - 1), 1800)
		r.next_attempt_at = _dt(now + wait)
		frappe.db.set_value("Channel ARI Outbox", r.name, {
			"attempts": r.attempts, "next_attempt_at": r.next_attempt_at}, update_modified=True)


def _fail(rows: list, detail: str) -> None:
	for r in rows:
		r.status = "Failed"
		frappe.db.set_value("Channel ARI Outbox", r.name, {"status": "Failed", "detail": detail[:280]},
		                    update_modified=True)


def _rejected_detail(rejected: list[dict]) -> str:
	parts = []
	for c in rejected:
		when = c.get("date") or f"{c.get('date_from')}..{c.get('date_to')}"
		why = "; ".join(f"{f}: {', '.join(map(str, m))}" for f, m in (c.get("reasons") or {}).items())
		parts.append(f"{c.get('external_id')} {when} ({why})")
	return "Rejected: " + " | ".join(parts) if parts else ""


_CLAIM_SECONDS = 600  # a worker that dies mid-call: its rows are taken again after this
_ROW_FIELDS = ["name", "status", "date_from", "date_to", "kinds", "full", "queued_at", "next_attempt_at",
               "attempts", "task_ids"]


def _claim(connection: str, now: float) -> list:
	"""Take the connection's due rows - Pending with their wait over, or
	Sending whose worker died (its claim lapsed) - and mark them Sending
	until the pass ends, committed BEFORE the cells are computed: a change
	saved from here on gets a row of its own (_queue never joins a Sending
	row) and goes out on the next pass. The locking read keeps a second
	worker off the same rows."""
	rows = frappe.db.get_values("Channel ARI Outbox",
	                            {"connection": connection, "status": ("in", ("Pending", "Sending"))},
	                            _ROW_FIELDS, as_dict=True, order_by="creation asc", for_update=True)
	due = [r for r in rows if not r.next_attempt_at or _ts(r.next_attempt_at) <= now]
	for r in due:
		# a lapsed claim's wait was the claim itself: none left
		r.next_attempt_at = r.next_attempt_at if r.status == "Pending" else None
		r.status = "Sending"
		frappe.db.set_value("Channel ARI Outbox", r.name, {
			"status": "Sending", "next_attempt_at": _dt(now + _CLAIM_SECONDS)}, update_modified=True)
	if due:
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- ari worker: the claim is seen before any cell is computed
	return due


def _release(rows: list, reread: bool = False) -> None:
	"""The claimed rows this pass did not finish go back to Pending with
	their own wait (the retry's, or the one they had). After a rollback the
	row's status is read again: what the pass had not committed is undone."""
	for r in rows:
		if reread:
			r.status = frappe.db.get_value("Channel ARI Outbox", r.name, "status")
		if r.status != "Sending":
			continue
		r.status = "Pending"
		frappe.db.set_value("Channel ARI Outbox", r.name, {
			"status": "Pending", "next_attempt_at": r.next_attempt_at}, update_modified=True)


def flush_outbox(connection: str) -> dict:
	"""Worker (short queue). Claims the connection's rows that are due,
	merges their windows and, per kind: computes the cells, keeps what
	differs from Channel ARI State (everything if a row asks for a full
	sync), joins it into ranges and makes ONE call. What it did not finish
	goes back to Pending. Returns {kind: {"sent": n} | {"paused": s} |
	{"waiting": s} | {"retry": s} | {"failed": detail} | {"nothing": True}}."""
	conn = frappe.get_doc("Channel Manager Connection", connection)
	result = {kind: {"nothing": True} for kind in KINDS}
	if not conn.active or not _supports_outbox(conn.provider):
		return result
	now = _now()
	rows = _claim(connection, now)
	if not rows:
		return result
	try:
		_flush(conn, rows, now, result)
	except BaseException:
		frappe.db.rollback()
		_release(rows, reread=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- ari worker: an unexpected error gives the claimed rows back
		raise
	_release(rows)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- ari worker: the rows left for a later pass
	return result


def _flush(conn, rows: list, now: float, result: dict) -> None:
	from kamra.channels import provider_for
	provider = provider_for(conn.provider)
	connection = conn.name
	bumped: set = set()
	sent, failed = {}, []
	for kind in KINDS:
		krows = [r for r in rows if r.get("status") != "Failed" and r.kinds in ("both", kind)]
		if not krows:
			continue
		wait = _hold(conn, kind, krows, now)
		if wait:
			result[kind] = {"waiting": wait}
			continue
		full = any(r.full for r in krows)
		cells = _cells(conn, kind, _windows(krows))
		changes = compress(cells if full else diff_cells(cells, _load_sent(connection, kind)))
		if not changes:
			_done(krows, kind, [], now)
			result[kind] = {"sent": 0}
			frappe.db.commit()  # nosemgrep: frappe-manual-commit -- ari worker: nothing to send, the rows are done
			continue
		_count_call(connection, kind, now)
		try:
			out = provider.push_ari_changes(conn, kind, changes)
		except Exception as exc:
			status = getattr(exc, "status", None)
			if getattr(exc, "retry_after", None) is not None:
				result[kind] = {"paused": _pause(connection, kind, exc.retry_after, now)}
			elif status is not None and 400 <= int(status) < 500:
				detail = str(exc)[:280]
				_fail(krows, detail)
				failed.append(f"{kind}: {detail}")
				frappe.log_error(title=f"Channex ARI failed {conn.name}",
				                 message=f"{kind}: {type(exc).__name__}: {exc}"[:1000])
				result[kind] = {"failed": detail}
			else:
				_backoff(krows, bumped, now)
				_ari_error(conn, exc)
				result[kind] = {"retry": min(30 * 2 ** (max(r.attempts for r in krows) - 1), 1800)}
			frappe.db.commit()  # nosemgrep: frappe-manual-commit -- ari worker: keep the attempt and its error
			continue
		rejected = out.get("rejected") or []
		refused = {_key(c) for c in rejected}
		_remember(connection, kind, _expand([c for c in changes if _key(c) not in refused]))
		detail = _rejected_detail(rejected)
		_done(krows, kind, out.get("task_ids") or [], now, detail)
		if rejected:
			frappe.log_error(title=f"Channex ARI rejected {conn.name}", message=json.dumps(
				[dict(c, values={f: _canon(v) for f, v in (c.get("values") or {}).items()}) for c in rejected],
				default=str)[:4000])
		if out.get("wait"):
			_pause(connection, kind, out["wait"], now)
		sent[kind] = len(changes)
		result[kind] = {"sent": len(changes)}
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- ari worker: what the provider accepted is recorded before the next call
	if sent or failed:
		_report(conn, sent, failed)


def _report(conn, sent: dict, failed: list) -> None:
	"""last_push / last_push_status and the audit entry, as push_ari does."""
	from kamra.savings import log_action
	if failed:
		status = "FAILED: " + "; ".join(failed)
	else:
		status = f"OK: {sent.get('availability', 0)} availability, {sent.get('restrictions', 0)} restrictions"
	frappe.db.set_value("Channel Manager Connection", conn.name, {
		"last_push": frappe.utils.now_datetime(), "last_push_status": status[:140]}, update_modified=False)
	log_action("channel.ari_push", "Channel Manager Connection", conn.name, conn.property,
	           rationale=f"{conn.provider}: {status[:160]}", channel="API")
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- ari worker: the push result


def enqueue_ari_flushes() -> None:
	"""Every minute: a flush for each connection with Pending rows (what was
	waiting for its batch window, its pause or its retry) or Sending ones (a
	worker that died mid-call: the flush takes them once the claim lapses)."""
	for name in sorted(set(frappe.get_all("Channel ARI Outbox",
	                                      filters={"status": ("in", ("Pending", "Sending"))},
	                                      pluck="connection"))):
		enqueue_flush(name)


# ---------------------------------------------------------------------------
# Triggers, the full sync on demand and the nightly sweep
# ---------------------------------------------------------------------------

_HORIZON_SOURCES = ("Rate Plan", "Room Type", "Hurdle Rate", "Rate Guardrail")


def _dates(*values) -> list:
	return [getdate(v) for v in values if v]


def _window(starts: list, ends: list) -> tuple[str, str] | None:
	if not starts or not ends:
		return None
	start, end = min(starts), max(ends)
	return str(start), str(max(start, end))


def reservation_window(doc, method=None) -> tuple[str, str] | None:
	"""The nights a booking holds, before and after the change:
	[min(check-in), max(check-out)) as an inclusive (from, to). None when an
	update moved nothing that counts (dates, room type, room, status)."""
	before = doc.get_doc_before_save() if method == "on_update" else None
	if method == "on_update":
		if doc.flags.in_insert:
			return None  # after_insert has it
		fields = ("check_in_date", "check_out_date", "room_type", "room", "status")
		if before and not any(str(before.get(f) or "") != str(doc.get(f) or "") for f in fields):
			return None
	ins = _dates(doc.get("check_in_date"), before and before.get("check_in_date"))
	outs = [add_days(d, -1) for d in _dates(doc.get("check_out_date"), before and before.get("check_out_date"))]
	return _window(ins, outs)


def _mapping_property(doc) -> str | None:
	return frappe.db.get_value("Channel Manager Connection", doc.get("connection"), "property")


def _source(doc, method) -> tuple[str, str | None, str | None, str] | None:
	"""(property, date_from, date_to, kinds) a document's change can move, or
	None when it moves nothing ARI."""
	before = doc.get_doc_before_save() if method == "on_update" else None
	dt = doc.doctype
	if dt in ("Season", "Rate Restriction"):
		w = _window(_dates(doc.start_date, before and before.start_date),
		            _dates(doc.end_date, before and before.end_date))
		return (doc.property, *w, "restrictions") if w else None
	if dt in _HORIZON_SOURCES:
		return doc.property, None, None, "restrictions"
	if dt == "Room":
		if method == "on_update":
			if not before:
				return None
			out_of_order = (before.housekeeping_status == "Out of Order") != (
				doc.housekeeping_status == "Out of Order")
			if not out_of_order and before.room_type == doc.room_type:
				return None
		return doc.property, None, None, "availability"
	if dt == "Room Block":
		w = _window(_dates(doc.from_date, before and before.from_date),
		            _dates(doc.to_date, before and before.to_date))
		return (doc.property, *w, "availability") if w else None
	if dt == "Channel Room Mapping":
		return _mapping_property(doc), None, None, "both"
	return None


def _forget_mapping(doc, before=None) -> None:
	"""A mapping removed (or re-pointed) leaves its provider ids unknown: what
	was sent for them is forgotten, so a new mapping sends them whole. The
	room id's availability stays while another mapping still uses it."""
	old = before or doc
	if before and before.external_rate_id == doc.external_rate_id \
			and before.external_room_id == doc.external_room_id:
		return
	if not before or before.external_rate_id != doc.external_rate_id:
		_forget(old.connection, "restrictions", old.external_rate_id)
	if not before or before.external_room_id != doc.external_room_id:
		still = frappe.db.exists("Channel Room Mapping", {"connection": old.connection,
			"external_room_id": old.external_room_id, "name": ("!=", doc.name)})
		if not still:
			_forget(old.connection, "availability", old.external_room_id)


def on_ari_source_change(doc, method=None) -> None:
	"""doc_events (on_update, after_insert, on_trash) of what moves
	availability or price: queue its window. Never blocks the save."""
	try:
		if method == "on_update" and doc.flags.in_insert:
			return  # after_insert has it
		if doc.doctype == "Channel Room Mapping":
			before = doc.get_doc_before_save() if method == "on_update" else None
			if method == "on_trash" or before:
				_forget_mapping(doc, before)
		spec = _source(doc, method)
		if spec and spec[0]:
			enqueue_ari_change(spec[0], spec[1], spec[2], kinds=spec[3], reason=f"{doc.doctype} {doc.name}")
	except Exception as exc:
		frappe.log_error(title="Channex ARI enqueue",
		                 message=f"{doc.doctype} {doc.name} · {type(exc).__name__}: {exc}"[:1000])


def queue_full_sync(conn) -> None:
	"""Everything, today .. today + ARI_HORIZON_DAYS, in one call per kind."""
	if not conn.active:
		frappe.throw(_("This connection is not active."))
	if not _supports_outbox(conn.provider):
		frappe.throw(_("{0} does not take ARI changes.").format(conn.provider))
	if not frappe.db.exists("Channel Room Mapping", {"connection": conn.name}):
		frappe.throw(_("No room mappings yet - map your room types to the provider's room and rate ids first."))
	today = nowdate()
	_queue(conn.name, conn.property, today, add_days(today, ARI_HORIZON_DAYS - 1), "both", "Full sync", True)
	frappe.db.set_value("Channel Manager Connection", conn.name, "last_full_sync",
	                    frappe.utils.now_datetime(), update_modified=False)



@frappe.whitelist()
@require_roles("Revenue Manager", "Hotel Admin")
def request_full_sync(connection: str, confirm: int = 0) -> dict:
	"""The full sync button: {"queued": True}, or {"needs_confirm": True,
	"last_full_sync"} when the last one is less than 24 h old and confirm is
	not set (Channex admits one a day)."""
	conn = frappe.get_doc("Channel Manager Connection", connection)
	last = conn.last_full_sync
	if last and not int(confirm or 0):
		age = (frappe.utils.now_datetime() - frappe.utils.get_datetime(last)).total_seconds()
		if age < 86400:
			return {"needs_confirm": True, "last_full_sync": str(last)}
	queue_full_sync(conn)
	return {"queued": True}


@frappe.whitelist()
@require_roles("Revenue Manager", "Hotel Admin", "Front Desk")
def outbox_status(connection: str) -> dict:
	"""The connection panel: whether the connection goes through the outbox,
	rows waiting and failed, pauses per kind (s) and the last push and full
	sync."""
	conn = frappe.get_doc("Channel Manager Connection", connection)
	now = _now()
	paused = {}
	for kind in KINDS:
		until = frappe.cache.get_value(_ARI_PAUSE.format(connection=connection, kind=kind))
		if until and float(until) > now:
			paused[kind] = math.ceil(float(until) - now)
	count = lambda status: frappe.db.count("Channel ARI Outbox", {"connection": connection, "status": status})  # noqa: E731
	return {"outbox": _supports_outbox(conn.provider),
	        "pending": count("Pending") + count("Sending"), "failed": count("Failed"), "paused": paused,
	        "last_push": str(conn.last_push or ""), "last_push_status": conn.last_push_status or "",
	        "last_full_sync": str(conn.last_full_sync or "")}


def nightly_sweep() -> None:
	"""Daily, before dawn: per connection, one row (not a full sync) for today
	.. today + ARI_HORIZON_DAYS. Only differences go out: the day that just
	entered the horizon, whatever a trigger missed, what failed. Rows done
	more than 30 days ago are deleted."""
	today = nowdate()
	for c in outbox_connections():
		_queue(c.name, c.property, today, add_days(today, ARI_HORIZON_DAYS - 1), "both", "Nightly sweep", False)
	cutoff = add_days(frappe.utils.now_datetime(), -30)
	frappe.db.delete("Channel ARI Outbox", {"status": "Sent", "sent_at": ("<", cutoff)})
	frappe.db.delete("Channel ARI Outbox", {"status": "Failed", "modified": ("<", cutoff)})
