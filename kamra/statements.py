"""Company statements and payment reminders (#238 phase 2).

A statement is one company's city ledger at one property: every open bill
with its invoice date, due date and days overdue, what was paid, money paid
ahead (unapplied credit), the balance and the aging by due date. The
numbers come from `kamra.ledger.city_ledger_account`, so they always agree
with the AR screen. It renders as an HTML page the desk prints or saves as
PDF, and is emailed as an attachment.

Reminders (Settings > Property > Company credit, off by default so an
upgrade never starts emailing customers): a daily job emails each
company's billing contact (Corporate Account.contact_email) when a bill
reaches a stage - 3 days before its due date, on the due date, and 15 days
after it. Each bill gets each stage at most once: a send is written to the
Activity log against the folio and that row is what stops a repeat. If the
job misses a day it sends the stage the bill has reached since, not the
older ones. Finance gets an in-app notice of what went out.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from kamra.authz import assert_property_access, require_roles

# (stage, days past the due date it starts), latest stage first
STAGES = (("late", 15), ("due", 0), ("pre", -3))
LOG_PREFIX = "credit_reminder_"


def reminder_stage(days_overdue: int) -> str | None:
	"""The reminder stage a bill this many days past due has reached."""
	for stage, start in STAGES:
		if days_overdue >= start:
			return stage
	return None


# --- statement ---------------------------------------------------------------

def statement(account: str) -> dict:
	from kamra.credit import _symbol
	from kamra.ledger import city_ledger_account
	st = city_ledger_account(account)
	prop = frappe.db.get_value("City Ledger Account", account, "property")
	st.update({
		"property": prop,
		"property_name": frappe.db.get_value("Property", prop, "property_name") or prop,
		"contact_email": frappe.db.get_value("Corporate Account", st["company"],
		                                     "contact_email"),
		"as_of": nowdate(),
		"currency_symbol": _symbol(prop),
	})
	return st


def _money(v) -> str:
	return f"{flt(v):,.2f}"


def statement_html(st: dict, lang: str = "en") -> str:
	from kamra.custom_reports import _kpi_html, _page_html, _table_html, _tr
	sym = st.get("currency_symbol") or ""
	kpis = [{"label": label, "value": f"{sym}{_money(st[f])}"} for f, label in (
		("balance", "Balance due"), ("overdue", "Overdue"),
		("not_due", "Not due"), ("unapplied_credit", "Unapplied credit"))]
	bills = {
		"columns": [{"id": i, "label": label} for i, label in (
			("invoice", "Invoice"), ("guest", "Guest"),
			("invoice_date", "Invoice date"), ("due_date", "Due date"),
			("days_overdue", "Days overdue"), ("billed", "Billed"),
			("paid", "Paid"), ("outstanding", "Outstanding"))],
		"rows": [{
			"invoice": r.get("invoice_number") or r["folio"],
			"guest": r.get("guest_name") or "",
			"invoice_date": r["invoice_date"], "due_date": r["due_date"],
			"days_overdue": r.get("days_overdue") or "",
			"billed": _money(r["billed"]), "paid": _money(r["paid"]),
			"outstanding": _money(r["outstanding"]),
		} for r in st["open_items"]],
	}
	bills["rows"].append({"invoice": _tr("Total", lang),
	                      "outstanding": _money(st["open_balance"])})
	aging = {
		"columns": [{"id": i, "label": label} for i, label in (
			("not_due", "Not due"), ("d1_30", "1 to 30"), ("d31_60", "31 to 60"),
			("d61_90", "61 to 90"), ("d90p", "90+"), ("overdue", "Overdue"))],
		"rows": [{k: _money(st[k]) for k in
		          ("not_due", "d1_30", "d31_60", "d61_90", "d90p", "overdue")}],
	}
	payments = {
		"columns": [{"id": i, "label": label} for i, label in (
			("posting_date", "Date"), ("reference", "Reference"), ("amount", "Amount"))],
		"rows": [{"posting_date": str(p.posting_date), "reference": p.reference or "",
		          "amount": _money(p.credit)} for p in st["payments"]],
	}
	esc = frappe.utils.escape_html
	body = (_kpi_html(kpis, lang)
	        + f"<h2>{esc(_tr('Open bills', lang))}</h2>" + _table_html(bills, lang)
	        + f"<h2>{esc(_tr('Aging by days overdue', lang))}</h2>"
	        + _table_html(aging, lang))
	if payments["rows"]:
		body += (f"<h2>{esc(_tr('Recent payments', lang))}</h2>"
		         + _table_html(payments, lang))
	meta = " · ".join([
		st["company"], st["property_name"],
		_tr("As of {0}", lang).format(st["as_of"]),
		_tr("Payment terms: {0} days", lang).format(st["credit_days"]),
	])
	return _page_html(_tr("Statement of account", lang), meta, body, lang)


def _filename(st: dict) -> str:
	safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in st["company"])[:40]
	return f"Statement_{safe}_{st['as_of']}.html"


def _send(st: dict, recipients: list[str], subject: str, lines: list[str],
          lang: str = "en") -> None:
	from kamra.custom_reports import _tr
	esc = frappe.utils.escape_html
	paras = "".join(f"<p>{esc(x)}</p>" for x in [
		_tr("Dear {0},", lang).format(st["company"]), *lines,
		_tr("Your statement of account is attached.", lang), st["property_name"]])
	frappe.sendmail(
		recipients=recipients, subject=subject,
		message=f'<div dir="{"rtl" if lang == "ar" else "ltr"}">{paras}</div>',
		attachments=[{"fname": _filename(st),
		              "fcontent": statement_html(st, lang).encode("utf-8")}])


@frappe.whitelist()
@require_roles("Finance", "Hotel Admin")
def company_statement(account: str, format: str = "json", lang: str = "en"):
	"""One company's statement at its property: open bills with invoice
	date, due date, days overdue and amounts, unapplied credit, recent
	payments, totals and aging by due date. format=html returns the
	printable page (print or save as PDF from the browser)."""
	st = statement(account)
	assert_property_access(st["property"])
	if (format or "").lower() == "html":
		return {"format": "html", "filename": _filename(st),
		        "content": statement_html(st, lang or "en")}
	return st


@frappe.whitelist(methods=["POST"])
@require_roles("Finance", "Hotel Admin")
def email_company_statement(account: str, recipients: str | None = None,
                            lang: str = "en"):
	"""Email a company its statement (HTML attachment). Without recipients
	it goes to the company's billing contact email."""
	from kamra.custom_reports import _tr
	st = statement(account)
	assert_property_access(st["property"])
	emails = [e.strip() for e in (recipients or st.get("contact_email") or "").split(",")
	          if e.strip()]
	if not emails:
		frappe.throw(_("{0} has no billing contact email. Add one on the corporate account or type an address.").format(st["company"]))
	lang = lang or "en"
	_send(st, emails, _tr("Statement of account from {0}", lang).format(
		st["property_name"]), [_tr("Balance due: {0}", lang).format(
			f"{st['currency_symbol']}{_money(st['balance'])}")], lang)
	from kamra.savings import log_action
	log_action("company_statement_emailed", "City Ledger Account", account,
	           st["property"], rationale=f"{st['company']}: statement to {', '.join(emails)}")
	return {"ok": True, "sent_to": emails}


