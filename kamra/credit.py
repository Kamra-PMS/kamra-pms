"""Company credit control - payment terms, credit limit and overdue bills.

A company billed on the city ledger has, per property, a credit limit
(City Ledger Account.credit_limit, 0 = no limit) and payment terms (the
property's `default_credit_days` while use_default_credit_days is on, else
its own credit_days - 0 = due on the invoice date). Each bill moved to
the city ledger is due on invoice date + credit days.

`check_company_credit` is the one place that decides whether more can be
billed to a company: its exposure (AR still owed + what its stays in house
owe on company folios + the new amount) against the limit, and bills more
than `credit_overdue_grace_days` past their due date. The property's
`credit_control` setting decides what a failed check does:

  Off    nothing is checked
  Warn   the action goes ahead and returns the warning for the desk to show
  Block  refused (CREDIT_BLOCKED) unless Finance or a Hotel Admin overrides
         with a reason; the override is logged with who, why and the amount

It runs when a stay is booked on company billing (api.create_booking) and
when a bill moves to the city ledger at check-out (api.check_out,
ledger.city_ledger_transfer). The role check is on the server; an AI agent
(MCP, the copilot, a Kamra Agent user) can never override - it gets the
refusal reason.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from kamra.authz import assert_property_access, require_roles

POLICIES = ("off", "warn", "block")
DEFAULT_POLICY = "warn"
OVERRIDE_ROLES = frozenset({"Finance", "Hotel Admin", "System Manager",
                            "Administrator"})
BLOCKED = "CREDIT_BLOCKED"


class CreditBlocked(frappe.ValidationError):
	"""A company's credit check failed and the property blocks it."""


# --- policy ------------------------------------------------------------------

def credit_policy(property: str | None) -> str:
	from kamra.settings import get_setting
	value = str(get_setting(property, "credit_control") or "").strip().lower()
	return value if value in POLICIES else DEFAULT_POLICY


def grace_days(property: str | None) -> int:
	from kamra.settings import get_setting
	return max(int(get_setting(property, "credit_overdue_grace_days") or 0), 0)


def _symbol(property: str | None) -> str:
	if not property:
		return ""
	try:
		from kamra.localization import pack_for
		return pack_for(property).locale(
			frappe.get_cached_doc("Property", property)).get("currency_symbol", "")
	except Exception:
		return ""


def _is_agent() -> bool:
	from kamra.api import agent_channel
	if agent_channel():
		return True
	# an agent's service user (Administrator holds every role, Kamra Agent
	# included, and is not one)
	return (frappe.session.user != "Administrator"
	        and "Kamra Agent" in frappe.get_roles())


def can_override() -> bool:
	"""May the person acting now override a credit block? Finance or a
	Hotel Admin (System Manager / Administrator too), never an agent."""
	if _is_agent():
		return False
	return bool(OVERRIDE_ROLES & set(frappe.get_roles()))


# --- the check ---------------------------------------------------------------

def _resolve(account_or_company: str, property: str) -> tuple[str | None, str]:
	"""(City Ledger Account name or None, company) for an account name or a
	Corporate Account name at this property."""
	if account_or_company and frappe.db.exists("City Ledger Account",
	                                           account_or_company):
		row = frappe.db.get_value("City Ledger Account", account_or_company,
		                          ["company", "property"], as_dict=True)
		if row.property == property:
			return account_or_company, row.company
		account_or_company = row.company
	account = frappe.db.get_value(
		"City Ledger Account",
		{"property": property, "company": account_or_company, "disabled": 0},
		"name")
	return account, account_or_company


def in_house_exposure(company: str, property: str,
                      exclude_folios=None) -> float:
	"""What the company's stays in house owe on their company / group master
	folios right now (not yet on the city ledger)."""
	from kamra.ledger import company_payer_of
	skip = set(exclude_folios or ())
	rows = frappe.db.sql(
		"""
		SELECT f.name, f.folio_type, f.reservation, f.group_booking, f.balance
		FROM `tabFolio` f
		JOIN `tabReservation` r ON r.name = f.reservation
		WHERE f.property = %(p)s AND f.status = 'Open'
		  AND f.folio_type IN ('Company', 'Group')
		  AND r.status = 'Checked In'
		  AND (r.company = %(c)s OR f.group_booking IN (
		       SELECT name FROM `tabGroup Booking` WHERE company = %(c)s))
		""", {"p": property, "c": company}, as_dict=True)
	total = 0.0
	for f in rows:
		if f.name in skip or flt(f.balance) <= 0:
			continue
		if company_payer_of(f) == company:
			total += flt(f.balance)
	return round(total, 2)


