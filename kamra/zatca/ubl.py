"""UBL 2.1 XML for ZATCA e-invoices, and the ZATCA invoice hash.

Input is a *normalised* invoice (plain dict) so the same builder serves a
hotel folio, a restaurant bill or a credit note - the adapters in
kamra.zatca own the mapping from Kamra documents.

    {
      "number": "INV-SPH-26-00001", "uuid": "…", "icv": 7, "pih": "<b64>",
      "issue_dt": datetime, "kind": "Simplified" | "Standard",
      "type": "Invoice" | "Credit Note", "currency": "SAR",
      "billing_reference": "INV-…" (credit notes), "reason": "…",
      "seller": {name, vat, crn, street, building, district, city,
                 postal, additional, country},
      "buyer": {name, vat, street, building, district, city, postal,
                country} | None,
      "delivery_date": "YYYY-MM-DD" | None,
      "payment_means": "10" | "48" | "42" | "1",
      "lines": [{"name", "qty", "net", "rate"}],   # net excl. VAT
      "qr": "<b64>" | None,
    }

Negative lines (discounts, allowances) cannot be invoice lines under the
ZATCA rules; they become document-level allowances at their VAT rate.
Amounts are computed here, once, so the XML totals, the QR and the
stored record always agree.
"""

import base64
import hashlib
from decimal import ROUND_HALF_UP, Decimal

from lxml import etree

NS = {
	None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
	"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
	"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
	"ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}
CAC, CBC = "{%s}" % NS["cac"], "{%s}" % NS["cbc"]

# the hash of the first invoice's "previous invoice": base64(sha256("0"))
FIRST_PIH = ("NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0"
             "NjcyOWQ3M2EyN2ZiNTdlOQ==")

TYPE_CODE = {"Invoice": "388", "Credit Note": "381", "Debit Note": "383"}
KIND_NAME = {"Standard": "0100000", "Simplified": "0200000"}


def money(v) -> Decimal:
	return Decimal(str(v or 0)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def _fmt(v) -> str:
	return f"{money(v):.2f}"


def _category(rate: Decimal) -> str:
	# S = standard rated; a 0% line on a hotel bill is outside the scope
	# of VAT (O) - zero-rated / exempt supplies need a pack-level reason
	return "S" if rate > 0 else "O"


def compute(inv: dict) -> dict:
	"""Lines, allowances and totals, rounded the way the XML states them."""
	lines, allowances = [], {}
	for ln in inv["lines"]:
		net, rate = money(ln["net"]), Decimal(str(ln.get("rate") or 0))
		if net > 0:
			qty = Decimal(str(ln.get("qty") or 1)) or Decimal(1)
			vat = money(net * rate / 100)
			lines.append({"name": ln["name"], "qty": qty, "net": net,
			              "price": money(net / qty), "rate": rate, "vat": vat})
		elif net < 0:
			allowances[rate] = allowances.get(rate, Decimal(0)) + (-net)
	by_rate = {}
	for ln in lines:
		by_rate.setdefault(ln["rate"], Decimal(0))
		by_rate[ln["rate"]] += ln["net"]
	for rate, amt in allowances.items():
		by_rate[rate] = by_rate.get(rate, Decimal(0)) - money(amt)
	subtotals = [
		{"rate": r, "taxable": money(t), "tax": money(money(t) * r / 100)}
		for r, t in sorted(by_rate.items())]
	line_ext = sum((ln["net"] for ln in lines), Decimal(0))
	allowance_total = sum((money(a) for a in allowances.values()), Decimal(0))
	tax_excl = line_ext - allowance_total
	vat_total = sum((s["tax"] for s in subtotals), Decimal(0))
	return {
		"lines": lines,
		"allowances": {r: money(a) for r, a in allowances.items()},
		"subtotals": subtotals,
		"line_extension": money(line_ext),
		"allowance_total": money(allowance_total),
		"tax_exclusive": money(tax_excl),
		"vat_total": money(vat_total),
		"tax_inclusive": money(tax_excl + vat_total),
	}


def _el(parent, tag, text=None, **attrs):
	e = etree.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})
	if text is not None:
		e.text = str(text)
	return e


