# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""Unit tests for OpenAI Chat Completions payload compatibility (issue #23)."""

from kamra.llm_compat import (
	chat_payload,
	is_reasoning_model,
	retry_chat_payload,
)


def test_classic_models_are_not_reasoning():
	assert not is_reasoning_model("gpt-4o-mini")
	assert not is_reasoning_model("gpt-4.1")
	assert not is_reasoning_model("")
	assert not is_reasoning_model(None)


def test_gpt56_family_detected():
	for slug in (
		"gpt-5.6-luna",
		"gpt-5.6-terra",
		"gpt-5.6-sol",
		"gpt-5.6",
		"GPT-5.6-Luna",
		"openai/gpt-5.6-luna",
		"gpt-5-mini",
		"o3-mini",
	):
		assert is_reasoning_model(slug), slug


def test_classic_payload_keeps_temperature_and_skips_effort():
	body = chat_payload("gpt-4o-mini", [{"role": "user", "content": "hi"}],
	                    tools=[{"type": "function"}])
	assert body["temperature"] == 0.2
	assert "reasoning_effort" not in body
	assert body["tools"]


def test_luna_with_tools_pins_effort_none():
	body = chat_payload("gpt-5.6-luna", [{"role": "user", "content": "hi"}],
	                    tools=[{"type": "function"}])
	assert body["reasoning_effort"] == "none"
	assert "temperature" not in body
	assert body["tools"]


def test_luna_without_tools_does_not_force_effort():
	body = chat_payload("gpt-5.6-luna", [{"role": "user", "content": "hi"}])
	assert "reasoning_effort" not in body
	assert "temperature" not in body


def test_retry_on_reasoning_effort_400():
	original = {"model": "gpt-5.6-luna", "messages": [], "tools": []}
	err = ("Function tools with reasoning_effort are not supported for "
	       "gpt-5.6-luna in /v1/chat/completions.")
	retry = retry_chat_payload(original, err)
	assert retry is not None
	assert retry["reasoning_effort"] == "none"


def test_retry_drops_temperature():
	original = {"model": "gpt-5.6-luna", "messages": [], "temperature": 0.2}
	retry = retry_chat_payload(original, "Unsupported value: 'temperature'")
	assert retry is not None
	assert "temperature" not in retry


def test_retry_none_when_unrelated():
	assert retry_chat_payload({"model": "x"}, "insufficient_quota") is None
