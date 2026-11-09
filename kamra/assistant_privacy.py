"""Redact guest contact / ID fields in Kamra Agent tool results before they
are sent to an external LLM provider (DPDP s.8 / s.16 — issue #88)."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

_CONTACT_KEY_TOKENS = (
	"phone",
	"mobile",
	"whatsapp",
	"email",
	"aadhaar",
	"passport",
	"id_number",
	"id_no",
	"national_id",
	"gstin",
	"pan",
	"contact_no",
)


# Whole snake_case tokens only: a bare substring test would redact
# "occupancy" / "company" (pan) and "paid_now" (id_no).
_CONTACT_KEY_RE = re.compile(r"(?:^|_)(?:" + "|".join(_CONTACT_KEY_TOKENS) + r")s?(?:_|$)")


def is_contact_field(key: str) -> bool:
	k = (key or "").lower().replace("-", "_")
	return bool(_CONTACT_KEY_RE.search(k))


def mask_contact_value(value, *, strict: bool):
	if value is None:
		return value
	if strict:
		return "[redacted]"
	s = str(value).strip()
	if not s:
		return value
	digits = "".join(c for c in s if c.isdigit())
	if len(digits) >= 4:
		return f"***{digits[-4:]}"
	if "@" in s:
		local, _, domain = s.partition("@")
		if local and domain:
			return f"{local[0]}***@{domain}"
	return "***"


def _mask_all(data, *, strict: bool):
	if isinstance(data, dict):
		return {k: _mask_all(v, strict=strict) for k, v in data.items()}
	if isinstance(data, list):
		return [_mask_all(v, strict=strict) for v in data]
	return mask_contact_value(data, strict=strict)


def scrub_for_llm(data, *, strict: bool):
	"""Recursively mask contact-like fields in tool JSON sent to providers."""
	if isinstance(data, dict):
		out = {}
		for key, val in data.items():
			if is_contact_field(key):
				out[key] = _mask_all(val, strict=strict)
			else:
				out[key] = scrub_for_llm(val, strict=strict)
		return out
	if isinstance(data, list):
		return [scrub_for_llm(item, strict=strict) for item in data]
	return data


def processor_disclosure(base_url: str | None) -> str:
	"""Plain-language note for Settings — who processes chat/tool payloads."""
	try:
		parts = urlsplit((base_url or "").strip().lower())
		host, port = parts.hostname or "", parts.port
	except ValueError:
		host, port = "", None

	def on(*domains: str) -> bool:
		return any(host == d or host.endswith("." + d) for d in domains)

	if port == 11434 or "ollama" in host or host in ("127.0.0.1", "localhost"):
		return (
			"Local (Ollama): when the endpoint runs on this server or your LAN, "
			"chat and tool data stay on your infrastructure — no third-party LLM transfer."
		)
	if on("openai.com", "azure.com"):
		return (
			"OpenAI / Azure OpenAI: messages and tool results are processed under "
			"your cloud account (typically outside India unless you chose a regional deployment)."
		)
	if on("googleapis.com", "google.com"):
		return (
			"Google Gemini: messages and tool results are processed under your "
			"Google AI / Cloud account (cross-border transfer may apply)."
		)
	if on("groq.com"):
		return (
			"Groq: messages and tool results are processed under your Groq account "
			"(United States — cross-border transfer may apply)."
		)
	if on("openrouter.ai"):
		return (
			"OpenRouter: routes to the model you selected; that upstream provider "
			"processes messages and tool results under its terms and region."
		)
	return (
		"Your configured endpoint processes chat messages and tool results under "
		"that provider's terms, privacy policy, and region."
	)
