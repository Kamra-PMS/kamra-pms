"""MCP tool registry — no Frappe site required."""

from pathlib import Path

from kamra.mcp_tools import BY_NAME, TOOL_COUNT, TOOLS, prepare_arguments


def test_tool_names_are_unique():
	names = [t.name for t in TOOLS]
	assert len(names) == len(set(names))


def test_tool_count_matches_registry():
	assert TOOL_COUNT == len(TOOLS) == len(BY_NAME)
	assert TOOL_COUNT >= 50


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