def _address(party, a: dict):
	addr = _el(party, CAC + "PostalAddress")
	for tag, key in (("StreetName", "street"), ("BuildingNumber", "building"),
	                 ("PlotIdentification", "additional"),
	                 ("CitySubdivisionName", "district"), ("CityName", "city"),
	                 ("PostalZone", "postal")):
		if a.get(key):
			_el(addr, CBC + tag, a[key])
	country = _el(addr, CAC + "Country")
	_el(country, CBC + "IdentificationCode", a.get("country") or "SA")


def _tax_scheme(parent):
	_el(_el(parent, CAC + "TaxScheme"), CBC + "ID", "VAT")


def _tax_category(parent, tag, rate: Decimal):
	cat = _el(parent, CAC + tag)
	code = _category(rate)
	_el(cat, CBC + "ID", code)
	_el(cat, CBC + "Percent", f"{rate:.2f}")
	if code == "O":
		_el(cat, CBC + "TaxExemptionReasonCode", "VATEX-SA-OOS")
		_el(cat, CBC + "TaxExemptionReason", "Not subject to VAT")
	_tax_scheme(cat)


def build(inv: dict) -> tuple[str, dict]:
	"""(xml, totals). The XML is unsigned - Phase 2 signing adds the
	UBLExtensions / Signature blocks, which the hash deliberately ignores."""
	t = compute(inv)
	cur = inv.get("currency") or "SAR"
	root = etree.Element("Invoice", nsmap=NS)
	_el(root, CBC + "ProfileID", "reporting:1.0")
	_el(root, CBC + "ID", inv["number"])
	_el(root, CBC + "UUID", inv["uuid"])
	dt = inv["issue_dt"]
	_el(root, CBC + "IssueDate", dt.strftime("%Y-%m-%d"))
	_el(root, CBC + "IssueTime", dt.strftime("%H:%M:%S"))
	_el(root, CBC + "InvoiceTypeCode", TYPE_CODE[inv.get("type") or "Invoice"],
	    name=KIND_NAME[inv.get("kind") or "Simplified"])
	_el(root, CBC + "DocumentCurrencyCode", cur)
	_el(root, CBC + "TaxCurrencyCode", cur)
	if inv.get("billing_reference"):
		ref = _el(root, CAC + "BillingReference")
		_el(_el(ref, CAC + "InvoiceDocumentReference"), CBC + "ID",
		    inv["billing_reference"])
	icv = _el(root, CAC + "AdditionalDocumentReference")
	_el(icv, CBC + "ID", "ICV")
	_el(icv, CBC + "UUID", inv["icv"])
	pih = _el(root, CAC + "AdditionalDocumentReference")
	_el(pih, CBC + "ID", "PIH")
	_el(_el(pih, CAC + "Attachment"), CBC + "EmbeddedDocumentBinaryObject",
	    inv.get("pih") or FIRST_PIH, mimeCode="text/plain")
	if inv.get("qr"):
		qr = _el(root, CAC + "AdditionalDocumentReference")
		_el(qr, CBC + "ID", "QR")
		_el(_el(qr, CAC + "Attachment"), CBC + "EmbeddedDocumentBinaryObject",
		    inv["qr"], mimeCode="text/plain")

	s = inv["seller"]
	sp = _el(_el(root, CAC + "AccountingSupplierParty"), CAC + "Party")
	if s.get("crn"):
		_el(_el(sp, CAC + "PartyIdentification"), CBC + "ID", s["crn"],
		    schemeID="CRN")
	_address(sp, s)
	pts = _el(sp, CAC + "PartyTaxScheme")
	_el(pts, CBC + "CompanyID", s.get("vat") or "")
	_tax_scheme(pts)
	_el(_el(sp, CAC + "PartyLegalEntity"), CBC + "RegistrationName", s["name"])

	b = inv.get("buyer") or {}
	bp = _el(_el(root, CAC + "AccountingCustomerParty"), CAC + "Party")
	if b.get("street") or b.get("city"):
		_address(bp, b)
	if b.get("vat"):
		bts = _el(bp, CAC + "PartyTaxScheme")
		_el(bts, CBC + "CompanyID", b["vat"])
		_tax_scheme(bts)
	if b.get("name"):
		_el(_el(bp, CAC + "PartyLegalEntity"), CBC + "RegistrationName", b["name"])

	if inv.get("delivery_date"):
		_el(_el(root, CAC + "Delivery"), CBC + "ActualDeliveryDate",
		    inv["delivery_date"])
	pm = _el(root, CAC + "PaymentMeans")
	_el(pm, CBC + "PaymentMeansCode", inv.get("payment_means") or "10")
	if inv.get("reason"):
		# credit / debit notes state why (BR-KSA-17)
		_el(pm, CBC + "InstructionNote", inv["reason"])

	for rate, amt in sorted(t["allowances"].items()):
		ac = _el(root, CAC + "AllowanceCharge")
		_el(ac, CBC + "ChargeIndicator", "false")
		_el(ac, CBC + "AllowanceChargeReason", "Discount")
		_el(ac, CBC + "Amount", _fmt(amt), currencyID=cur)
		_tax_category(ac, "TaxCategory", rate)

	_el(_el(root, CAC + "TaxTotal"), CBC + "TaxAmount", _fmt(t["vat_total"]),
	    currencyID=cur)
	tt = _el(root, CAC + "TaxTotal")
	_el(tt, CBC + "TaxAmount", _fmt(t["vat_total"]), currencyID=cur)
	for sub in t["subtotals"]:
		st = _el(tt, CAC + "TaxSubtotal")
		_el(st, CBC + "TaxableAmount", _fmt(sub["taxable"]), currencyID=cur)
		_el(st, CBC + "TaxAmount", _fmt(sub["tax"]), currencyID=cur)
		_tax_category(st, "TaxCategory", sub["rate"])

	lmt = _el(root, CAC + "LegalMonetaryTotal")
	_el(lmt, CBC + "LineExtensionAmount", _fmt(t["line_extension"]), currencyID=cur)
	_el(lmt, CBC + "TaxExclusiveAmount", _fmt(t["tax_exclusive"]), currencyID=cur)
	_el(lmt, CBC + "TaxInclusiveAmount", _fmt(t["tax_inclusive"]), currencyID=cur)
	_el(lmt, CBC + "AllowanceTotalAmount", _fmt(t["allowance_total"]), currencyID=cur)
	_el(lmt, CBC + "PrepaidAmount", "0.00", currencyID=cur)
	_el(lmt, CBC + "PayableAmount", _fmt(t["tax_inclusive"]), currencyID=cur)

	for i, ln in enumerate(t["lines"], 1):
		il = _el(root, CAC + "InvoiceLine")
		_el(il, CBC + "ID", i)
		_el(il, CBC + "InvoicedQuantity", f"{ln['qty']:.2f}", unitCode="PCE")
		_el(il, CBC + "LineExtensionAmount", _fmt(ln["net"]), currencyID=cur)
		ltt = _el(il, CAC + "TaxTotal")
		_el(ltt, CBC + "TaxAmount", _fmt(ln["vat"]), currencyID=cur)
		_el(ltt, CBC + "RoundingAmount", _fmt(ln["net"] + ln["vat"]), currencyID=cur)
		item = _el(il, CAC + "Item")
		_el(item, CBC + "Name", (ln["name"] or "Item")[:1000])
		_tax_category(item, "ClassifiedTaxCategory", ln["rate"])
		_el(_el(il, CAC + "Price"), CBC + "PriceAmount", _fmt(ln["price"]),
		    currencyID=cur)

	xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
	                     pretty_print=True).decode("utf-8")
	return xml, t


def invoice_hash(xml: str) -> str:
	"""ZATCA invoice hash: drop UBLExtensions, the Signature and the QR
	reference, canonicalise (C14N), SHA-256, base64 of the digest."""
	root = etree.fromstring(xml.encode("utf-8"))
	for path in ("ext:UBLExtensions", "cac:Signature",
	             "cac:AdditionalDocumentReference[cbc:ID='QR']"):
		for node in root.xpath(path, namespaces={k: v for k, v in NS.items() if k}):
			node.getparent().remove(node)
	canon = etree.tostring(root, method="c14n")
	return base64.b64encode(hashlib.sha256(canon).digest()).decode("ascii")
