"""ZATCA (FATOORA) e-invoicing for Saudi properties.

Phase 1 - generation - is complete: every invoice, credit note and paid
restaurant bill gets a UUID, a per-property invoice counter (ICV), the
previous invoice's hash (PIH), a UBL 2.1 XML, its ZATCA hash, and the TLV
QR printed on the bill. Records are append-only (ZATCA Invoice); a
cancelled invoice is answered with a credit note, never deleted.

Phase 2 - integration - is groundwork: the XML, hash chain and settings
(environment, EGS serial, CSID, private key) are what onboarding, XAdES
signing and the reporting / clearance APIs build on. Until an EGS unit is
onboarded the records stay "Generated".

The core never imports this module directly: the Saudi localization pack
calls it from its invoice hooks.
"""

import base64
import io
import uuid as uuidlib

import frappe
from frappe import _
from frappe.utils import now_datetime

from kamra.zatca import tlv, ubl

SETTINGS = "ZATCA Settings"
RECORD = "ZATCA Invoice"

# Folio / POS payment modes → UN/ECE 4461 payment means codes
PAYMENT_MEANS = {"Cash": "10", "Card": "48", "Bank Transfer": "42", "UPI": "42"}


# ── settings ─────────────────────────────────────────────────────────────

def settings_for(property: str):
	"""The property's ZATCA settings, created from the property record the
	first time they are needed - a Saudi site issues compliant QR codes
	from its first invoice without anyone opening a settings page."""
	name = frappe.db.get_value(SETTINGS, {"property": property})
	if name:
		return frappe.get_doc(SETTINGS, name)
	p = frappe.get_cached_doc("Property", property)
	doc = frappe.get_doc({
		"doctype": SETTINGS,
		"property": property,
		"enabled": 1,
		"seller_name": p.get("legal_name") or p.property_name,
		"vat_number": p.get("gstin"),
		"city_name": p.get("city"),
		"postal_code": p.get("pincode"),
		"street_name": p.get("address_line"),
	})
	doc.insert(ignore_permissions=True)
	return doc


def readiness(s) -> list[str]:
	"""What is missing for a valid e-invoice - shown in Settings, never a
	reason to stop the desk closing a bill."""
	missing = []
	vat = (s.vat_number or "").strip()
	if not (len(vat) == 15 and vat.isdigit() and vat[0] == "3" and vat[-1] == "3"):
		missing.append(_("VAT number (15 digits, starting and ending with 3)"))
	if not (s.seller_name or "").strip():
		missing.append(_("Seller name"))
	for field, label in (("cr_number", _("Commercial Registration")),
	                     ("street_name", _("Street")),
	                     ("district", _("District")),
	                     ("city_name", _("City"))):
		if not (s.get(field) or "").strip():
			missing.append(label)
	if not ((s.building_number or "").isdigit() and len(s.building_number) == 4):
		missing.append(_("Building number (4 digits)"))
	if not ((s.postal_code or "").isdigit() and len(s.postal_code) == 5):
		missing.append(_("Postal code (5 digits)"))
	return missing


def _seller(s) -> dict:
	return {
		"name": s.seller_name, "vat": s.vat_number, "crn": s.cr_number,
		"street": s.street_name, "building": s.building_number,
		"district": s.district, "city": s.city_name,
		"postal": s.postal_code, "additional": s.additional_number,
		"country": "SA",
	}


# ── issuing ──────────────────────────────────────────────────────────────

