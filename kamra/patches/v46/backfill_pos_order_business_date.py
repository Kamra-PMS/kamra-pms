"""Delivered POS orders from before business_date was stamped fall back to
DATE(creation) in the night audit report, which puts a bill rung after
midnight on the wrong day. Stamp them once: the posting date of the room
charge the order made (its folio line ends "(ORD-...)"), else the day it
was last modified (delivered)."""

from __future__ import annotations

import frappe


def execute():
	frappe.db.sql(
		"""
		UPDATE `tabPOS Order` o
		LEFT JOIN (
		  SELECT SUBSTRING_INDEX(SUBSTRING_INDEX(description, '(', -1), ')', 1) AS ord,
		         MIN(posting_date) AS posting_date
		  FROM `tabFolio Charge`
		  WHERE description LIKE '%%(ORD-%%)'
		  GROUP BY ord
		) fc ON fc.ord = o.name
		SET o.business_date = COALESCE(fc.posting_date, DATE(o.modified))
		WHERE o.business_date IS NULL AND o.status = 'Delivered'
		""")