def check_company_credit(account_or_company: str, property: str,
                         amount: float = 0, exclude_folios=None) -> dict:
	"""Can `amount` more be billed to this company at this property?

	Returns {ok, reasons, over_limit_by, overdue_amount, ...}. ok is False
	when the exposure (AR + in-house company folios + amount) is over a
	non-zero credit limit, or bills are more than the grace period past
	their due date. With credit control Off it is always ok."""
	from kamra.ledger import _account_position, overdue_past_grace
	policy = credit_policy(property)
	account, company = _resolve(account_or_company, property)
	amount = round(flt(amount), 2)
	out = {
		"ok": True, "policy": policy, "company": company, "account": account,
		"amount": amount, "reasons": [], "over_limit_by": 0.0,
		"overdue_amount": 0.0, "oldest_due_date": None,
		"credit_limit": 0.0, "ar_balance": 0.0, "in_house": 0.0,
		"exposure": amount, "grace_days": grace_days(property),
		"blocked": False,
	}
	if policy == "off" or not company:
		return out
	limit = 0.0
	ar = 0.0
	if account:
		limit = flt(frappe.db.get_value("City Ledger Account", account,
		                                "credit_limit"))
		pos = _account_position(account)
		ar = round(flt(frappe.db.sql(
			"""SELECT COALESCE(SUM(debit - credit), 0) FROM `tabCity Ledger Entry`
			   WHERE account = %s""", account)[0][0]), 2)
		overdue, oldest = overdue_past_grace(
			pos["open_items"], pos["unapplied_credit"], out["grace_days"])
		out["overdue_amount"], out["oldest_due_date"] = overdue, oldest
	in_house = in_house_exposure(company, property, exclude_folios)
	exposure = round(ar + in_house + amount, 2)
	out.update(credit_limit=limit, ar_balance=ar, in_house=in_house,
	           exposure=exposure)
	sym = _symbol(property)
	if limit > 0 and exposure > limit + 0.005:
		out["over_limit_by"] = round(exposure - limit, 2)
		out["reasons"].append(_(
			"Over the credit limit by {0}{1:,.2f} (limit {0}{2:,.2f}, owed and "
			"billed with this {0}{3:,.2f}).").format(
				sym, out["over_limit_by"], limit, exposure))
	if out["overdue_amount"] > 0.005:
		if out["grace_days"]:
			out["reasons"].append(_(
				"{0}{1:,.2f} overdue by more than {2} days (oldest due {3}).").format(
					sym, out["overdue_amount"], out["grace_days"],
					out["oldest_due_date"]))
		else:
			out["reasons"].append(_(
				"{0}{1:,.2f} overdue (oldest due {2}).").format(
					sym, out["overdue_amount"], out["oldest_due_date"]))
	out["ok"] = not out["reasons"]
	out["blocked"] = not out["ok"] and policy == "block"
	return out


def credit_applies(company: str | None) -> bool:
	"""Only a company on credit is billed on the city ledger."""
	return bool(company and frappe.db.get_value(
		"Corporate Account", company, "credit_allowed"))


