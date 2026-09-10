"""MCP tool registry — no Frappe site required."""

from pathlib import Path

from kamra.mcp_tools import (
	BY_NAME,
	GROUP_MODULE,
	TOOL_COUNT,
	TOOLS,
	module_allowed,
	prepare_arguments,
)


def test_tool_names_are_unique():
	names = [t.name for t in TOOLS]
	assert len(names) == len(set(names))


def test_tool_count_matches_registry():
	assert TOOL_COUNT == len(TOOLS) == len(BY_NAME)
	assert TOOL_COUNT >= 70


def test_wave1_parity_tools_registered():
	for name in (
		"find_reservations",
		"stay_detail",
		"amend_stay",
		"move_room",
		"record_payment",
		"void_charge",
		"apply_allowance",
		"close_folio",
		"advance_ticket",
		"hk_queue",
		"pos_create_order",
		"laundry_board",
	):
		assert name in BY_NAME, name


def test_groups_map_to_modules():
	assert BY_NAME["hk_queue"].module == "housekeeping"
	assert BY_NAME["pos_menu"].module == "fnb"
	assert BY_NAME["laundry_rates"].module == "fnb"
	assert BY_NAME["banquet_enquiry"].module == "events"
	assert BY_NAME["record_payment"].module == "finance"
	assert GROUP_MODULE["Housekeeping"] == "housekeeping"


def test_module_allowed_filters():
	hk = BY_NAME["hk_queue"]
	assert module_allowed(hk, modules={"housekeeping", "front-desk"})
	assert not module_allowed(hk, modules={"front-desk", "finance"})
	# Onboarding maps to admin — filtered when admin off
	assert BY_NAME["setup_property"].module == "admin"
	assert module_allowed(BY_NAME["setup_property"], modules={"admin", "front-desk"})
	assert not module_allowed(BY_NAME["setup_property"], modules={"front-desk"})


def test_duplicate_banquet_receipt_is_split():
	assert "banquet_record_receipt" in BY_NAME
	assert "banquet_receipt_document" in BY_NAME
	assert "banquet_receipt" not in BY_NAME


def test_stdio_sidecar_runs_at_eof():
	src = (Path(__file__).resolve().parents[2] / "mcp" / "kamra_mcp.py").read_text()
	assert src.strip().endswith("mcp.run()")
	assert src.index("if __name__") > src.index("for _spec in TOOLS")


def test_prepare_arguments_injects_property_and_bools():
	spec = BY_NAME["cancel_booking"]
	out = prepare_arguments(spec, {"reservation": "RES-1", "waive_fee": True}, "Hotel")
	assert out["reservation"] == "RES-1"
	assert out["waive_fee"] == 1
	assert "property" not in out

	book = BY_NAME["create_booking"]
	out = prepare_arguments(
		book,
		{"guest_name": "Rao", "room_type": "DLX", "check_in_date": "2026-09-01",
		 "check_out_date": "2026-09-03", "phone": ""},
		"Hotel",
	)
	assert out["property"] == "Hotel"
	assert out["source"] == "AI Agent"
	assert "phone" not in out
