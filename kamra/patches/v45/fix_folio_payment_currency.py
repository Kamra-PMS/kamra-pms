"""Stamp Folio Payment.currency from the property when it still has the
old INR schema default and this was not an FX row (#341).

Skips rows with fx_amount set (genuine foreign-currency payments)."""

from __future__ import annotations

import frappe


def execute():
	frappe.db.sql(
		"""
		UPDATE `tabFolio Payment` fp
		INNER JOIN `tabFolio` f ON f.name = fp.parent
		INNER JOIN `tabProperty` p ON p.name = f.property
		SET fp.currency = p.currency
		WHERE IFNULL(fp.currency, 'INR') = 'INR'
		  AND IFNULL(p.currency, '') != ''
		  AND p.currency != 'INR'
		  AND IFNULL(fp.fx_amount, 0) = 0
		"""
	)
