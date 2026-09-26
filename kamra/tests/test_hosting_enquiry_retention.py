# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Hosting Enquiry retention rules (issue #93)."""

from kamra.hosting_enquiry_retention import (
	DEFAULT_RETENTION_MONTHS,
	KEEP_STATUSES,
)


def test_default_retention_is_24_months():
	assert DEFAULT_RETENTION_MONTHS == 24


def test_won_leads_are_kept():
	assert "Won" in KEEP_STATUSES
	assert "New" not in KEEP_STATUSES
	assert "Lost" not in KEEP_STATUSES
	assert "Contacted" not in KEEP_STATUSES
