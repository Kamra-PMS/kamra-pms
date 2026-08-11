# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Pure tests for deposit_satisfied logic without a Frappe site."""


def deposit_satisfied_logic(required: float, status: str | None, collected: float) -> bool:
	if required <= 0:
		return True
	if status is None:
		return False
	if status == "Waived":
		return True
	return collected + 0.01 >= required


def test_no_deposit_required():
	assert deposit_satisfied_logic(0, None, 0) is True


def test_required_uncollected():
	assert deposit_satisfied_logic(5000, "Required", 0) is False


def test_waived():
	assert deposit_satisfied_logic(5000, "Waived", 0) is True


def test_fully_collected():
	assert deposit_satisfied_logic(5000, "Collected", 5000) is True
