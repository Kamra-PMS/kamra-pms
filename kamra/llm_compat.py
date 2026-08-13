# Copyright (c) 2026, HeyKoala and contributors
# For license information, please see license.txt

"""OpenAI-compatible /v1/chat/completions payload helpers.

GPT-5.6 (luna / terra / sol) and other reasoning models default to a
non-none ``reasoning_effort``. Chat Completions then refuses function
tools:

    Function tools with reasoning_effort are not supported for
    gpt-5.6-luna in /v1/chat/completions. To use function tools, use
    /v1/responses or set reasoning_effort to 'none'.

Kamra talks to any OpenAI-compatible host (OpenAI, OpenRouter, Groq,
Ollama, vLLM…), so we stay on ``/chat/completions`` and pin effort to
``none`` when tools are sent. See https://github.com/Kamra-PMS/kamra-pms/issues/23
"""

from __future__ import annotations

DEFAULT_MODEL = "gpt-4o-mini"

# Prefixes matched at the start of the slug, after a provider prefix
# (``openai/gpt-5.6-luna``), or after a hyphen.
_REASONING_MARKERS = ("gpt-5", "o1", "o3", "o4")


def is_reasoning_model(model: str | None) -> bool:
	"""True for GPT-5.x / o-series slugs, including OpenRouter-style prefixes."""
	m = (model or "").strip().lower()
	if not m:
		return False
	# ``openai/gpt-5.6-luna`` → ``gpt-5.6-luna``
	if "/" in m:
		m = m.rsplit("/", 1)[-1]
	return any(m.startswith(p) for p in _REASONING_MARKERS)


def chat_payload(
	model: str | None,
	messages: list,
	*,
	tools: list | None = None,
	stream: bool = False,
	temperature: float = 0.2,
) -> dict:
	"""JSON body for ``POST /v1/chat/completions``.

	Reasoning models omit ``temperature`` (often rejected) and, when tools
	are present, send ``reasoning_effort: "none"`` so function calling works
	on Chat Completions.
	"""
	body: dict = {"model": model or DEFAULT_MODEL, "messages": messages}
	if tools:
		body["tools"] = tools
	if stream:
		body["stream"] = True
	if is_reasoning_model(model):
		if tools:
			body["reasoning_effort"] = "none"
	else:
		body["temperature"] = temperature
	return body


def retry_chat_payload(body: dict, error_text: str) -> dict | None:
	"""Return a patched body if the 400 looks recoverable, else None."""
	text = (error_text or "").lower()
	retry = dict(body)
	changed = False
	if "reasoning_effort" in text and retry.get("reasoning_effort") != "none":
		retry["reasoning_effort"] = "none"
		changed = True
	if "temperature" in text and "temperature" in retry:
		retry.pop("temperature", None)
		changed = True
	return retry if changed else None