def enforce_company_credit(company: str, property: str, amount: float,
                           override_reason: str | None = None,
                           context: str = "",
                           reference_doctype: str | None = None,
                           reference_name: str | None = None,
                           exclude_folios=None) -> dict:
	"""Run the check and apply the property's policy. Returns the check
	(with `warning` set when it failed under Warn, `overridden` when a
	block was overridden); raises CreditBlocked under Block, or
	PermissionError when someone who may not override tries to."""
	res = check_company_credit(company, property, amount, exclude_folios)
	if res["ok"]:
		return res
	from kamra.savings import log_action
	from kamra.api import agent_channel
	channel = agent_channel() or "Desk"
	what = f" ({context})" if context else ""
	summary = " ".join(res["reasons"])
	if res["policy"] == "warn":
		res["warning"] = _("{0}: {1}").format(company, summary)
		log_action("credit_warning", reference_doctype, reference_name, property,
		           rationale=f"{company}{what}: {summary} Went ahead (policy Warn).",
		           channel=channel, before_snapshot=_snapshot(res))
		return res
	reason = (override_reason or "").strip()
	if not reason:
		frappe.throw(
			_("{0}: {1} - {2} Credit control blocks this {3}. Finance or a "
			  "Hotel Admin can override it with a reason.").format(
				BLOCKED, company, summary, context or _("billing")),
			CreditBlocked, title=_("Company credit"))
	if _is_agent():
		frappe.throw(_("{0}: an AI agent can't override a credit block. {1} "
		               "Ask Finance or a Hotel Admin.").format(BLOCKED, summary),
		             frappe.PermissionError)
	if not can_override():
		frappe.throw(_("Only Finance or a Hotel Admin can override a credit "
		               "block."), frappe.PermissionError)
	user = frappe.session.user
	log_action("credit_override", reference_doctype, reference_name, property,
	           rationale=f"{company}{what}: {summary} Overridden by {user} for "
	                     f"{amount:,.2f}: {reason[:300]}",
	           approver=user, channel=channel,
	           before_snapshot=_snapshot(res),
	           after_snapshot={"amount": round(flt(amount), 2),
	                           "reason": reason[:500], "by": user})
	res["overridden"] = True
	res["override_reason"] = reason[:500]
	return res


def _snapshot(res: dict) -> dict:
	keys = ("company", "account", "policy", "amount", "credit_limit",
	        "ar_balance", "in_house", "exposure", "over_limit_by",
	        "overdue_amount", "oldest_due_date", "grace_days", "reasons")
	return {k: res.get(k) for k in keys}


def _for_ui(res: dict) -> dict:
	return {**res, "can_override": can_override()}


# --- endpoints ---------------------------------------------------------------

@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Night Auditor",
               "Revenue Manager", "Kamra Agent")
def company_credit_status(company: str, property: str, amount: float = 0):
	"""The credit check for billing `amount` more to a company, without
	doing anything: what the booking dialog shows before a company stay is
	booked. `applies` is False for a company not on credit."""
	assert_property_access(property)
	if not credit_applies(company):
		return {"applies": False, "ok": True, "reasons": [],
		        "policy": credit_policy(property), "can_override": can_override()}
	return {"applies": True, **_for_ui(check_company_credit(company, property, amount))}


def _city_ledger_moves(reservation: str) -> list[tuple[str, str, float]]:
	"""(folio, company, balance) for every folio of the stay the company
	pays - what check-out would move to the city ledger."""
	from kamra.ledger import company_payer_of
	out = []
	for f in frappe.get_all("Folio", filters={"reservation": reservation},
	                        fields=["name", "balance", "folio_type",
	                                "group_booking", "reservation"]):
		if flt(f.balance) > 0.009:
			payer = company_payer_of(f)
			if payer:
				out.append((f.name, payer, round(flt(f.balance), 2)))
	return out


def checkout_credit_checks(reservation: str) -> list[dict]:
	"""One credit check per company the stay's bills would move to."""
	by_company: dict[str, list] = {}
	for folio, company, bal in _city_ledger_moves(reservation):
		by_company.setdefault(company, []).append((folio, bal))
	prop = frappe.db.get_value("Reservation", reservation, "property")
	out = []
	for company, rows in by_company.items():
		res = check_company_credit(company, prop, sum(b for _f, b in rows),
		                           exclude_folios=[f for f, _b in rows])
		res["folios"] = [f for f, _b in rows]
		out.append(res)
	return out


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Night Auditor",
               "Kamra Agent")