def issue(property: str, number: str, lines: list[dict], *,
          source_doctype: str, source_name: str,
          kind: str = "Simplified", doc_type: str = "Invoice",
          buyer: dict | None = None, delivery_date: str | None = None,
          payment_mode: str | None = None,
          billing_reference: str | None = None,
          reason: str | None = None):
	"""Append one document to the property's invoice chain. Idempotent
	per (source, number, type): re-closing never forks the chain."""
	existing = frappe.db.get_value(RECORD, {
		"property": property, "invoice_number": number,
		"document_type": doc_type})
	if existing:
		return frappe.get_doc(RECORD, existing)
	s = settings_for(property)
	if not s.enabled:
		return None
	# serialise the chain: ICV and PIH must be strictly sequential
	frappe.db.sql("SELECT name FROM `tabZATCA Settings` WHERE name=%s FOR UPDATE",
	              s.name)
	last_icv, last_hash = frappe.db.get_value(
		SETTINGS, s.name, ["last_icv", "last_invoice_hash"])
	currency = frappe.get_cached_value("Property", property, "currency") or "SAR"
	inv = {
		"number": number, "uuid": str(uuidlib.uuid4()),
		"icv": int(last_icv or 0) + 1,
		"pih": last_hash or ubl.FIRST_PIH,
		"issue_dt": now_datetime(), "kind": kind, "type": doc_type,
		"currency": currency, "billing_reference": billing_reference,
		"reason": reason, "seller": _seller(s), "buyer": buyer,
		"delivery_date": delivery_date,
		"payment_means": PAYMENT_MEANS.get(payment_mode or "", "10"),
		"lines": lines,
	}
	totals = ubl.compute(inv)
	inv["qr"] = tlv.phase1_qr(
		s.seller_name or "", s.vat_number or "",
		inv["issue_dt"].strftime("%Y-%m-%dT%H:%M:%S"),
		f"{totals['tax_inclusive']:.2f}", f"{totals['vat_total']:.2f}")
	xml, totals = ubl.build(inv)
	digest = ubl.invoice_hash(xml)
	rec = frappe.get_doc({
		"doctype": RECORD, "property": property,
		"document_type": doc_type, "invoice_kind": kind,
		"invoice_number": number, "billing_reference": billing_reference,
		"source_doctype": source_doctype, "source_name": source_name,
		"issued_on": inv["issue_dt"], "status": "Generated",
		"currency": currency,
		"tax_exclusive": float(totals["tax_exclusive"]),
		"vat_total": float(totals["vat_total"]),
		"tax_inclusive": float(totals["tax_inclusive"]),
		"uuid": inv["uuid"], "icv": inv["icv"],
		"invoice_hash": digest, "previous_hash": inv["pih"],
		"qr": inv["qr"], "reason": reason, "xml": xml,
	}).insert(ignore_permissions=True)
	frappe.db.set_value(SETTINGS, s.name, {
		"last_icv": inv["icv"], "last_invoice_hash": digest,
	}, update_modified=False)
	return rec


# ── adapters ─────────────────────────────────────────────────────────────

def _folio_lines(folio) -> list[dict]:
	return [{
		"name": c.description or c.charge_type or "Charge",
		"qty": 1,
		# a line's quantity and rate are folded into its net amount: ZATCA
		# checks net = price x qty, and hotel lines carry the night count
		# in the description already
		"net": float(c.amount or 0),
		"rate": float(c.gst_rate or 0),
	} for c in folio.charges]


def _folio_buyer(folio) -> tuple[str, dict]:
	res = frappe.db.get_value(
		"Reservation", folio.reservation,
		["guest_name", "company", "check_out_date"], as_dict=True) or {}
	company = res.get("company")
	if folio.folio_type == "Group" and folio.get("group_booking"):
		company = frappe.db.get_value(
			"Group Booking", folio.group_booking, "company") or company
	if company:
		c = frappe.db.get_value("Corporate Account", company,
		                        ["company_name", "gstin"], as_dict=True) or {}
		if c.get("gstin"):
			# a VAT-registered buyer gets a standard (B2B) tax invoice
			return "Standard", {"name": c.company_name, "vat": c.gstin}
		return "Simplified", {"name": c.get("company_name")}
	return "Simplified", {"name": res.get("guest_name")}