# --- reminders ---------------------------------------------------------------

def _reminded(folio: str, stage: str) -> bool:
	return bool(frappe.db.exists("Agent Action Log", {
		"action_type": LOG_PREFIX + stage, "reference_doctype": "Folio",
		"reference_name": folio}))


def _line(r: dict, amount: float, stage: str, late: int, sym: str) -> str:
	inv, amt = r.get("invoice_number") or r["folio"], f"{sym}{_money(amount)}"
	if stage == "pre":
		return _("Invoice {0} for {1} is due on {2}.").format(inv, amt, r["due_date"])
	if stage == "due":
		return _("Invoice {0} for {1} is due today.").format(inv, amt)
	return _("Invoice {0} for {1} was due on {2} and is {3} days overdue.").format(
		inv, amt, r["due_date"], late)


def send_property_reminders(property: str) -> dict:
	"""Email each company with a bill that reached a reminder stage today
	and has not had that stage yet. Returns what was sent and the companies
	skipped for want of a billing email."""
	from kamra.ledger import _netted, days_overdue
	from kamra.savings import log_action
	today = nowdate()
	sent, no_email = [], []
	for account in frappe.get_all("City Ledger Account", pluck="name",
	                              filters={"property": property, "disabled": 0}):
		st = statement(account)
		due = []
		for r, amount in _netted(st["open_items"], st["unapplied_credit"]):
			late = days_overdue(r, today)
			stage = reminder_stage(late)
			if stage and not _reminded(r["folio"], stage):
				due.append((r, amount, stage, late))
		if not due:
			continue
		if not st.get("contact_email"):
			no_email.append(st["company"])
			continue
		_send(st, [st["contact_email"]],
		      _("Payment reminder from {0}").format(st["property_name"]),
		      [_line(r, a, s, late, st["currency_symbol"]) for r, a, s, late in due])
		for r, amount, stage, _late in due:
			log_action(LOG_PREFIX + stage, "Folio", r["folio"], property,
			           rationale=f"{st['company']}: {stage} reminder to "
			                     f"{st['contact_email']}, due {r['due_date']}, "
			                     f"{_money(amount)} owed")
			sent.append({"company": st["company"], "folio": r["folio"],
			             "stage": stage, "amount": amount})
	if sent or no_email:
		from kamra.night_audit import alert_staff
		stages = {"pre": _("due in 3 days"), "due": _("due today"),
		          "late": _("15 days overdue")}
		lines = [_("{0}: reminder sent for {1} ({2})").format(
			s["company"], s["folio"], stages[s["stage"]]) for s in sent]
		if no_email:
			lines.append(_("Not sent, no billing contact email: {0}").format(
				", ".join(no_email)))
		alert_staff(property, ("Finance",),
		            _("Payment reminders at {0}").format(property), "<br>".join(lines))
	return {"sent": sent, "no_email": no_email}


def run_payment_reminders():
	"""Daily: send due-date reminders for every property that turned them on."""
	from kamra.settings import get_setting
	for prop in frappe.get_all("Property", filters={"disabled": 0}, pluck="name"):
		if not cint(get_setting(prop, "credit_reminders")):
			continue
		try:
			send_property_reminders(prop)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit -- one property's sends and their log rows stand even if a later property fails
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Payment reminders failed: {prop}",
			                 message=frappe.get_traceback())