def checkout_credit_preview(reservation: str):
	"""Before check-out: the credit check for each company the stay's bills
	would move to, so the desk can warn, or ask Finance / a Hotel Admin to
	override a block. Check-out re-runs the same check itself.

	Check-out first posts any night not yet on the folio, so the preview
	does the same inside a savepoint it rolls back - the amounts match
	what check-out will move, and nothing is written."""
	from kamra.folio import post_remaining_nights
	frappe.db.savepoint("kamra_credit_preview")
	try:
		post_remaining_nights(frappe.get_doc("Reservation", reservation))
		checks = [_for_ui(c) for c in checkout_credit_checks(reservation)]
	finally:
		frappe.db.rollback(save_point="kamra_credit_preview")
	prop = frappe.db.get_value("Reservation", reservation, "property")
	return {
		"reservation": reservation,
		"policy": credit_policy(prop),
		"checks": checks,
		"ok": all(c["ok"] for c in checks),
		"blocked": any(c["blocked"] for c in checks),
		"can_override": can_override(),
	}


@frappe.whitelist()
@require_roles("Front Desk", "Finance", "Hotel Admin", "Revenue Manager")
def company_credit_terms(company: str, property: str):
	"""A company's credit terms at one property: limit, credit days and
	what it owes (for the corporate account editor)."""
	assert_property_access(property)
	from kamra.ledger import effective_credit_days
	from kamra.settings import get_setting
	account = frappe.db.get_value(
		"City Ledger Account",
		{"property": property, "company": company, "disabled": 0},
		["name", "credit_limit", "credit_days", "use_default_credit_days",
		 "balance"], as_dict=True)
	return {
		"company": company,
		"credit_allowed": credit_applies(company),
		"account": account.name if account else None,
		"credit_limit": flt(account.credit_limit) if account else 0.0,
		"credit_days": int(account.credit_days or 0) if account else 0,
		"use_default_credit_days": bool(account.use_default_credit_days)
		                           if account else True,
		"effective_credit_days": effective_credit_days(
			account.name if account else None, property),
		"default_credit_days": int(get_setting(property, "default_credit_days") or 0),
		"balance": flt(account.balance) if account else 0.0,
		"policy": credit_policy(property),
		"can_edit": bool({"Finance", "Hotel Admin", "System Manager",
		                  "Administrator"} & set(frappe.get_roles())),
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def set_company_credit_terms(company: str, property: str,
                             credit_limit: float | None = None,
                             credit_days: int | None = None,
                             use_default_credit_days=None):
	"""Set a company's credit limit (0 = no limit) and payment terms at one
	property: `use_default_credit_days` 1 follows the property's default
	payment terms; 0 uses `credit_days` as given (0 = due on the invoice
	date). Creates its city ledger account if it has none. Logged with
	before / after."""
	assert_property_access(property)
	if not frappe.db.exists("Corporate Account", company):
		frappe.throw(_("Unknown company {0}.").format(company))
	from kamra.ledger import _ar_account
	acc = frappe.get_doc("City Ledger Account", _ar_account(property, company))
	before = {"credit_limit": flt(acc.credit_limit),
	          "credit_days": int(acc.credit_days or 0),
	          "use_default_credit_days": int(acc.use_default_credit_days or 0)}
	if credit_limit not in (None, ""):
		limit = flt(credit_limit)
		if limit < 0:
			frappe.throw(_("The credit limit can't be negative."))
		acc.credit_limit = limit
	if credit_days not in (None, ""):
		days = int(flt(credit_days))
		if days < 0 or days > 365:
			frappe.throw(_("Credit days must be between 0 and 365."))
		acc.credit_days = days
	if use_default_credit_days not in (None, ""):
		acc.use_default_credit_days = 1 if str(use_default_credit_days).lower() in (
			"1", "true") else 0
	acc.save(ignore_permissions=True)
	after = {"credit_limit": flt(acc.credit_limit),
	         "credit_days": int(acc.credit_days or 0),
	         "use_default_credit_days": int(acc.use_default_credit_days or 0)}
	if after != before:
		from kamra.savings import log_action
		log_action("credit_terms_changed", "City Ledger Account", acc.name,
		           property, rationale=f"{company}: credit limit "
		                               f"{after['credit_limit']:,.2f}, "
		                               + ("property default payment terms"
		                                  if after["use_default_credit_days"]
		                                  else f"{after['credit_days']} credit days"),
		           before_snapshot=before, after_snapshot=after)
	return company_credit_terms(company, property)