def issue_for_folio(folio_name: str):
	folio = frappe.get_doc("Folio", folio_name)
	if not folio.invoice_number:
		return None
	kind, buyer = _folio_buyer(folio)
	mode = folio.payments[0].mode if folio.get("payments") else None
	checkout = frappe.db.get_value("Reservation", folio.reservation,
	                               "check_out_date")
	return issue(folio.property, folio.invoice_number, _folio_lines(folio),
	             source_doctype="Folio", source_name=folio.name,
	             kind=kind, buyer=buyer, payment_mode=mode,
	             delivery_date=str(checkout) if checkout else None)


def credit_note_for_folio(folio_name: str, invoice_number: str, reason: str):
	"""ZATCA has no cancel: a voided invoice is reversed by a credit note
	for the same lines, referencing it."""
	original = frappe.db.get_value(RECORD, {
		"invoice_number": invoice_number, "document_type": "Invoice"},
		["invoice_kind"], as_dict=True)
	if not original:
		return None  # issued before ZATCA was on - nothing to reverse
	folio = frappe.get_doc("Folio", folio_name)
	_, buyer = _folio_buyer(folio)
	return issue(folio.property, f"CN-{invoice_number}", _folio_lines(folio),
	             source_doctype="Folio", source_name=folio.name,
	             kind=original.invoice_kind, doc_type="Credit Note",
	             buyer=buyer, billing_reference=invoice_number,
	             reason=reason or "Invoice cancelled")


def issue_for_pos_order(order_name: str, vat_rate: float):
	o = frappe.get_doc("POS Order", order_name)
	lines = [{"name": it.item_name, "qty": float(it.qty or 1),
	          "net": float(it.amount or 0), "rate": vat_rate}
	         for it in o.items if not it.voided]
	if float(o.discount_amount or 0):
		lines.append({"name": "Discount", "qty": 1,
		              "net": -float(o.discount_amount), "rate": vat_rate})
	return issue(o.property, o.name, lines,
	             source_doctype="POS Order", source_name=o.name,
	             buyer={"name": o.customer_name} if o.customer_name else None,
	             payment_mode=o.payment_mode)


# ── what the printed bill needs ──────────────────────────────────────────

def qr_svg_data_uri(payload: str) -> str:
	import pyqrcode
	buf = io.BytesIO()
	pyqrcode.create(payload, error="M", encoding="utf-8").svg(
		buf, scale=3, quiet_zone=2, xmldecl=False, svgns=True)
	return "data:image/svg+xml;base64," + base64.b64encode(
		buf.getvalue()).decode("ascii")


TITLES = {
	("Invoice", "Simplified"): ("Simplified Tax Invoice", "فاتورة ضريبية مبسطة"),
	("Invoice", "Standard"): ("Tax Invoice", "فاتورة ضريبية"),
	("Credit Note", "Simplified"): ("Simplified Credit Note", "إشعار دائن مبسط"),
	("Credit Note", "Standard"): ("Credit Note", "إشعار دائن"),
}


def print_block(source_doctype: str, source_name: str,
                number: str | None = None) -> dict | None:
	"""QR image, bilingual title and chain ids for a printed bill."""
	filters = {"source_doctype": source_doctype, "source_name": source_name,
	           "document_type": "Invoice"}
	if number:
		filters["invoice_number"] = number
	rec = frappe.db.get_value(
		RECORD, filters,
		["invoice_kind", "document_type", "qr", "uuid", "icv", "status",
		 "invoice_hash", "tax_inclusive", "vat_total"],
		as_dict=True, order_by="creation desc")
	if not rec:
		return None
	en, ar = TITLES[(rec.document_type, rec.invoice_kind)]
	return {
		"title": en, "title_ar": ar, "kind": rec.invoice_kind,
		"qr": rec.qr, "qr_image": qr_svg_data_uri(rec.qr),
		"uuid": rec.uuid, "icv": rec.icv, "status": rec.status,
		"hash": rec.invoice_hash,
		"tax_inclusive": rec.tax_inclusive, "vat_total": rec.vat_total,
	}
